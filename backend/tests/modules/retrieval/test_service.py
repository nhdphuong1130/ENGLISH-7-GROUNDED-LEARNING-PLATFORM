from dataclasses import replace
from uuid import uuid4

from english7.modules.retrieval.service import (
    RetrievalCandidate,
    RetrievalService,
)


class FakeEmbedder:
    def embed(self, text: str) -> list[float]:
        assert text
        return [0.1, 0.2]


class FakeRepository:
    def __init__(self, vector, graph=()) -> None:
        self.vector = list(vector)
        self.graph = list(graph)
        self.depth = None

    def vector_search(self, query_vector, top_k):
        assert query_vector == [0.1, 0.2]
        return self.vector[:top_k]

    def expand(self, fragment_ids, max_depth):
        self.depth = max_depth
        return self.graph


def candidate(
    *,
    unit: int,
    vector_score: float,
    text: str = "verified evidence",
    page: int = 10,
    has_source: bool = True,
):
    return RetrievalCandidate(
        fragment_id=uuid4(),
        unit_number=unit,
        text=text,
        pdf_page=page + 2,
        printed_page=page,
        vector_score=vector_score,
        has_verified_source=has_source,
        hierarchy=("English 7", f"Unit {unit}", "Section", "Activity"),
    )


def service(repository, threshold=0.7):
    return RetrievalService(
        repository=repository,
        embedder=FakeEmbedder(),
        allowed_units=frozenset({1, 2}),
        top_k=5,
        min_vector_score=threshold,
        graph_depth=2,
        rrf_constant=60,
        max_context_fragments=5,
    )


def test_filters_units_and_requires_verified_source_for_graph_enrichment() -> None:
    seed = candidate(unit=1, vector_score=0.92)
    outside = candidate(unit=3, vector_score=0.99)
    neighbor = candidate(unit=1, vector_score=0.0, text="related evidence", page=11)
    unsupported = candidate(unit=1, vector_score=0.0, has_source=False)
    repository = FakeRepository([outside, seed], [neighbor, unsupported])

    context = service(repository).retrieve("healthy activities")

    assert repository.depth == 2
    assert {item.fragment_id for item in context.fragments} == {
        seed.fragment_id,
        neighbor.fragment_id,
    }
    assert all(item.unit_number in {1, 2} for item in context.fragments)


def test_low_confidence_returns_no_grounded_context() -> None:
    repository = FakeRepository([candidate(unit=1, vector_score=0.69)])

    context = service(repository).retrieve("unrelated question")

    assert context.fragments == ()
    assert context.citations == ()


def test_citations_are_deduplicated_and_ordered_by_fused_rank() -> None:
    first = candidate(unit=1, vector_score=0.95, page=10)
    duplicate_page = replace(
        candidate(unit=1, vector_score=0.90, page=10),
        pdf_page=first.pdf_page,
    )
    second_page = candidate(unit=2, vector_score=0.85, page=20)
    repository = FakeRepository([first, duplicate_page, second_page])

    context = service(repository).retrieve("hobbies and health")

    assert [(c.pdf_page, c.printed_page) for c in context.citations] == [
        (12, 10),
        (22, 20),
    ]


def test_concept_search_prioritizes_pedagogical_fragments() -> None:
    class ConceptFakeRepository(FakeRepository):
        def __init__(self, vector, concept_results):
            super().__init__(vector)
            self.concept_results = concept_results
            self.searched_keywords = None

        def concept_search(self, keywords, limit=5):
            self.searched_keywords = keywords
            return self.concept_results

    concept_frag = candidate(unit=1, vector_score=0.95, text="The Present Simple rule", page=12)
    other_frag = candidate(unit=1, vector_score=0.80, text="General hobbies", page=15)
    repository = ConceptFakeRepository(vector=[other_frag], concept_results=[concept_frag])

    context = service(repository).retrieve("thì hiện tại đơn là gì")

    assert repository.searched_keywords == ("hiện tại đơn", "present simple")
    assert context.fragments[0].fragment_id == concept_frag.fragment_id
