#!/usr/bin/env python3
"""PostToolUse hook: refresh the graphify graph for a file Claude just edited.

Runs AST extraction on the single changed file and splices the result into
graphify-out/graph.json. No LLM call, no re-clustering — community ids stay
stable so graphify-out/community_labels.json keeps matching. Semantic nodes
(the ones the extraction subagents produced) are preserved untouched; only the
AST-derived nodes and edges for that file are replaced.

Full re-clustering and semantic re-extraction still need `/graphify . --update`;
this hook records that need in graphify-out/.needs_update.

Silent no-op on any failure — a stale graph beats a broken edit loop.
"""
import json
import os
import subprocess
import sys
import tempfile

CODE_EXT = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".cpp", ".c",
    ".rb", ".swift", ".kt", ".cs", ".scala", ".php", ".h", ".hpp", ".lua",
}
SKIP_DIRS = ("graphify-out/", "static/vendor/", ".git/", "node_modules/", ".claude/")

# Runs inside the interpreter graphify is installed into, not this hook's.
WORKER = r'''
import json, sys
from pathlib import Path
from graphify.extract import extract

root = Path(sys.argv[1])
rel = sys.argv[2]
target = root / rel


def semantic_ids_for(rel):
    """Ids the LLM pass produced for this file.

    The cache is keyed by content hash, so an edited file no longer resolves —
    scan every semantic entry by source_file instead, or the edit would delete
    the file's semantic nodes from the graph.
    """
    ids = set()
    for entry in (root / "graphify-out" / "cache" / "semantic").glob("*.json"):
        try:
            data = json.loads(entry.read_text())
        except Exception:
            continue
        ids.update(n["id"] for n in data.get("nodes", []) if n.get("source_file") == rel)
    return ids

fresh = extract([target], cache_root=root)
# Extracting one file in isolation loses the repo-relative path and picks a
# different id prefix than the full-corpus run did, so trust only the labels.
for n in fresh["nodes"]:
    n["source_file"] = rel
for e in fresh["edges"]:
    e["source_file"] = rel

# Nodes the LLM pass produced for this file must survive an AST-only refresh.
sem_ids = semantic_ids_for(rel)

graph_file = root / "graphify-out" / "graph.json"
graph = json.loads(graph_file.read_text())

old_ast = [
    n for n in graph["nodes"]
    if n.get("source_file") == rel and n["id"] not in sem_ids
]
# Same symbol keeps its old id so every existing edge endpoint stays valid.
by_label = {n.get("label"): n["id"] for n in old_ast}
remap = {n["id"]: by_label[n.get("label")] for n in fresh["nodes"] if n.get("label") in by_label}
for n in fresh["nodes"]:
    n["id"] = remap.get(n["id"], n["id"])
for e in fresh["edges"]:
    e["source"] = remap.get(e.get("source"), e.get("source"))
    e["target"] = remap.get(e.get("target"), e.get("target"))

survivors = {n["id"] for n in fresh["nodes"]}
stale = {n["id"] for n in old_ast if n["id"] not in survivors}
# Drop the file's old AST edges wholesale; fresh extraction re-supplies them.
old_ast_ids = {n["id"] for n in old_ast}
kept_nodes = [n for n in graph["nodes"] if n["id"] not in stale]
kept_links = [
    e for e in graph["links"]
    if e.get("source") not in stale and e.get("target") not in stale
    and not (e.get("source_file") == rel
             and e.get("source") in old_ast_ids and e.get("target") in old_ast_ids)
]

# Reuse the community this file already belonged to; unseen files get a fresh
# id so clustering stays deterministic until the next full /graphify --update.
prior = [n.get("community") for n in graph["nodes"] if n.get("source_file") == rel]
prior = [c for c in prior if c is not None]
if prior:
    community = max(set(prior), key=prior.count)
else:
    community = max((n.get("community", 0) for n in graph["nodes"]), default=0) + 1

index = {n["id"]: n for n in kept_nodes}
added = 0
for n in fresh["nodes"]:
    old = index.get(n["id"])
    if old is not None:
        # Refresh line numbers in place; keep clustering and any semantic fields.
        old["source_location"] = n.get("source_location", old.get("source_location"))
        old["label"] = n.get("label", old.get("label"))
        continue
    n.setdefault("community", community)
    n.setdefault("norm_label", n.get("label", n["id"]))
    kept_nodes.append(n)
    index[n["id"]] = n
    added += 1

for e in fresh["edges"]:
    if e.get("source") in index and e.get("target") in index:
        kept_links.append(e)

# Re-extraction re-emits edges the graph already holds; collapse them so
# repeated edits can't inflate the link list.
seen, deduped = set(), []
for e in kept_links:
    key = (e.get("source"), e.get("target"), e.get("relation"))
    if key in seen:
        continue
    seen.add(key)
    deduped.append(e)

graph["nodes"] = kept_nodes
graph["links"] = deduped
tmp = graph_file.with_suffix(".json.tmp")
tmp.write_text(json.dumps(graph))
tmp.replace(graph_file)

(root / "graphify-out" / ".needs_update").write_text(
    "AST-only refresh applied; run /graphify . --update for semantic re-extraction\n")
print(f"{rel}: -{len(stale)} +{added} AST nodes")
'''


def repo_root():
    here = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    while True:
        if os.path.isdir(os.path.join(here, "graphify-out")):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent


def main():
    payload = json.load(sys.stdin)
    ti = payload.get("tool_input") or {}
    tr = payload.get("tool_response") or {}
    raw = tr.get("filePath") or ti.get("file_path") or ""
    if not raw or os.path.splitext(raw)[1].lower() not in CODE_EXT:
        return

    root = repo_root()
    if not root or not os.path.exists(os.path.join(root, "graphify-out", "graph.json")):
        return
    rel = os.path.relpath(os.path.abspath(raw), root)
    if rel.startswith("..") or any(rel.startswith(d) for d in SKIP_DIRS):
        return
    if not os.path.exists(os.path.join(root, rel)):
        return

    marker = os.path.join(root, "graphify-out", ".graphify_python")
    python = open(marker).read().strip() if os.path.exists(marker) else sys.executable

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(WORKER)
        worker = f.name
    try:
        subprocess.run([python, worker, root, rel], capture_output=True, timeout=90)
    finally:
        os.unlink(worker)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
