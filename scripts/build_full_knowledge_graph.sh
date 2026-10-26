#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if command -v docker >/dev/null 2>&1 && docker compose ps api --status running -q 2>/dev/null | grep -q .; then
  echo "Building full knowledge graph in Neo4j (via Docker API container)..."
  docker compose exec -T api python - < "$REPO_ROOT/backend/scripts/build_full_knowledge_graph.py"
else
  cd "$REPO_ROOT/backend"
  if [ -f "$HOME/.local/bin/uv" ]; then
    UV="$HOME/.local/bin/uv"
  else
    UV="uv"
  fi
  echo "Building full knowledge graph in Neo4j (via local uv)..."
  $UV run python scripts/build_full_knowledge_graph.py
fi
