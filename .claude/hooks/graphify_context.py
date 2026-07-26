#!/usr/bin/env python3
"""PreToolUse hook: answer from the graphify graph before the source file.

Read is gated in two phases, per session and per file. The first Read is
denied and returns the graph slice instead — nodes, communities, and the
cross-file edges that are invisible from inside the file. Repeating the same
Read goes through to the real contents.

Grep and Glob are never denied: they scan rather than read, and there is no
useful "second attempt" to redirect them to. They only get the slice appended
as extra context.

Silent no-op when there is no graph, no match, or anything goes wrong: a hook
that breaks Read is worse than a hook that adds nothing.
"""
import hashlib
import json
import os
import sys
from collections import defaultdict

MAX_NODES = 14
MAX_EDGES = 14
MAX_COMMUNITIES = 8
MAX_LABEL = 60
# Minified vendor bundles produce thousands of meaningless nodes.
SKIP_DIRS = ("graphify-out/", "static/vendor/", ".git/", "node_modules/")


def clip(text):
    text = " ".join(str(text).split())
    return text if len(text) <= MAX_LABEL else text[: MAX_LABEL - 1] + "…"


def repo_root():
    # Hook cwd is the project dir; fall back to walking up for graphify-out/.
    here = os.getcwd()
    while True:
        if os.path.isdir(os.path.join(here, "graphify-out")):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent


def target_path(payload):
    ti = payload.get("tool_input") or {}
    return ti.get("file_path") or ti.get("path") or ""


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def resolve_labels(root, graph):
    """Map community id -> human label, surviving a re-cluster.

    community_labels.json is keyed by numeric community id, which the git
    post-commit rebuild reassigns. community_anchors.json pins each label to a
    handful of member node ids instead, and those ids are stable, so anchors
    win wherever they resolve.
    """
    out = os.path.join(root, "graphify-out")
    labels = load_json(os.path.join(out, "community_labels.json"))
    anchors = load_json(os.path.join(out, "community_anchors.json"))
    if not anchors:
        return labels

    node_comm = {n["id"]: n.get("community") for n in graph["nodes"]}
    votes = defaultdict(lambda: defaultdict(int))
    for name, ids in anchors.items():
        for nid in ids:
            cid = node_comm.get(nid)
            if cid is not None:
                votes[cid][name] += 1

    resolved = dict(labels)
    for cid, tally in votes.items():
        resolved[str(cid)] = max(tally.items(), key=lambda kv: kv[1])[0]
    return resolved


def already_shown(root, payload, rel):
    """True once this session has been given the graph slice for this path.

    Marks on first call, so the caller can deny the first Read and let the
    retry through. State lives under .claude/.cache/ (gitignored) keyed by
    session so a fresh session starts from the graph again.
    """
    session = str(payload.get("session_id") or "nosession").replace("/", "_")
    key = hashlib.sha1(rel.encode()).hexdigest()[:16]
    d = os.path.join(root, ".claude", ".cache", "graphify-seen", session)
    marker = os.path.join(d, key)
    if os.path.exists(marker):
        return True
    os.makedirs(d, exist_ok=True)
    open(marker, "w").close()
    return False


def edge_line(nodes, e, direction):
    other = e["target"] if direction == "out" else e["source"]
    arrow = "-->" if direction == "out" else "<--"
    conf = e.get("confidence", "")
    score = e.get("confidence_score")
    tag = f"{conf} {score}" if score is not None else conf
    o = nodes.get(other, {})
    return f'  {arrow} {e.get("relation","?")} [{tag}] {clip(o.get("label", other))} ({o.get("source_file","?")})'


def main():
    payload = json.load(sys.stdin)
    root = repo_root()
    if not root:
        return
    graph_file = os.path.join(root, "graphify-out", "graph.json")
    if not os.path.exists(graph_file):
        return

    raw = target_path(payload)
    if not raw:
        return
    rel = os.path.relpath(os.path.abspath(raw), root)
    if rel.startswith("..") or any(rel.startswith(d) for d in SKIP_DIRS):
        return

    with open(graph_file) as f:
        graph = json.load(f)
    nodes = {n["id"]: n for n in graph["nodes"]}

    is_dir = os.path.isdir(raw)
    prefix = rel.rstrip("/") + "/" if is_dir else None
    mine = {
        nid: n for nid, n in nodes.items()
        if (n.get("source_file", "").startswith(prefix) if is_dir
            else n.get("source_file") == rel)
    }
    if not mine:
        return

    comm_labels = resolve_labels(root, graph)

    # Cross-file edges are the payload — same-file edges are visible in the source.
    out_edges, in_edges = [], []
    for e in graph["links"]:
        s, t = e.get("source"), e.get("target")
        if s in mine and t not in mine:
            out_edges.append(e)
        elif t in mine and s not in mine:
            in_edges.append(e)

    def rank(e, direction):
        other = nodes.get(e["target"] if direction == "out" else e["source"], {})
        vendor = "vendor/" in other.get("source_file", "")
        # Weak-confidence edges flag missing/uncertain structure — surface first.
        weak = e.get("confidence") in ("AMBIGUOUS", "INFERRED")
        return (vendor, not weak, e.get("confidence_score") or 0)

    def dedupe(edges, direction):
        seen, kept = set(), []
        for e in edges:
            key = (e.get("relation"), e["target"] if direction == "out" else e["source"])
            if key in seen:
                continue
            seen.add(key)
            kept.append(e)
        return kept

    out_edges = dedupe(sorted(out_edges, key=lambda e: rank(e, "out")), "out")
    in_edges = dedupe(sorted(in_edges, key=lambda e: rank(e, "in")), "in")

    by_comm = defaultdict(list)
    for n in mine.values():
        by_comm[n.get("community")].append(clip(n.get("label", n["id"])))

    lines = [f"[graphify] {rel} — {len(mine)} nodes in graph"]
    ranked = sorted(by_comm.items(), key=lambda kv: -len(kv[1]))
    for cid, labs in ranked[:MAX_COMMUNITIES]:
        name = comm_labels.get(str(cid), f"Community {cid}")
        if is_dir:
            # A whole directory spans too many nodes to list — names and counts only.
            lines.append(f'  C{cid} "{name}" — {len(labs)} nodes')
            continue
        shown = labs[:MAX_NODES]
        more = f" (+{len(labs) - len(shown)} more)" if len(labs) > len(shown) else ""
        lines.append(f'  C{cid} "{name}": {", ".join(shown)}{more}')
    if len(ranked) > MAX_COMMUNITIES:
        rest = sum(len(l) for _, l in ranked[MAX_COMMUNITIES:])
        lines.append(f"  (+{len(ranked) - MAX_COMMUNITIES} smaller communities, {rest} nodes)")

    half = max(1, MAX_EDGES // 2)
    if out_edges:
        lines.append(f"  outgoing ({len(out_edges)} total):")
        lines += [edge_line(nodes, e, "out") for e in out_edges[:half]]
    if in_edges:
        lines.append(f"  incoming ({len(in_edges)} total):")
        lines += [edge_line(nodes, e, "in") for e in in_edges[:half]]

    slice_text = "\n".join(lines)
    gate = payload.get("tool_name") == "Read" and not is_dir

    if gate and not already_shown(root, payload, rel):
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    slice_text
                    + "\n\nThis is the graph view of the file, served instead of its "
                      "contents. If the structure above answers the question, use it. "
                      "If you need the source, issue the same Read again — it will go "
                      "through."
                ),
            }
        }))
        return

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": slice_text,
        }
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
