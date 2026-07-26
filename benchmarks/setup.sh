#!/usr/bin/env bash
# Clone and index the repositories the benchmark measures.
#
# Commits are PINNED. The numbers in docs/BENCHMARKS.md are from these exact
# trees, and an unpinned clone would silently report different ones tomorrow —
# which is the difference between a benchmark and an anecdote.
#
#   ./benchmarks/setup.sh            # into benchmarks/repos/
#   ./benchmarks/setup.sh /tmp/bench # somewhere else
#
# Indexing calls the embedding endpoint, so it needs OPENROUTER_API_KEY (or a
# local endpoint via MEGABRAIN_EMBED_BASE_URL). Roughly 430 files in total.
set -euo pipefail

WHERE="${1:-$(dirname "$0")/repos}"
mkdir -p "$WHERE"

# name|url|commit
REPOS=(
  "click|https://github.com/pallets/click|00e592cea702e0b2caa0dee42489fdb1c22cd845"
  "bench-express|https://github.com/expressjs/express|ae6dd37680e3a00618d6c8a3e522f0ee4eeba1a4"
  "sinatra|https://github.com/sinatra/sinatra|cb22afd7902b566b6eaba6c4ea89739494a65d12"
)

for entry in "${REPOS[@]}"; do
  IFS='|' read -r name url commit <<< "$entry"
  target="$WHERE/$name"
  if [ ! -d "$target/.git" ]; then
    echo "── cloning $name"
    git clone -q "$url" "$target"
  fi
  git -C "$target" fetch -q --depth 1 origin "$commit" 2>/dev/null || git -C "$target" fetch -q
  git -C "$target" checkout -q "$commit"
  echo "── indexing $name at ${commit:0:8}"
  megabrain index "$target"
done

echo
echo "ready. now: python benchmarks/measure.py --repos $WHERE"
