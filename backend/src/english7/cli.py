import argparse
import json
from pathlib import Path
from uuid import UUID

from neo4j import GraphDatabase

from english7.core.settings import get_settings
from english7.db.session import get_session_factory
from english7.modules.knowledge.embedding import EmbeddingIdentity, FastEmbedService
from english7.modules.knowledge.embedding_benchmark import BenchmarkDataset, benchmark
from english7.modules.knowledge.build_service import KnowledgeGraphBuildService
from english7.modules.knowledge.graph_builder import ProjectionEmbeddingBuilder
from english7.modules.knowledge.neo4j_repository import (
    BuildIdentifiers,
    VersionedNeo4jRepository,
)
from english7.modules.knowledge.ontology_importer import OntologyImporter
from english7.modules.knowledge.ontology_manifest import OntologyManifest
from english7.modules.knowledge.sql_repository import SQLAlchemyKnowledgeRepository
from english7.modules.seeding.importer import SeedImporter
from english7.modules.seeding.manifest import SeedManifest
from english7.modules.seeding.repository import SQLAlchemySeedRepository


class FileObjectCatalog:
    def __init__(self, listing_path: Path) -> None:
        self._keys = {
            line.strip()
            for line in listing_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }

    def exists(self, object_key: str) -> bool:
        return object_key in self._keys


def _repository() -> SQLAlchemySeedRepository:
    return SQLAlchemySeedRepository(lambda: get_session_factory()())


def _knowledge_repository() -> SQLAlchemyKnowledgeRepository:
    return SQLAlchemyKnowledgeRepository(lambda: get_session_factory()())


def import_seed(args: argparse.Namespace) -> None:
    manifest = SeedManifest.load(args.manifest)
    importer = SeedImporter(
        _repository(),
        FileObjectCatalog(args.audio_object_list),
        set(args.supported_schema_version),
        set(args.allowed_unit),
    )
    result = importer.import_manifest(manifest, args.source.read_bytes())
    print(
        f"package={result.package_id} created={str(result.created).lower()} "
        f"fragments={result.fragment_count} audio={result.audio_count}"
    )


def export_seed(args: argparse.Namespace) -> None:
    manifest = _repository().get_manifest(args.package_id)
    if manifest is None:
        raise SystemExit("Seed package was not found")
    args.output.write_text(manifest.to_json() + "\n", encoding="utf-8")


def dump_sql(args: argparse.Namespace) -> None:
    import sys
    from english7.db.session import get_engine
    from english7.modules.backup import SqlDatabaseDumper

    dumper = SqlDatabaseDumper(get_engine(), database_name=args.database)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as f:
            dumper.dump(f)
        print(f"Dump written to {args.output}")
    else:
        dumper.dump(sys.stdout)



def import_ontology(args: argparse.Namespace) -> None:
    result = OntologyImporter(_knowledge_repository()).import_manifest(
        OntologyManifest.load(args.manifest)
    )
    print(
        f"manifest={result.manifest_id} created={str(result.created).lower()} "
        f"concepts={result.concept_count} assertions={result.assertion_count}"
    )


def benchmark_embeddings(args: argparse.Namespace) -> None:
    settings = get_settings()
    dimensions = args.dimensions or settings.embedding_dimensions
    if dimensions is None:
        raise SystemExit("Embedding dimensions are required")
    identity = EmbeddingIdentity(
        provider=settings.embedding_provider,
        model=args.model,
        model_version=args.model_version,
        dimensions=dimensions,
        query_prefix=settings.embedding_query_prefix,
        passage_prefix=settings.embedding_passage_prefix,
        preprocessing_version=settings.embedding_preprocessing_version,
    )
    dataset = BenchmarkDataset.load(args.cases)
    report = benchmark(
        FastEmbedService(
            identity=identity,
            cache_dir=Path(settings.embedding_cache_dir),
            batch_size=settings.embedding_batch_size,
        ),
        dataset.cases,
        dataset.candidates,
        top_k=args.top_k,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))


def _knowledge_build_service():
    settings = get_settings()
    required = {
        "ENGLISH7_NEO4J_URI": settings.neo4j_uri,
        "ENGLISH7_NEO4J_USER": settings.neo4j_user,
        "ENGLISH7_NEO4J_PASSWORD": settings.neo4j_password,
        "ENGLISH7_EMBEDDING_MODEL": settings.embedding_model,
        "ENGLISH7_EMBEDDING_MODEL_VERSION": settings.embedding_model_version,
        "ENGLISH7_EMBEDDING_DIMENSIONS": settings.embedding_dimensions,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise SystemExit("Missing required settings: " + ", ".join(missing))
    identity = EmbeddingIdentity(
        provider=settings.embedding_provider,
        model=settings.embedding_model,
        model_version=settings.embedding_model_version,
        dimensions=settings.embedding_dimensions,
        query_prefix=settings.embedding_query_prefix,
        passage_prefix=settings.embedding_passage_prefix,
        preprocessing_version=settings.embedding_preprocessing_version,
    )
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
    )
    embedder = FastEmbedService(
        identity=identity,
        cache_dir=Path(settings.embedding_cache_dir),
        batch_size=settings.embedding_batch_size,
    )
    service = KnowledgeGraphBuildService(
        _knowledge_repository(),
        VersionedNeo4jRepository(driver),
        ProjectionEmbeddingBuilder(
            embedder, batch_size=settings.embedding_batch_size
        ),
        index_timeout_seconds=settings.knowledge_graph_index_timeout_seconds,
    )
    return service, driver, identity


def build_knowledge_graph(args: argparse.Namespace) -> None:
    service, driver, identity = _knowledge_build_service()
    try:
        result = service.build(args.ontology_version)
    finally:
        driver.close()
    names = BuildIdentifiers.from_build_id(result.build.id)
    summary = {
        "build_id": str(result.build.id),
        "status": result.build.status.value,
        "source_checksum": result.build.source_checksum,
        "ontology_version": result.build.ontology_version,
        "reused_active_build": result.reused_active_build,
        "expected_counts": result.build.expected_counts,
        "actual_counts": result.build.actual_counts,
        "embedding_identity": {
            "provider": identity.provider,
            "model": identity.model,
            "model_version": identity.model_version,
            "dimensions": identity.dimensions,
            "preprocessing_version": identity.preprocessing_version,
        },
        "indexes": {
            "fragment": names.fragment_index,
            "concept": names.concept_index,
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="english7")
    commands = parser.add_subparsers(required=True)

    importer = commands.add_parser("import-seed")
    importer.add_argument("--manifest", type=Path, required=True)
    importer.add_argument("--source", type=Path, required=True)
    importer.add_argument("--audio-object-list", type=Path, required=True)
    importer.add_argument(
        "--supported-schema-version", type=int, action="append", required=True
    )
    importer.add_argument("--allowed-unit", type=int, action="append", required=True)
    importer.set_defaults(handler=import_seed)

    exporter = commands.add_parser("export-seed")
    exporter.add_argument("--package-id", type=UUID, required=True)
    exporter.add_argument("--output", type=Path, required=True)
    exporter.set_defaults(handler=export_seed)

    ontology = commands.add_parser("import-ontology")
    ontology.add_argument("--manifest", type=Path, required=True)
    ontology.set_defaults(handler=import_ontology)

    embedding_benchmark = commands.add_parser("benchmark-embeddings")
    embedding_benchmark.add_argument("--cases", type=Path, required=True)
    embedding_benchmark.add_argument("--model", required=True)
    embedding_benchmark.add_argument("--model-version", required=True)
    embedding_benchmark.add_argument("--dimensions", type=int)
    embedding_benchmark.add_argument("--top-k", type=int, default=5)
    embedding_benchmark.set_defaults(handler=benchmark_embeddings)

    graph_build = commands.add_parser("build-knowledge-graph")
    graph_build.add_argument("--ontology-version", required=True)
    graph_build.set_defaults(handler=build_knowledge_graph)

    dump_parser = commands.add_parser("dump-sql")
    dump_parser.add_argument("--database", default="english7")
    dump_parser.add_argument("--output", type=Path, default=None)
    dump_parser.set_defaults(handler=dump_sql)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
