import re
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from english7.modules.knowledge.contracts import Embedder
from english7.modules.retrieval.reranker import (
    reciprocal_rank_fusion,
    weighted_reciprocal_rank_fusion,
)


_UNIT_SECTION_IMAGES = {
    (1, "getting started"): "/api/v1/media/image/unit1_act3_pic1.png",
    (1, "closer look 1"): "/api/v1/media/image/unit1_closerlook1_act1_webs.png",
    (1, "closer look 2"): "/api/v1/media/image/unit1_closerlook1_act4_table.png",
    (1, "communication"): "/api/v1/media/image/unit1_closerlook1_act3_practice.png",
    (1, "skills 1"): "/api/v1/media/image/unit1_act3_pic4.png",
    (1, "skills 2"): "/api/v1/media/image/unit1_closerlook1_act5_table.png",
    (1, "project"): "/api/v1/media/image/unit1_closerlook1_act3_example.png",
    (2, "getting started"): "/api/v1/media/image/unit2_gs_act3_pic1.png",
    (2, "closer look 1"): "/api/v1/media/image/unit2_closerlook1_act1_grid.png",
    (2, "skills 1"): "/api/v1/media/image/unit2_skills1_act1_pic1.png",
    (2, "project"): "/api/v1/media/image/unit2_project_banner.png",
    (3, "getting started"): "/api/v1/media/image/unit3_gs_act3_grid.png",
    (3, "closer look 1"): "/api/v1/media/image/unit3_closerlook1_act3_grid.png",
    (3, "communication"): "/api/v1/media/image/unit3_communication_poster.png",
    (3, "skills 2"): "/api/v1/media/image/unit3_skills2_act1_grid.png",
    (3, "project"): "/api/v1/media/image/unit3_project_banner.png",
    (4, "getting started"): "/api/v1/media/image/unit4_gs_act4_grid.png",
    (4, "closer look 1"): "/api/v1/media/image/unit4_closerlook1_act5_orchestra.png",
    (4, "closer look 2"): "/api/v1/media/image/unit4_closerlook2_act5_cats.png",
    (4, "communication"): "/api/v1/media/image/unit4_communication_act5_books.png",
    (4, "skills 1"): "/api/v1/media/image/unit4_skills1_act1_puppets.png",
    (4, "skills 2"): "/api/v1/media/image/unit4_skills2_act1_streetart.png",
    (4, "project"): "/api/v1/media/image/unit4_project_invitation.png",
    (5, "closer look 1"): "/api/v1/media/image/unit5_closerlook1_act1_measurements.png",
    (5, "closer look 2"): "/api/v1/media/image/unit5_closerlook2_act5_recipes.png",
    (5, "communication"): "/api/v1/media/image/unit5_communication_act2_menu.png",
    (5, "skills 1"): "/api/v1/media/image/unit5_skills1_act1_pho.png",
    (5, "skills 2"): "/api/v1/media/image/unit5_skills2_act1_family.png",
    (5, "looking back"): "/api/v1/media/image/unit5_lookingback_act2_omelette.png",
    (5, "project"): "/api/v1/media/image/unit5_project_eatinghabits.png",
    (6, "getting started"): "/api/v1/media/image/unit6_gettingstarted_act3_places.png",
    (6, "closer look 2"): "/api/v1/media/image/unit6_closerlook2_act4_pictures.png",
    (6, "communication"): "/api/v1/media/image/unit6_communication_school.png",
    (6, "skills 1"): "/api/v1/media/image/unit6_skills1_act1_quochoc.png",
    (6, "skills 2"): "/api/v1/media/image/unit6_skills2_act1_activities.png",
    (6, "looking back"): "/api/v1/media/image/unit6_lookingback_vanmieu.png",
    (6, "project"): "/api/v1/media/image/unit6_project_school.png",
    (7, "skills 1"): "/api/v1/media/image/unit7_skills1_danger.png",
    (7, "skills 2"): "/api/v1/media/image/unit7_skills2_mumbai.png",
    (7, "closer look 1"): "/api/v1/media/image/unit7_act2_road_signs.png",
    (8, "getting started"): "/api/v1/media/image/unit8_gs_posters.png",
    (8, "closer look 1"): "/api/v1/media/image/unit8_closer1_skyfall.png",
    (8, "skills 1"): "/api/v1/media/image/unit8_skills1_harry_potter.png",
    (8, "project"): "/api/v1/media/image/unit8_project_posters.png",
    (9, "getting started"): "/api/v1/media/image/unit9_act1_festivals.png",
    (9, "communication"): "/api/v1/media/image/unit9_comm_symbols.png",
    (9, "skills 1"): "/api/v1/media/image/unit9_skills1_twins.png",
    (9, "skills 2"): "/api/v1/media/image/unit9_skills2_turkey.png",
    (9, "project"): "/api/v1/media/image/unit9_project_festivals.png",
    (10, "getting started"): "/api/v1/media/image/unit10_act1_activities.png",
    (10, "closer look 1"): "/api/v1/media/image/unit10_act2_energy_types.png",
    (10, "skills 2"): "/api/v1/media/image/unit10_skills2_energy.png",
    (10, "looking back"): "/api/v1/media/image/unit10_lb_energy.png",
    (11, "closer look 1"): "/api/v1/media/image/unit11_closer1_vehicles.png",
    (11, "closer look 2"): "/api/v1/media/image/unit11_closer2_vehicles.png",
    (11, "communication"): "/api/v1/media/image/unit11_comm_vehicles.png",
    (11, "skills 1"): "/api/v1/media/image/unit11_skills1_car.png",
    (11, "looking back"): "/api/v1/media/image/unit11_lb_vehicles.png",
    (11, "project"): "/api/v1/media/image/unit11_project_transport.png",
    (12, "getting started"): "/api/v1/media/image/unit12_gs_capitals.png",
    (12, "closer look 1"): "/api/v1/media/image/unit12_closer1_pictures.png",
    (12, "communication"): "/api/v1/media/image/unit12_comm_flags.png",
    (12, "skills 2"): "/api/v1/media/image/unit12_skills2_london.png",
    (12, "looking back"): "/api/v1/media/image/unit12_lb_pictures.png",
    (12, "project"): "/api/v1/media/image/unit12_project_countries.png",
    (31, "review"): "/api/v1/media/image/review1_language_plant_trees.png",
    (61, "review"): "/api/v1/media/image/review2_speaking_act2_school.png",
    (91, "review"): "/api/v1/media/image/review3_act2_road_signs.png",
    (121, "review"): "/api/v1/media/image/review4_skills_alaska.png",
}

_UNIT_FALLBACK_IMAGES = {
    1: "/api/v1/media/image/unit1_closerlook1_act1_webs.png",
    2: "/api/v1/media/image/unit2_closerlook1_act1_grid.png",
    3: "/api/v1/media/image/unit3_closerlook1_act3_grid.png",
    4: "/api/v1/media/image/unit4_closerlook1_act5_orchestra.png",
    5: "/api/v1/media/image/unit5_closerlook1_act1_measurements.png",
    6: "/api/v1/media/image/unit6_closerlook2_act4_pictures.png",
    7: "/api/v1/media/image/unit7_act2_road_signs.png",
    8: "/api/v1/media/image/unit8_closer1_skyfall.png",
    9: "/api/v1/media/image/unit9_act1_festivals.png",
    10: "/api/v1/media/image/unit10_act2_energy_types.png",
    11: "/api/v1/media/image/unit11_closer1_vehicles.png",
    12: "/api/v1/media/image/unit12_closer1_pictures.png",
    31: "/api/v1/media/image/review1_language_plant_trees.png",
    61: "/api/v1/media/image/review2_speaking_act2_school.png",
    91: "/api/v1/media/image/review3_act2_road_signs.png",
    121: "/api/v1/media/image/review4_skills_alaska.png",
}


def resolve_citation_image(fragment) -> str | None:
    text = getattr(fragment, "text", "") or ""
    md_match = re.search(r"!\[.*?\]\((/api/v1/media/image[s]?/[^\)]+)\)", text)
    if md_match:
        return md_match.group(1)
    tag_match = re.search(r"\[image:(?:images/)?([^\]]+)\]", text)
    if tag_match:
        return f"/api/v1/media/image/{tag_match.group(1)}"

    unit_num = getattr(fragment, "unit_number", None)
    hierarchy = getattr(fragment, "hierarchy", ()) or ()
    sec_title = (hierarchy[2] if len(hierarchy) > 2 else "").lower()

    if unit_num is not None:
        for (u, kw), img_path in _UNIT_SECTION_IMAGES.items():
            if u == unit_num and kw in sec_title:
                return img_path
        if unit_num in _UNIT_FALLBACK_IMAGES:
            return _UNIT_FALLBACK_IMAGES[unit_num]

    return None


@dataclass(frozen=True, slots=True)
class RetrievalCandidate:
    fragment_id: UUID
    unit_number: int
    text: str
    pdf_page: int
    printed_page: int | None
    vector_score: float
    has_verified_source: bool
    hierarchy: tuple[str, str, str, str]


@dataclass(frozen=True, slots=True)
class Citation:
    fragment_id: UUID
    pdf_page: int
    printed_page: int | None
    image_url: str | None = None


@dataclass(frozen=True, slots=True)
class GroundedContext:
    fragments: tuple[RetrievalCandidate, ...]
    citations: tuple[Citation, ...]


class RetrievalRepository(Protocol):
    def vector_search(
        self, query_vector: list[float], top_k: int
    ) -> list[RetrievalCandidate]: ...

    def expand(
        self, fragment_ids: tuple[UUID, ...], max_depth: int
    ) -> list[RetrievalCandidate]: ...


class RetrievalService:
    def __init__(
        self,
        *,
        repository: RetrievalRepository,
        embedder: Embedder,
        allowed_units: frozenset[int],
        top_k: int,
        min_vector_score: float,
        graph_depth: int,
        rrf_constant: int,
        max_context_fragments: int,
    ) -> None:
        if not allowed_units:
            raise ValueError("At least one allowed unit is required")
        if top_k <= 0 or graph_depth <= 0 or max_context_fragments <= 0:
            raise ValueError("Retrieval limits must be positive")
        self._repository = repository
        self._embedder = embedder
        self._allowed_units = allowed_units
        self._top_k = top_k
        self._threshold = min_vector_score
        self._graph_depth = graph_depth
        self._rrf_constant = rrf_constant
        self._max_context = max_context_fragments

    def _allowed(self, item: RetrievalCandidate) -> bool:
        return item.unit_number in self._allowed_units and item.has_verified_source

    def retrieve(self, query: str) -> GroundedContext:
        vector = [
            item
            for item in self._repository.vector_search(
                self._embedder.embed(query), self._top_k
            )
            if self._allowed(item) and item.vector_score >= self._threshold
        ]
        if not vector:
            return GroundedContext((), ())

        if hasattr(self._repository, "weighted_graph_search"):
            graph_results = [
                (item, weight)
                for item, weight in self._repository.weighted_graph_search(
                    tuple(item.fragment_id for item in vector), self._graph_depth
                )
                if self._allowed(item)
            ]
            by_id = {str(item.fragment_id): item for item in vector}
            for item, _ in graph_results:
                by_id[str(item.fragment_id)] = item
            fused = weighted_reciprocal_rank_fusion(
                vector_ids=tuple(str(item.fragment_id) for item in vector),
                graph_scored_ids=tuple(
                    (str(item.fragment_id), weight) for item, weight in graph_results
                ),
                rank_constant=self._rrf_constant,
            )
        else:
            graph = [
                item
                for item in self._repository.expand(
                    tuple(item.fragment_id for item in vector), self._graph_depth
                )
                if self._allowed(item)
            ]
            by_id = {str(item.fragment_id): item for item in (*vector, *graph)}
            fused = reciprocal_rank_fusion(
                vector_ids=tuple(str(item.fragment_id) for item in vector),
                graph_ids=tuple(str(item.fragment_id) for item in graph),
                rank_constant=self._rrf_constant,
            )

        fragments = tuple(
            by_id[item.item_id] for item in fused[: self._max_context]
        )
        seen_pages: set[tuple[int, int | None]] = set()
        citations: list[Citation] = []
        for fragment in fragments:
            page_key = (fragment.pdf_page, fragment.printed_page)
            if page_key in seen_pages:
                continue
            seen_pages.add(page_key)
            citations.append(
                Citation(
                    fragment.fragment_id,
                    fragment.pdf_page,
                    fragment.printed_page,
                    resolve_citation_image(fragment),
                )
            )
        return GroundedContext(fragments, tuple(citations))
