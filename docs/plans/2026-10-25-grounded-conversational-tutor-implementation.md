# Grounded Conversational Tutor Implementation Plan

**Goal:** Build ownership-scoped, bounded, persistent Tutor conversations with natural learner-directed dialogue and strict English 7 textbook grounding.

**Architecture:** Add a conversation aggregate and SQL repository around the existing `TutorChat` rows, then pass bounded history through a Tutor-specific AI request/prompt without ever treating history as evidence. Expose owner-scoped REST endpoints and move Flutter Tutor state from local-only messages to server-backed conversations. Preserve the existing retrieval, citation-image, admin-history, image-upload, and bilingual behavior already present in the dirty working tree.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, SQL Server, OpenRouter JSON chat completions, Neo4j retrieval, Pytest, Flutter/Dart, flutter_secure_storage.

---

### Task 1: Add the conversation persistence model and additive migration

**Files:**
- Modify: `backend/src/english7/db/models.py`
- Modify: `backend/alembic/versions/0008_tutor_chats.py`
- Create: `backend/alembic/versions/0009_tutor_conversations.py`
- Modify: `backend/tests/integration/test_migrations.py`
- Create: `backend/tests/modules/tutor/test_conversation_models.py`

**Step 1: Write the failing model test**

Add tests that instantiate `TutorConversation` with an owner, title, language,
expiry, and optional addressing preference, and `TutorChat` with a conversation
ID and sequence number. Assert the relationship and uniqueness/index metadata are
present.

```python
def test_tutor_exchange_belongs_to_ordered_conversation():
    conversation_id = uuid4()
    exchange = TutorChat(
        user_id=uuid4(), conversation_id=conversation_id, sequence_number=1,
        question="Why?", answer="Because...", language="en", citations=[]
    )
    assert exchange.conversation_id == conversation_id
    assert exchange.sequence_number == 1
```

**Step 2: Run the test to verify RED**

Run: `cd backend && uv run pytest tests/modules/tutor/test_conversation_models.py -q`

Expected: FAIL because `TutorConversation`, `conversation_id`, and
`sequence_number` do not exist.

**Step 3: Implement the model and migration**

Create `TutorConversation` with UUID/timestamps, owner FK, bounded title,
language, optional addressing preference, and expiry. Add an owner/update index.
Extend `TutorChat` with nullable migration-safe `conversation_id`, required at the
ORM boundary for new rows, and `sequence_number`. The migration creates one
legacy conversation per existing chat, backfills both columns, then makes them
non-null and adds the FK/index/unique constraint. Preserve `0008` as the existing
table migration and make `0009` depend on it.

**Step 4: Verify GREEN**

Run: `cd backend && uv run pytest tests/modules/tutor/test_conversation_models.py tests/integration/test_migrations.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/english7/db/models.py backend/alembic/versions/0008_tutor_chats.py \
  backend/alembic/versions/0009_tutor_conversations.py \
  backend/tests/modules/tutor/test_conversation_models.py \
  backend/tests/integration/test_migrations.py
git commit -m "feat(tutor): add persistent conversation model"
```

### Task 2: Implement owner-scoped conversation repository and limits

**Files:**
- Create: `backend/src/english7/modules/tutor/conversations.py`
- Create: `backend/tests/modules/tutor/test_conversations.py`

**Step 1: Write failing repository/service tests**

Use an in-memory SQLite session for repository behavior and a fixed UTC clock.
Cover:

- create/list/get/delete only for the owner;
- title normalization and neutral addressing default;
- removal of conversations expired after 90 days;
- automatic removal of the oldest conversation when creating number 21;
- rejection with `conversation_full` before writing exchange 51;
- history returns only the six latest completed exchanges in ascending order;
- failed generation does not append or consume a sequence number.

```python
def test_context_contains_only_six_latest_exchanges(repository, owner):
    conversation = repository.create(owner, Language.VIETNAMESE, "Unit 1")
    for number in range(1, 9):
        repository.append_exchange(conversation.id, owner, f"q{number}", f"a{number}", [])
    assert [x.sequence_number for x in repository.recent_exchanges(
        conversation.id, owner, limit=6
    )] == [3, 4, 5, 6, 7, 8]
```

**Step 2: Verify RED**

Run: `cd backend && uv run pytest tests/modules/tutor/test_conversations.py -q`

Expected: FAIL because the repository/service does not exist.

**Step 3: Implement minimal repository and policy service**

Define immutable summaries/exchanges, a `ConversationRepository` protocol, and
`SQLAlchemyConversationRepository`. Inject clock and limits with defaults 20,
50, 6, and 90 days. Cleanup and oldest eviction occur in transactions. All
queries include `user_id`; foreign/missing IDs return `None` and never reveal
existence.

**Step 4: Verify GREEN**

Run: `cd backend && uv run pytest tests/modules/tutor/test_conversations.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/english7/modules/tutor/conversations.py \
  backend/tests/modules/tutor/test_conversations.py
git commit -m "feat(tutor): enforce conversation ownership and limits"
```

### Task 3: Introduce bounded conversational AI contracts and pedagogy prompt

**Files:**
- Modify: `backend/src/english7/modules/ai/contracts.py`
- Modify: `backend/src/english7/modules/ai/openrouter.py`
- Modify: `backend/tests/modules/ai/test_openrouter.py`

**Step 1: Write failing prompt-contract tests**

Extend `AIRequest` with `history`, `addressing_preference`, and task metadata
using defaults so quiz/test callers remain compatible. Add an immutable
`ConversationTurn`. Extend `AIResponse` with `scope_status` defaulting to grounded.
Assert generated messages:

- describe a warm English 7 tutor/lecturer rather than a terse responder;
- separate untrusted history, current question, and verified evidence;
- state that history is context and never evidence;
- require age-appropriate step-by-step help and optional comprehension checks;
- follow explicit addressing preference and otherwise use neutral language;
- prohibit outside facts, prompt disclosure, and role/scope override;
- require structured `scope_status` and supplied citation IDs.

```python
def test_tutor_prompt_separates_history_from_verified_evidence():
    messages = OpenRouterProvider._messages(request_with_history())
    assert "never evidence" in messages[0]["content"].lower()
    user = json.loads(messages[1]["content"])
    assert user["conversation_history"][0]["learner"] == "Why?"
    assert user["verified_textbook_evidence"][0]["fragment_id"]
```

**Step 2: Verify RED**

Run: `cd backend && uv run pytest tests/modules/ai/test_openrouter.py -q`

Expected: FAIL on missing history/scope fields and prompt rules.

**Step 3: Implement prompt builder and response parsing**

Keep HTTP transport generic. Add `_tutor_system_prompt` and structured user JSON.
Parse only `grounded` or `out_of_scope`; unknown values become invalid provider
output. Do not derive factual evidence from history. Preserve API-key redaction.

**Step 4: Verify GREEN**

Run: `cd backend && uv run pytest tests/modules/ai/test_openrouter.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/english7/modules/ai/contracts.py \
  backend/src/english7/modules/ai/openrouter.py \
  backend/tests/modules/ai/test_openrouter.py
git commit -m "feat(tutor): add grounded conversational prompt contract"
```

### Task 4: Connect conversations, retrieval, validation, and REST endpoints

**Files:**
- Modify: `backend/src/english7/modules/tutor/service.py`
- Modify: `backend/src/english7/modules/tutor/router.py`
- Modify: `backend/src/english7/bootstrap.py`
- Modify: `backend/tests/modules/tutor/test_service.py`
- Modify: `backend/tests/api/test_tutor.py`
- Modify: `backend/tests/test_bootstrap.py`

**Step 1: Write failing service and API tests**

Cover current-question retrieval, six-turn AI context, history excluded from
`Evidence`, explicit style persistence, deterministic out-of-scope refusal,
grounded citation validation, owner isolation, create/list/detail/delete/ask, and
temporary `/tutor/ask` compatibility.

**Step 2: Verify RED**

Run: `cd backend && uv run pytest tests/modules/tutor/test_service.py tests/api/test_tutor.py tests/test_bootstrap.py -q`

Expected: FAIL on missing conversation APIs and contextual request.

**Step 3: Implement minimal integration**

Move chat persistence out of router `_record_chat` into the conversation service
transaction. Add Pydantic request/response models, owner dependency checks, and
friendly error codes. Configure the SQL repository in `bootstrap.py`. Keep image
question ownership/status checks and citation images intact.

**Step 4: Verify GREEN**

Run: `cd backend && uv run pytest tests/modules/tutor tests/api/test_tutor.py tests/test_bootstrap.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/english7/modules/tutor backend/src/english7/bootstrap.py \
  backend/tests/modules/tutor backend/tests/api/test_tutor.py backend/tests/test_bootstrap.py
git commit -m "feat(tutor): expose grounded conversation APIs"
```

### Task 5: Add Flutter conversation contracts and API client

**Files:**
- Modify: `mobile/lib/app/student_api.dart`
- Modify: `mobile/lib/app/api_student_api.dart`
- Modify: `mobile/test/app/api_learning_test.dart`

**Step 1: Write failing API parsing tests**

Add `TutorConversationSummary`, `TutorConversation`, and `TutorExchange`; extend
`StudentApi` with create/list/load/delete/ask-in-conversation. Assert paths,
ownership-safe error mapping, citations, `conversation_full`, and expired chat
fallback.

**Step 2: Verify RED**

Run: `cd mobile && flutter test test/app/api_learning_test.dart`

Expected: FAIL on missing types/methods.

**Step 3: Implement client contracts**

Parse ISO timestamps and ordered exchanges. Keep image upload polling and submit
the resulting upload ID to `/{conversationId}/ask`. Preserve the old method only
as a compatibility wrapper during migration.

**Step 4: Verify GREEN and commit**

Run: `cd mobile && flutter test test/app/api_learning_test.dart`

```bash
git add mobile/lib/app/student_api.dart mobile/lib/app/api_student_api.dart \
  mobile/test/app/api_learning_test.dart
git commit -m "feat(mobile): add tutor conversation API client"
```

### Task 6: Build mobile history and bounded conversation UX

**Files:**
- Modify: `mobile/lib/features/tutor/tutor_screen.dart`
- Modify: `mobile/lib/app/english7_app.dart`
- Modify: `mobile/test/features/tutor_flow_test.dart`

**Step 1: Write failing widget tests**

Cover history opening, newest-first summaries, restoring exchanges, new-chat
creation, deletion confirmation, continuing an old chat, full-chat CTA, and
expired-chat fallback. Assert citations remain visible and grounded.

**Step 2: Verify RED**

Run: `cd mobile && flutter test test/features/tutor_flow_test.dart`

Expected: FAIL because UI is local-only.

**Step 3: Implement minimal UI**

Load conversation summaries lazily when Tutor opens. Use a modal bottom sheet for
history, maintain the selected server ID, and render server exchanges through the
existing message/citation widgets. `Đoạn chat mới` creates server state. Do not
store authoritative answer content in secure storage.

**Step 4: Verify GREEN and commit**

Run: `cd mobile && flutter test test/features/tutor_flow_test.dart`

```bash
git add mobile/lib/features/tutor/tutor_screen.dart \
  mobile/lib/app/english7_app.dart mobile/test/features/tutor_flow_test.dart
git commit -m "feat(mobile): add bounded tutor chat history"
```

### Task 7: Full verification, documentation, and safe deployment

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `README.md`
- Modify: `.env.example` only if limits become configurable

**Step 1: Run focused and full verification**

Run:

```bash
make test
make analyze
```

Expected: all backend/mobile tests pass and Flutter reports no issues.

**Step 2: Inspect migration and diff**

Run:

```bash
git diff --check
git status --short
```

Confirm unrelated pre-existing changes remain preserved.

**Step 3: Update documentation and commit**

Document conversation behavior, limits, retention, and strict grounding.

```bash
git add CHANGELOG.md README.md .env.example
git commit -m "docs: document conversational tutor limits"
```

**Step 4: Deploy without deleting volumes**

Copy only committed/source changes to `/home/ubuntu/DoAN_LTDD`, run
`alembic upgrade head`, rebuild/recreate API with production and speech overlays,
and build the updated mobile artifact. Never run `docker compose down -v`.

**Step 5: Production smoke verification**

Verify API health, migration head, ownership isolation, a grounded follow-up with
`[Unit X, Page Y]`, an out-of-scope refusal, history reopening, and all container
health. Do not log credentials, JWTs, or OpenRouter keys.
