import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from neo4j import Driver

from english7.modules.knowledge.contracts import IndexedFragment, KnowledgeProjection
from english7.modules.knowledge.curriculum_ontology import (
    PedagogicalGrammarRule,
    PedagogicalPronunciation,
    PedagogicalTopic,
    PedagogicalVocabulary,
)
from english7.modules.knowledge.domain import AssertionType
from english7.modules.knowledge.embedding import EmbeddingIdentity
from english7.modules.retrieval.service import RetrievalCandidate

_CYPHER_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


class Neo4jKnowledgeRepository:
    def __init__(
        self,
        driver: Driver,
        *,
        vector_index_name: str,
        embedding_dimensions: int,
        graph_result_limit: int,
        database: str | None = None,
    ) -> None:
        if not _CYPHER_IDENTIFIER.fullmatch(vector_index_name):
            raise ValueError("Vector index name is not a safe Cypher identifier")
        if embedding_dimensions <= 0 or graph_result_limit <= 0:
            raise ValueError("Neo4j retrieval limits must be positive")
        self._driver = driver
        self._index_name = vector_index_name
        self._dimensions = embedding_dimensions
        self._graph_result_limit = graph_result_limit
        self._database = database

    def ensure_schema(self) -> None:
        constraints = [
            "CREATE CONSTRAINT textbook_title IF NOT EXISTS FOR (tb:Textbook) REQUIRE tb.title IS UNIQUE",
            "CREATE CONSTRAINT unit_number IF NOT EXISTS FOR (u:Unit) REQUIRE u.number IS UNIQUE",
            "CREATE CONSTRAINT section_sql_id IF NOT EXISTS FOR (s:Section) REQUIRE s.sql_id IS UNIQUE",
            "CREATE CONSTRAINT activity_sql_id IF NOT EXISTS FOR (a:Activity) REQUIRE a.sql_id IS UNIQUE",
            "CREATE CONSTRAINT source_fragment_sql_id IF NOT EXISTS FOR (fragment:SourceFragment) REQUIRE fragment.sql_id IS UNIQUE",
            "CREATE CONSTRAINT knowledge_concept_id IF NOT EXISTS FOR (concept:KnowledgeConcept) REQUIRE concept.id IS UNIQUE",
        ]
        indexes = [
            (
                f"CREATE VECTOR INDEX {self._index_name} IF NOT EXISTS "
                "FOR (fragment:SourceFragment) ON (fragment.embedding) "
                "OPTIONS {indexConfig: {"
                f"`vector.dimensions`: {self._dimensions}, "
                "`vector.similarity_function`: 'cosine'}}"
            ),
            (
                "CREATE VECTOR INDEX knowledge_concept_embedding IF NOT EXISTS "
                "FOR (concept:KnowledgeConcept) ON (concept.embedding) "
                "OPTIONS {indexConfig: {"
                f"`vector.dimensions`: {self._dimensions}, "
                "`vector.similarity_function`: 'cosine'}}"
            ),
        ]
        with self._driver.session(database=self._database) as session:
            for constraint in constraints:
                session.run(constraint).consume()
            for vector_index in indexes:
                session.run(vector_index).consume()

    def upsert_fragment(self, fragment: IndexedFragment) -> None:
        if len(fragment.embedding) != self._dimensions:
            raise ValueError("Embedding dimensions do not match the vector index")
        query = """
        MERGE (textbook:Textbook {sql_id: $textbook_id})
        SET textbook.title = $textbook_title
        MERGE (unit:Unit {sql_id: $unit_id})
        SET unit.number = $unit_number, unit.title = $unit_title
        MERGE (section:Section {sql_id: $section_id})
        SET section.title = $section_title
        MERGE (activity:Activity {sql_id: $activity_id})
        MERGE (fragment:SourceFragment {sql_id: $fragment_id})
        SET fragment.text = $text,
            fragment.pdf_page = $pdf_page,
            fragment.printed_page = $printed_page,
            fragment.unit_number = $unit_number,
            fragment.embedding = $embedding,
            fragment.verified = true,
            fragment.hierarchy = $hierarchy
        MERGE (textbook)-[:HAS_UNIT]->(unit)
        MERGE (unit)-[:HAS_SECTION]->(section)
        MERGE (section)-[:HAS_ACTIVITY]->(activity)
        MERGE (activity)-[:HAS_SOURCE]->(fragment)
        """
        parameters = {
            "textbook_id": str(fragment.textbook_id),
            "textbook_title": fragment.hierarchy[0],
            "unit_id": str(fragment.unit_id),
            "unit_number": fragment.unit_number,
            "unit_title": fragment.hierarchy[1],
            "section_id": str(fragment.section_id),
            "section_title": fragment.hierarchy[2],
            "activity_id": str(fragment.activity_id),
            "fragment_id": str(fragment.fragment_id),
            "text": fragment.text,
            "pdf_page": fragment.pdf_page,
            "printed_page": fragment.printed_page,
            "embedding": fragment.embedding,
            "hierarchy": list(fragment.hierarchy),
        }
        with self._driver.session(database=self._database) as session:
            session.run(query, parameters).consume()

    @staticmethod
    def _candidate(record) -> RetrievalCandidate:
        node = record["fragment"]
        return RetrievalCandidate(
            fragment_id=UUID(node["sql_id"]),
            unit_number=node["unit_number"],
            text=node["text"],
            pdf_page=node["pdf_page"],
            printed_page=node.get("printed_page"),
            vector_score=float(record.get("score", 0.0)),
            has_verified_source=bool(node.get("verified", False)),
            hierarchy=tuple(node["hierarchy"]),
        )

    def vector_search(
        self, query_vector: list[float], top_k: int
    ) -> list[RetrievalCandidate]:
        query = """
        CALL db.index.vector.queryNodes($index_name, $top_k, $query_vector)
        YIELD node AS fragment, score
        WHERE fragment.verified = true
        RETURN fragment, score
        ORDER BY score DESC, fragment.sql_id
        """
        with self._driver.session(database=self._database) as session:
            records = session.run(
                query,
                index_name=self._index_name,
                top_k=top_k,
                query_vector=query_vector,
            )
            return [self._candidate(record) for record in records]

    def expand(
        self, fragment_ids: tuple[UUID, ...], max_depth: int
    ) -> list[RetrievalCandidate]:
        if max_depth <= 0:
            raise ValueError("Graph depth must be positive")
        depth = min(max_depth, 8)
        norm_ids = [str(fid).lower() for fid in fragment_ids]
        query = f"""
        MATCH (seed:SourceFragment)
        WHERE toLower(seed.sql_id) IN $fragment_ids
        MATCH path = (seed)-[*1..{depth}]-(neighbor:SourceFragment)
        WHERE neighbor.verified = true AND NOT toLower(neighbor.sql_id) IN $fragment_ids
        WITH neighbor, min(length(path)) AS distance
        RETURN neighbor AS fragment, 0.0 AS score
        ORDER BY distance, fragment.sql_id
        LIMIT $result_limit
        """
        with self._driver.session(database=self._database) as session:
            records = session.run(
                query,
                fragment_ids=norm_ids,
                result_limit=self._graph_result_limit,
            )
            return [self._candidate(record) for record in records]

    def upsert_topic(self, topic: PedagogicalTopic, embedding: list[float]) -> None:
        query = """
        MERGE (t:Topic:KnowledgeConcept {id: $id})
        SET t.unit_number = $unit_number,
            t.name = $name,
            t.description = $description,
            t.embedding = $embedding
        """
        params = {
            "id": topic.id,
            "unit_number": topic.unit_number,
            "name": topic.name,
            "description": topic.description,
            "embedding": embedding,
        }
        with self._driver.session(database=self._database) as session:
            session.run(query, params).consume()

    def upsert_grammar_rule(self, rule: PedagogicalGrammarRule, embedding: list[float]) -> None:
        query = """
        MERGE (g:GrammarRule:KnowledgeConcept {id: $id})
        SET g.unit_number = $unit_number,
            g.name = $name,
            g.formula = $formula,
            g.explanation_vi = $explanation_vi,
            g.examples = $examples,
            g.embedding = $embedding
        """
        params = {
            "id": rule.id,
            "unit_number": rule.unit_number,
            "name": rule.name,
            "formula": rule.formula,
            "explanation_vi": rule.explanation_vi,
            "examples": rule.examples,
            "embedding": embedding,
        }
        with self._driver.session(database=self._database) as session:
            session.run(query, params).consume()

    def upsert_vocabulary(self, vocab: PedagogicalVocabulary, embedding: list[float]) -> None:
        query = """
        MERGE (v:Vocabulary:KnowledgeConcept {id: $id})
        SET v.unit_number = $unit_number,
            v.word = $word,
            v.pos = $pos,
            v.ipa = $ipa,
            v.meaning_vi = $meaning_vi,
            v.example = $example,
            v.embedding = $embedding
        """
        params = {
            "id": vocab.id,
            "unit_number": vocab.unit_number,
            "word": vocab.word,
            "pos": vocab.pos,
            "ipa": vocab.ipa,
            "meaning_vi": vocab.meaning_vi,
            "example": vocab.example,
            "embedding": embedding,
        }
        with self._driver.session(database=self._database) as session:
            session.run(query, params).consume()

    def upsert_pronunciation(self, pron: PedagogicalPronunciation, embedding: list[float]) -> None:
        query = """
        MERGE (p:PronunciationSound:KnowledgeConcept {id: $id})
        SET p.unit_number = $unit_number,
            p.symbol = $symbol,
            p.description = $description,
            p.sample_words = $sample_words,
            p.embedding = $embedding
        """
        params = {
            "id": pron.id,
            "unit_number": pron.unit_number,
            "symbol": pron.symbol,
            "description": pron.description,
            "sample_words": pron.sample_words,
            "embedding": embedding,
        }
        with self._driver.session(database=self._database) as session:
            session.run(query, params).consume()

    def upsert_weighted_relationship(
        self,
        source_id: str,
        source_label: str,
        target_id: str,
        target_label: str,
        rel_type: str,
        weight: float,
    ) -> None:
        src_id_prop = "sql_id" if source_label in ("SourceFragment", "Activity", "Section", "Unit", "Textbook") else "id"
        tgt_id_prop = "sql_id" if target_label in ("SourceFragment", "Activity", "Section", "Unit", "Textbook") else "id"
        query = f"""
        MATCH (s:{source_label} {{{src_id_prop}: $source_id}})
        MATCH (t:{target_label} {{{tgt_id_prop}: $target_id}})
        MERGE (s)-[r:{rel_type}]->(t)
        SET r.weight = $weight
        """
        params = {
            "source_id": source_id,
            "target_id": target_id,
            "weight": weight,
        }
        with self._driver.session(database=self._database) as session:
            session.run(query, params).consume()

    def weighted_graph_search(
        self, seed_fragment_ids: tuple[UUID, ...], max_depth: int = 2
    ) -> list[tuple[RetrievalCandidate, float]]:
        depth = min(max(max_depth, 1), 4)
        norm_ids = [str(fid).lower() for fid in seed_fragment_ids]
        query = f"""
        MATCH (seed:SourceFragment)
        WHERE toLower(seed.sql_id) IN $fragment_ids
        MATCH path = (seed)-[r:TEACHES|EXPLAINS|PRACTICES|APPEARS_IN|PREREQUISITE_OF*1..{depth}]-(neighbor:SourceFragment)
        WHERE neighbor.verified = true AND NOT toLower(neighbor.sql_id) IN $fragment_ids
        WITH neighbor,
             reduce(w = 1.0, rel IN relationships(path) | w * coalesce(rel.weight,
                case type(rel)
                    when 'TEACHES' then 0.95
                    when 'EXPLAINS' then 0.85
                    when 'PRACTICES' then 0.75
                    when 'PREREQUISITE_OF' then 0.7
                    when 'APPEARS_IN' then 0.25
                    else 0.5
                end
             )) AS path_weight,
             length(path) AS dist
        WITH neighbor, max(path_weight * (0.8 ^ (dist - 1))) AS score
        RETURN neighbor AS fragment, score
        ORDER BY score DESC, fragment.sql_id
        LIMIT $result_limit
        """
        with self._driver.session(database=self._database) as session:
            records = session.run(
                query,
                fragment_ids=norm_ids,
                result_limit=self._graph_result_limit,
            )
            return [
                (self._candidate(record), float(record.get("score", 0.5)))
                for record in records
            ]

    def concept_search(
        self, keywords: tuple[str, ...], limit: int = 6
    ) -> list[RetrievalCandidate]:
        if not keywords:
            return []
        query = """
        UNWIND $keywords AS kw
        MATCH (c:KnowledgeConcept)
        WHERE toLower(c.name) CONTAINS toLower(kw)
           OR toLower(coalesce(c.explanation_vi, '')) CONTAINS toLower(kw)
        MATCH (f:SourceFragment)-[r:TEACHES|EXPLAINS|PRACTICES]-(c)
        WHERE f.verified = true
        WITH f, max(case type(r) when 'TEACHES' then 0.95 when 'EXPLAINS' then 0.85 else 0.75 end) as score
        RETURN f AS fragment, score
        ORDER BY score DESC, f.sql_id
        LIMIT $limit
        """
        with self._driver.session(database=self._database) as session:
            records = session.run(
                query,
                keywords=list(keywords),
                limit=limit,
            )
            return [self._candidate(record) for record in records]


@dataclass(frozen=True, slots=True)
class BuildIdentifiers:
    suffix: str
    fragment_label: str
    concept_label: str
    fragment_index: str
    concept_index: str

    @classmethod
    def from_build_id(cls, build_id: UUID) -> "BuildIdentifiers":
        suffix = build_id.hex
        return cls(
            suffix,
            f"SourceFragmentBuild_{suffix}",
            f"KnowledgeConceptBuild_{suffix}",
            f"fragment_embedding_{suffix}",
            f"concept_embedding_{suffix}",
        )


@dataclass(frozen=True, slots=True)
class ProjectionEmbeddings:
    fragments: dict[UUID, list[float]]
    concepts: dict[UUID, list[float]]
    fragment_input_hashes: dict[UUID, str] = field(default_factory=dict)
    concept_input_hashes: dict[UUID, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Neo4jBuildReport:
    counts: dict[str, int]
    relationship_counts: dict[str, int]
    orphan_counts: dict[str, int]
    dimension_mismatches: int
    non_verified: int
    duplicate_ids: int
    index_states: dict[str, str]
    failures: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.failures

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def require_valid(self) -> None:
        if self.failures:
            raise ValueError("Graph build validation failed: " + ", ".join(self.failures))


_RELATIONSHIP_TYPES = {
    item.value: item.value.upper() for item in AssertionType
}


class VersionedNeo4jRepository:
    def __init__(
        self,
        driver: Driver,
        *,
        database: str | None = None,
        batch_size: int = 200,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("Neo4j batch size must be positive")
        self._driver = driver
        self._database = database
        self._batch_size = batch_size

    @staticmethod
    def _consume(tx, query: str, parameters: dict) -> None:
        tx.run(query, parameters).consume()

    def _run(self, query: str, parameters: dict) -> None:
        with self._driver.session(database=self._database) as session:
            session.execute_write(self._consume, query, parameters)

    def _run_rows(self, query: str, rows: list[dict], build_id: UUID) -> None:
        for start in range(0, len(rows), self._batch_size):
            self._run(
                query,
                {
                    "build_id": str(build_id),
                    "rows": rows[start : start + self._batch_size],
                },
            )

    def prepare_build(self, build_id: UUID, identity: EmbeddingIdentity) -> None:
        constraints = {
            "textbook_build_identity": "Textbook",
            "unit_build_identity": "Unit",
            "section_build_identity": "Section",
            "activity_build_identity": "Activity",
            "fragment_build_identity": "SourceFragment",
            "concept_build_identity": "KnowledgeConcept",
        }
        with self._driver.session(database=self._database) as session:
            for name, label in constraints.items():
                session.run(
                    f"CREATE CONSTRAINT {name} IF NOT EXISTS "
                    f"FOR (node:{label}) REQUIRE (node.sql_id, node.build_id) IS UNIQUE"
                ).consume()

    def ensure_indexes(self, build_id: UUID, identity: EmbeddingIdentity) -> None:
        names = BuildIdentifiers.from_build_id(build_id)
        statements = (
            (
                names.fragment_index,
                names.fragment_label,
            ),
            (
                names.concept_index,
                names.concept_label,
            ),
        )
        with self._driver.session(database=self._database) as session:
            for index_name, label in statements:
                session.run(
                    f"CREATE VECTOR INDEX {index_name} IF NOT EXISTS "
                    f"FOR (node:{label}) ON (node.embedding) "
                    "OPTIONS {indexConfig: {"
                    f"`vector.dimensions`: {identity.dimensions}, "
                    "`vector.similarity_function`: 'cosine'}}"
                ).consume()

    @staticmethod
    def _properties(value: Any) -> dict:
        properties = asdict(value)
        return {
            key: (
                str(item)
                if isinstance(item, (UUID, datetime))
                else item
            )
            for key, item in properties.items()
            if item is not None
        }

    def write_projection(
        self,
        build_id: UUID,
        projection: KnowledgeProjection,
        embeddings: ProjectionEmbeddings,
    ) -> None:
        fragment_ids = {item.id for item in projection.fragments}
        concept_ids = {item.id for item in projection.concepts}
        if set(embeddings.fragments) != fragment_ids:
            raise ValueError("Fragment embeddings do not match projection")
        if set(embeddings.concepts) != concept_ids:
            raise ValueError("Concept embeddings do not match projection")
        names = BuildIdentifiers.from_build_id(build_id)

        self._run(
            "MERGE (build:GraphBuild {build_id: $build_id}) "
            "SET build.ontology_version = $ontology_version, "
            "build.source_checksum = $source_checksum",
            {
                "build_id": str(build_id),
                "ontology_version": projection.ontology_version,
                "source_checksum": projection.source_checksum,
            },
        )
        for label, nodes in (
            ("Textbook", projection.textbooks),
            ("Unit", projection.units),
            ("Section", projection.sections),
            ("Activity", projection.activities),
        ):
            self._run_rows(
                f"UNWIND $rows AS row "
                f"MERGE (node:{label} {{sql_id: row.sql_id, build_id: $build_id}}) "
                "SET node += row.properties",
                [
                    {"sql_id": str(item.id), "properties": item.properties}
                    for item in nodes
                ],
                build_id,
            )

        fragment_rows = [
            {
                "sql_id": str(item.id),
                "textbook_id": str(item.textbook_id),
                "unit_id": str(item.unit_id),
                "section_id": str(item.section_id),
                "activity_id": str(item.activity_id),
                "text": item.text,
                "pdf_page": item.pdf_page,
                "printed_page": item.printed_page,
                "properties": item.properties,
                "embedding": embeddings.fragments[item.id],
                "embedding_input_hash": embeddings.fragment_input_hashes.get(item.id),
            }
            for item in projection.fragments
        ]
        self._run_rows(
            f"UNWIND $rows AS row "
            f"MERGE (node:SourceFragment:{names.fragment_label} "
            "{sql_id: row.sql_id, build_id: $build_id}) "
            "SET node.text = row.text, node.pdf_page = row.pdf_page, "
            "node.printed_page = row.printed_page, node.verified = true, "
            "node.embedding = row.embedding, "
            "node.embedding_input_hash = row.embedding_input_hash, "
            "node += row.properties",
            fragment_rows,
            build_id,
        )
        concept_rows = [
            {
                "sql_id": str(item.id),
                "concept_type": item.concept_type,
                "canonical_name": item.canonical_name,
                "concept_text": item.concept_text,
                "properties": item.properties,
                "embedding": embeddings.concepts[item.id],
                "embedding_input_hash": embeddings.concept_input_hashes.get(item.id),
            }
            for item in projection.concepts
        ]
        self._run_rows(
            f"UNWIND $rows AS row "
            f"MERGE (node:KnowledgeConcept:{names.concept_label} "
            "{sql_id: row.sql_id, build_id: $build_id}) "
            "SET node.concept_type = row.concept_type, "
            "node.canonical_name = row.canonical_name, "
            "node.concept_text = row.concept_text, node.verified = true, "
            "node.embedding = row.embedding, "
            "node.embedding_input_hash = row.embedding_input_hash, "
            "node += row.properties",
            concept_rows,
            build_id,
        )

        hierarchy_queries = (
            (
                "MATCH (parent:Textbook {sql_id: row.parent_id, build_id: $build_id}) "
                "MATCH (child:Unit {sql_id: row.child_id, build_id: $build_id}) "
                "MERGE (parent)-[:HAS_UNIT {build_id: $build_id}]->(child)",
                [
                    {"parent_id": item.properties["textbook_id"], "child_id": str(item.id)}
                    for item in projection.units
                ],
            ),
            (
                "MATCH (parent:Unit {sql_id: row.parent_id, build_id: $build_id}) "
                "MATCH (child:Section {sql_id: row.child_id, build_id: $build_id}) "
                "MERGE (parent)-[:HAS_SECTION {build_id: $build_id}]->(child)",
                [
                    {"parent_id": item.properties["unit_id"], "child_id": str(item.id)}
                    for item in projection.sections
                ],
            ),
            (
                "MATCH (parent:Section {sql_id: row.parent_id, build_id: $build_id}) "
                "MATCH (child:Activity {sql_id: row.child_id, build_id: $build_id}) "
                "MERGE (parent)-[:HAS_ACTIVITY {build_id: $build_id}]->(child)",
                [
                    {"parent_id": item.properties["section_id"], "child_id": str(item.id)}
                    for item in projection.activities
                ],
            ),
            (
                "MATCH (parent:Activity {sql_id: row.parent_id, build_id: $build_id}) "
                "MATCH (child:SourceFragment {sql_id: row.child_id, build_id: $build_id}) "
                "MERGE (parent)-[:HAS_SOURCE {build_id: $build_id}]->(child)",
                [
                    {"parent_id": str(item.activity_id), "child_id": str(item.id)}
                    for item in projection.fragments
                ],
            ),
        )
        for body, rows in hierarchy_queries:
            self._run_rows("UNWIND $rows AS row " + body, rows, build_id)

        self._write_semantic_relationships(build_id, projection)

    def _write_semantic_relationships(
        self, build_id: UUID, projection: KnowledgeProjection
    ) -> None:
        groups: dict[tuple[str, str], list[dict]] = {}
        for item in projection.fragment_assertions:
            groups.setdefault(("fragment", item.assertion_type), []).append(
                {
                    "assertion_id": str(item.id),
                    "source_id": str(item.fragment_id),
                    "target_id": str(item.concept_id),
                    "properties": self._properties(item),
                }
            )
        for item in projection.concept_relations:
            groups.setdefault(("concept", item.assertion_type), []).append(
                {
                    "assertion_id": str(item.id),
                    "source_id": str(item.source_concept_id),
                    "target_id": str(item.target_concept_id),
                    "properties": self._properties(item),
                }
            )
        for item in projection.unit_assertions:
            groups.setdefault(("unit", item.assertion_type), []).append(
                {
                    "assertion_id": str(item.id),
                    "source_id": str(item.unit_id),
                    "target_id": str(item.concept_id),
                    "properties": self._properties(item),
                }
            )
        source_labels = {
            "fragment": "SourceFragment",
            "concept": "KnowledgeConcept",
            "unit": "Unit",
        }
        for (source_kind, assertion_type), rows in groups.items():
            relation = _RELATIONSHIP_TYPES.get(assertion_type)
            if relation is None:
                raise ValueError(f"Unsupported assertion type: {assertion_type}")
            self._run_rows(
                "UNWIND $rows AS row "
                f"MATCH (source:{source_labels[source_kind]} "
                "{sql_id: row.source_id, build_id: $build_id}) "
                "MATCH (target:KnowledgeConcept "
                "{sql_id: row.target_id, build_id: $build_id}) "
                f"MERGE (source)-[rel:{relation} "
                "{build_id: $build_id, assertion_id: row.assertion_id}]->(target) "
                "SET rel += row.properties, rel.review_status = 'verified'",
                rows,
                build_id,
            )

    def wait_until_online(
        self, build_id: UUID, *, timeout_seconds: float, poll_seconds: float = 0.25
    ) -> None:
        if timeout_seconds <= 0 or poll_seconds <= 0:
            raise ValueError("Index wait timing must be positive")
        names = BuildIdentifiers.from_build_id(build_id)
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            with self._driver.session(database=self._database) as session:
                records = session.run(
                    "SHOW VECTOR INDEXES YIELD name, state "
                    "WHERE name IN $names RETURN name, state",
                    names=[names.fragment_index, names.concept_index],
                )
                states = {record["name"]: record["state"] for record in records}
            if states == {
                names.fragment_index: "ONLINE",
                names.concept_index: "ONLINE",
            }:
                return
            time.sleep(poll_seconds)
        raise TimeoutError("Neo4j vector indexes did not become ONLINE")

    def validate_build(
        self,
        build_id: UUID,
        expected_counts: dict[str, int],
        *,
        dimensions: int,
    ) -> Neo4jBuildReport:
        label_map = {
            "textbooks": "Textbook",
            "units": "Unit",
            "sections": "Section",
            "activities": "Activity",
            "fragments": "SourceFragment",
            "concepts": "KnowledgeConcept",
        }
        counts: dict[str, int] = {}
        names = BuildIdentifiers.from_build_id(build_id)
        build_value = str(build_id)
        with self._driver.session(database=self._database) as session:
            for key, label in label_map.items():
                record = session.run(
                    f"MATCH (node:{label} {{build_id: $build_id}}) "
                    "RETURN count(node) AS count",
                    build_id=build_value,
                ).single()
                counts[key] = int(record["count"])
            for key, source_label in (
                ("fragment_assertions", "SourceFragment"),
                ("concept_relations", "KnowledgeConcept"),
                ("unit_assertions", "Unit"),
            ):
                record = session.run(
                    f"MATCH (source:{source_label} {{build_id: $build_id}})"
                    "-[rel {build_id: $build_id}]->"
                    "(:KnowledgeConcept {build_id: $build_id}) "
                    "WHERE rel.assertion_id IS NOT NULL "
                    "RETURN count(rel) AS count",
                    build_id=build_value,
                ).single()
                counts[key] = int(record["count"])
            relationship_records = session.run(
                "MATCH ()-[rel {build_id: $build_id}]->() "
                "RETURN type(rel) AS type, count(rel) AS count",
                build_id=build_value,
            )
            relationship_counts = {
                record["type"]: int(record["count"])
                for record in relationship_records
            }
            dimension_record = session.run(
                "MATCH (node {build_id: $build_id}) "
                "WHERE (node:SourceFragment OR node:KnowledgeConcept) "
                "AND size(node.embedding) <> $dimensions "
                "RETURN count(node) AS count",
                build_id=build_value,
                dimensions=dimensions,
            ).single()
            verified_record = session.run(
                "MATCH (node {build_id: $build_id}) "
                "WHERE (node:SourceFragment OR node:KnowledgeConcept) "
                "AND coalesce(node.verified, false) = false "
                "WITH count(node) AS bad_nodes "
                "OPTIONAL MATCH ()-[rel {build_id: $build_id}]->() "
                "WHERE rel.assertion_id IS NOT NULL "
                "AND coalesce(rel.review_status, '') <> 'verified' "
                "WITH bad_nodes, count(rel) AS bad_relationships "
                "RETURN bad_nodes + bad_relationships AS count",
                build_id=build_value,
            ).single()
            structural_orphans = session.run(
                "CALL { "
                "MATCH (node:Unit {build_id: $build_id}) "
                "WHERE NOT EXISTS { MATCH (:Textbook {build_id: $build_id})"
                "-[:HAS_UNIT {build_id: $build_id}]->(node) } "
                "RETURN count(node) AS count UNION ALL "
                "MATCH (node:Section {build_id: $build_id}) "
                "WHERE NOT EXISTS { MATCH (:Unit {build_id: $build_id})"
                "-[:HAS_SECTION {build_id: $build_id}]->(node) } "
                "RETURN count(node) AS count UNION ALL "
                "MATCH (node:Activity {build_id: $build_id}) "
                "WHERE NOT EXISTS { MATCH (:Section {build_id: $build_id})"
                "-[:HAS_ACTIVITY {build_id: $build_id}]->(node) } "
                "RETURN count(node) AS count UNION ALL "
                "MATCH (node:SourceFragment {build_id: $build_id}) "
                "WHERE NOT EXISTS { MATCH (:Activity {build_id: $build_id})"
                "-[:HAS_SOURCE {build_id: $build_id}]->(node) } "
                "RETURN count(node) AS count } "
                "RETURN sum(count) AS count",
                build_id=build_value,
            ).single()
            semantic_orphans = session.run(
                "MATCH (source)-[rel {build_id: $build_id}]->(target) "
                "WHERE rel.assertion_id IS NOT NULL AND "
                "(source.build_id <> $build_id OR target.build_id <> $build_id "
                "OR NOT target:KnowledgeConcept) "
                "RETURN count(rel) AS count",
                build_id=build_value,
            ).single()
            duplicate_record = session.run(
                "MATCH (node {build_id: $build_id}) "
                "UNWIND [label IN labels(node) WHERE label IN $labels] AS label "
                "WITH label, node.sql_id AS stable_id, count(node) AS occurrences "
                "WHERE occurrences > 1 "
                "RETURN coalesce(sum(occurrences - 1), 0) AS count",
                build_id=build_value,
                labels=list(label_map.values()),
            ).single()
            index_records = session.run(
                "SHOW VECTOR INDEXES YIELD name, state "
                "WHERE name IN $names RETURN name, state",
                names=[names.fragment_index, names.concept_index],
            )
            index_states = {
                record["name"]: record["state"] for record in index_records
            }
        orphan_counts = {
            "structural": int(structural_orphans["count"]),
            "semantic": int(semantic_orphans["count"]),
        }
        duplicate_ids = int(duplicate_record["count"])
        dimension_mismatches = int(dimension_record["count"])
        non_verified = int(verified_record["count"])
        failures = [
            f"count:{key}"
            for key, expected in expected_counts.items()
            if key in counts and counts[key] != expected
        ]
        if dimension_mismatches:
            failures.append("embedding_dimensions")
        if non_verified:
            failures.append("non_verified")
        if any(orphan_counts.values()):
            failures.append("orphan_endpoints")
        if duplicate_ids:
            failures.append("duplicate_ids")
        if index_states != {
            names.fragment_index: "ONLINE",
            names.concept_index: "ONLINE",
        }:
            failures.append("index_state")
        return Neo4jBuildReport(
            counts,
            relationship_counts,
            orphan_counts,
            dimension_mismatches,
            non_verified,
            duplicate_ids,
            index_states,
            tuple(failures),
        )

    def delete_build(self, build_id: UUID) -> None:
        names = BuildIdentifiers.from_build_id(build_id)
        with self._driver.session(database=self._database) as session:
            session.run(f"DROP INDEX {names.fragment_index} IF EXISTS").consume()
            session.run(f"DROP INDEX {names.concept_index} IF EXISTS").consume()
            session.run(
                "MATCH (node {build_id: $build_id}) DETACH DELETE node",
                build_id=str(build_id),
            ).consume()

    def query_vector_index(
        self,
        build_id: UUID,
        *,
        kind: str,
        vector: list[float],
        top_k: int,
    ) -> list[dict]:
        if kind not in {"fragment", "concept"} or top_k <= 0:
            raise ValueError("Vector query arguments are invalid")
        names = BuildIdentifiers.from_build_id(build_id)
        index_name = names.fragment_index if kind == "fragment" else names.concept_index
        with self._driver.session(database=self._database) as session:
            records = session.run(
                "CALL db.index.vector.queryNodes($index_name, $top_k, $vector) "
                "YIELD node, score WHERE node.build_id = $build_id "
                "RETURN node.sql_id AS sql_id, score ORDER BY score DESC, sql_id",
                index_name=index_name,
                top_k=top_k,
                vector=vector,
                build_id=str(build_id),
            )
            return [dict(record) for record in records]

