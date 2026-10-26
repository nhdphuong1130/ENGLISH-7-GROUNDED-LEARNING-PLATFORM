import logging
from uuid import uuid4

import pytest
from pydantic import SecretStr

from english7.modules.ai.contracts import (
    AIRequest,
    ConversationTurn,
    Evidence,
    Language,
    ScopeStatus,
)
from english7.modules.ai.openrouter import (
    AIProviderError,
    OpenRouterEmbedder,
    OpenRouterProvider,
)


class FakeHTTP:
    def __init__(self, response=None, error=None) -> None:
        self.response = response
        self.error = error
        self.call = None

    def post_json(self, url, *, headers, payload, timeout_seconds):
        self.call = (url, headers, payload, timeout_seconds)
        if self.error:
            raise self.error
        return self.response


def request() -> AIRequest:
    fragment_id = uuid4()
    return AIRequest(
        question="What is a healthy habit?",
        language=Language.ENGLISH,
        evidence=(Evidence(fragment_id, "Exercise every day.", 20, 18),),
    )


def test_provider_uses_configured_model_timeout_and_structured_output() -> None:
    req = request()
    http = FakeHTTP(
        {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"answer":"Exercise every day.",'
                            '"language":"en","scope_status":"grounded",'
                            '"citations":["'
                            + str(req.evidence[0].fragment_id)
                            + '"]}'
                        )
                    }
                }
            ]
        }
    )
    provider = OpenRouterProvider(
        http=http,
        api_key=SecretStr("top-secret-key"),
        endpoint="https://openrouter.example/api/v1/chat/completions",
        model="configured/model",
        timeout_seconds=17.5,
    )

    result = provider.generate(req)

    url, headers, payload, timeout = http.call
    assert url.endswith("/chat/completions")
    assert headers["Authorization"] == "Bearer top-secret-key"
    assert payload["model"] == "configured/model"
    assert payload["response_format"] == {"type": "json_object"}
    assert timeout == 17.5
    assert result.citations == (req.evidence[0].fragment_id,)
    assert result.scope_status is ScopeStatus.GROUNDED


def test_provider_generates_ipa_for_personal_learning_content() -> None:
    http = FakeHTTP(
        {
            "choices": [
                {"message": {"content": '{"ipa":"/ˈbenɪfɪt/"}'}}
            ]
        }
    )
    provider = OpenRouterProvider(
        http=http,
        api_key=SecretStr("secret"),
        endpoint="https://openrouter.example/api/v1/chat/completions",
        model="configured/model",
        timeout_seconds=10,
    )

    ipa = provider.pronounce("benefit")

    assert ipa == "/ˈbenɪfɪt/"
    payload = http.call[2]
    assert payload["response_format"] == {"type": "json_object"}
    assert "benefit" in payload["messages"][1]["content"]


def test_tutor_prompt_separates_history_from_verified_evidence() -> None:
    req = request()
    conversational = AIRequest(
        question="Can you explain that again?",
        language=req.language,
        evidence=req.evidence,
        history=(
            ConversationTurn(
                learner="What is a healthy habit?",
                tutor="Exercise every day.",
            ),
        ),
        addressing_preference="Speak as a friendly classmate.",
    )

    messages = OpenRouterProvider._messages(conversational)

    system = messages[0]["content"].lower()
    user = __import__("json").loads(messages[1]["content"])
    assert "warm" in system
    assert "step-by-step" in system
    assert "never evidence" in system
    assert "outside" in system
    assert "reveal" in system
    assert user["current_question"] == "Can you explain that again?"
    assert user["conversation_history"][0]["learner"] == (
        "What is a healthy habit?"
    )
    assert user["verified_textbook_evidence"][0]["fragment_id"] == str(
        req.evidence[0].fragment_id
    )
    assert user["addressing_preference"] == "Speak as a friendly classmate."


def test_tutor_prompt_requires_the_entire_answer_in_selected_language() -> None:
    messages = OpenRouterProvider._messages(request())

    system = messages[0]["content"].lower()
    assert "entire answer" in system
    assert "requested language" in system


def test_social_turn_prompt_allows_natural_reply_without_textbook_citations() -> None:
    messages = OpenRouterProvider._messages(
        AIRequest(
            question="xin chào",
            language=Language.VIETNAMESE,
            evidence=(),
            social_turn=True,
        )
    )

    system = messages[0]["content"].lower()
    user = __import__("json").loads(messages[1]["content"])
    assert "social" in system
    assert "no textbook citations" in system
    assert "if social_turn is true" in system
    assert user["social_turn"] is True


def test_provider_parses_out_of_scope_response() -> None:
    http = FakeHTTP(
        {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"answer":"","language":"vi",'
                            '"scope_status":"out_of_scope","citations":[]}'
                        )
                    }
                }
            ]
        }
    )
    provider = OpenRouterProvider(
        http=http,
        api_key=SecretStr("secret"),
        endpoint="https://openrouter.example/api/v1/chat/completions",
        model="configured/model",
        timeout_seconds=10,
    )
    req = request()

    result = provider.generate(
        AIRequest(req.question, Language.VIETNAMESE, req.evidence)
    )

    assert result.scope_status is ScopeStatus.OUT_OF_SCOPE
    assert result.citations == ()


def test_provider_rejects_unknown_scope_status() -> None:
    http = FakeHTTP(
        {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"answer":"Guessing", "language":"en",'
                            '"scope_status":"anything", "citations":[]}'
                        )
                    }
                }
            ]
        }
    )
    provider = OpenRouterProvider(
        http=http,
        api_key=SecretStr("secret"),
        endpoint="https://openrouter.example/api/v1/chat/completions",
        model="configured/model",
        timeout_seconds=10,
    )

    with pytest.raises(AIProviderError):
        provider.generate(request())


def test_provider_never_exposes_api_key_in_errors_or_logs(caplog) -> None:
    secret = "never-log-this-key"
    provider = OpenRouterProvider(
        http=FakeHTTP(error=RuntimeError(f"request failed using {secret}")),
        api_key=SecretStr(secret),
        endpoint="https://openrouter.example/api/v1/chat/completions",
        model="configured/model",
        timeout_seconds=10,
    )

    with caplog.at_level(logging.ERROR), pytest.raises(AIProviderError) as captured:
        provider.generate(request())

    assert secret not in str(captured.value)
    assert secret not in caplog.text
    assert captured.value.code == "ai_provider_failed"


def test_embedder_uses_configured_openrouter_embedding_model() -> None:
    http = FakeHTTP({"data": [{"embedding": [0.1, 0.2, 0.3]}]})
    embedder = OpenRouterEmbedder(
        http=http,
        api_key=SecretStr("embedding-secret"),
        endpoint="https://openrouter.example/api/v1/embeddings",
        model="configured/embedding-model",
        dimensions=3,
        timeout_seconds=12,
    )

    result = embedder.embed("healthy living")

    url, headers, payload, timeout = http.call
    assert url.endswith("/embeddings")
    assert headers["Authorization"] == "Bearer embedding-secret"
    assert payload == {
        "model": "configured/embedding-model",
        "input": "healthy living",
        "dimensions": 3,
    }
    assert timeout == 12
    assert result == [0.1, 0.2, 0.3]


def test_embedder_rejects_wrong_vector_dimensions() -> None:
    embedder = OpenRouterEmbedder(
        http=FakeHTTP({"data": [{"embedding": [0.1]}]}),
        api_key=SecretStr("embedding-secret"),
        endpoint="https://openrouter.example/api/v1/embeddings",
        model="configured/embedding-model",
        dimensions=3,
        timeout_seconds=12,
    )

    with pytest.raises(AIProviderError) as captured:
        embedder.embed("healthy living")

    assert captured.value.code == "embedding_provider_failed"
