*Load when: a case has grown past roughly 150 entities and the questions have turned structural — which cluster is this, what connects these two, who is the hub — and the mermaid chart from `graph.py` has stopped being readable. Not before. Read the "Do not bother" section first; on most cases it ends here.*

# graphify as an optional case backend

graphify is **third-party software, not part of this plugin**. Nothing in the OSINT plugin depends
on it, no play requires it, and no case is worse for never touching it. It is a knowledge-graph
builder with community detection, shortest-path and degree-centrality queries, and it happens to
fit `entities.jsonl` + `events.jsonl` well enough to be worth documenting.

Everything below was verified against the copy installed on this machine on 2026-07-28 by reading
its source and by building and querying a real fixture graph. It is **not** verified against any
other version. Re-check before trusting it elsewhere.

| What | Verified value |
|---|---|
| Skill | `~/.claude/skills/graphify/SKILL.md` plus `references/` |
| Package | `graphifyy` 0.9.8, installed as a `uv` tool |
| CLI | `graphify` on PATH |
| MCP server | tools named `mcp__graphify__*` |
| Graph file | `<dir>/graphify-out/graph.json` — one graph per directory |

## Do not bother

The integration is optional, and on a normal case it is the wrong call. Skip it when any of these
is true:

- **The case has under ~150 entities.** `graph.py` renders the whole thing as a mermaid chart you
  can read in one screen, with shapes carrying entity class, border weight carrying the confidence
  band, and `candidate_group` drawn as a dashed UNRESOLVED cluster. graphify draws none of that —
  it has no concept of an Admiralty grade or an unresolved identity. Below that size you lose
  meaning and gain nothing.
- **You want a picture.** graphify's HTML view is a force-directed blob. `graph.py --format mermaid`
  or `--format dot` is the deliverable-grade artifact, and `/osint:osint-graph` already runs it.
- **You want validation.** `graph.py --validate` is the identity-confusion gate and the pre-report
  check. graphify validates its own schema only; it will happily build a graph over entities that
  `graph.py --validate` rejects, and it will not tell you.
- **The question is "what did I find".** That is `findings.md`. A graph answers structural
  questions, not factual ones.
- **The case is still being collected.** The graph is a snapshot; rebuilding after every pivot
  costs more than it returns. Build it once, when collection is saturating.

graphify's own corpus check warns below 50,000 words that you may not need a graph at all
(`CORPUS_WARN_THRESHOLD` in its `detect.py`). A case file rarely reaches that. Take the hint.

Where it does earn its place: a link-analysis case with several hundred entities — a sanctions
network, an infrastructure estate across many registrants, a transaction graph with hundreds of
addresses — where the useful questions are which sub-network is which, what the shortest chain
between two named entities is, and which node holds the whole thing together.

## What it answers that `graph.py` cannot

| Question | graphify surface | `graph.py` |
|---|---|---|
| Which sub-networks exist, and who is in each | community detection, `get_community` | nothing — mermaid has no clustering |
| What is the shortest chain from A to B, and what does each hop assert | `shortest_path` / `graphify path` | nothing — you trace it by eye |
| Which entity is the hub of the network | `god_nodes` (degree ranking) | nothing |
| What is within N hops of this entity, budgeted | `query_graph` (BFS/DFS, token budget) | nothing |
| What is the confidence mix across the whole edge set | `graph_stats` | nothing |
| Is this entity's grade `B2` or `C3` | nothing | every node carries the pair |
| Is this identity unresolved | nothing | dashed UNRESOLVED cluster |
| Is the entity file internally sound | nothing | `--validate` |

They are complements, not alternatives. `graph.py` stays the authority on the case. graphify is a
lens over a copy of it.

## Feeding a case in

**`.jsonl` is not a file type graphify recognises.** Its `detect.py` classifies `.json` as code,
`.md`/`.txt`/`.yaml` as documents, `.pdf` as papers, plus image and video sets. `.jsonl` is in none
of them. Pointing `/graphify` at a case directory therefore does **not** ingest the entity or event
files — it ingests `scope.md`, `findings.md` and `gaps.md` as prose and sends them to an LLM for
semantic extraction.

Do not do that. An LLM re-deriving relationships from your findings prose invents edges into an
evidence graph, and graphify labels its own guesses `INFERRED`, not "invented". Convert the
structured files directly instead: they already are a node list and an edge list, so the conversion
is deterministic, costs no tokens, needs no API key, and cannot hallucinate.

### Schema graphify requires

Read from `graphify/validate.py`:

| | Required fields | Constrained values |
|---|---|---|
| Node | `id` `label` `file_type` `source_file` | `file_type` ∈ `code` `document` `paper` `image` `rationale` `concept` |
| Edge | `source` `target` `relation` `confidence` `source_file` | `confidence` ∈ `EXTRACTED` `INFERRED` `AMBIGUOUS` |

Extra keys on a node survive the build and land in `graph.json`, so carry `grade` and the canonical
selector `type` through as node attributes — verified.

### The mapping

| Case object | graphify object |
|---|---|
| `entities.jsonl` row | node, `id` = the `e-<n>` id, `label` = `<type>:<value>`, `file_type` = `concept` |
| `events.jsonl` row | node, `id` = `ev-<n>`, `label` = ts + description |
| entity `attributed_to` | edge, `relation` = `attributed_to`, `confidence` = `EXTRACTED` |
| shared `candidate_group` | edge chaining members, `relation` = `candidate_group`, `confidence` = `AMBIGUOUS` |
| event `actor_entity` | edge to the event node, `relation` = `event`, `confidence` = `EXTRACTED` |

That edge set is the same one `graph.py` builds, so the two views agree by construction. Chain
group members (`n-1` edges) rather than joining every pair — `graph.py` does the same and for the
same reason.

`EXTRACTED` here means "this edge is literally written in the case file", nothing more. It is not a
confidence claim. See the collision warning below.

### Build

Run under graphify's own interpreter, not the system Python — it needs `graphify` and `networkx`
importable. On this machine that is the `uv` tool venv; `uv tool dir` locates it, and graphify's
own skill writes the resolved path to `graphify-out/.graphify_python` when it runs.

```python
# convert a case to graphify-out/graph.json. Verified end to end 2026-07-28.
import json, sys
from pathlib import Path
from graphify.build import build_from_json
from graphify.cluster import cluster
from graphify.export import to_json

case = Path(sys.argv[1])
rows = lambda p: [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.is_file() else []

ents = {e["id"]: e for e in rows(case / "entities.jsonl")}          # last row per id wins
nodes = [{"id": i, "label": f'{e["type"]}:{e["value"]}', "file_type": "concept",
          "source_file": "entities.jsonl", "grade": e.get("grade", ""),
          "entity_type": e.get("type", "")} for i, e in ents.items()]
edges, groups = [], {}
for i, e in ents.items():
    if e.get("candidate_group"):
        groups.setdefault(e["candidate_group"], []).append(i)
    if e.get("attributed_to"):
        edges.append({"source": i, "target": e["attributed_to"], "relation": "attributed_to",
                      "confidence": "EXTRACTED", "source_file": "entities.jsonl"})
for ids in groups.values():
    edges += [{"source": a, "target": b, "relation": "candidate_group",
               "confidence": "AMBIGUOUS", "source_file": "entities.jsonl"} for a, b in zip(ids, ids[1:])]
for n, ev in enumerate(rows(case / "events.jsonl"), start=1):
    nodes.append({"id": f"ev-{n}", "label": f'{ev.get("ts")} {ev.get("description")}',
                  "file_type": "concept", "source_file": "events.jsonl", "grade": ev.get("grade", "")})
    if ev.get("actor_entity"):
        edges.append({"source": ev["actor_entity"], "target": f"ev-{n}", "relation": "event",
                      "confidence": "EXTRACTED", "source_file": "events.jsonl"})

G = build_from_json({"nodes": nodes, "edges": edges, "hyperedges": [],
                     "input_tokens": 0, "output_tokens": 0}, root=str(case), directed=False)
out = case / "graphify-out" / "graph.json"
out.parent.mkdir(parents=True, exist_ok=True)
if not to_json(G, cluster(G), str(out)):
    raise SystemExit("refused to shrink an existing graph.json; delete it to rebuild")
print(G.number_of_nodes(), "nodes,", G.number_of_edges(), "edges")
```

Verified API shapes: `build_from_json(extraction, *, directed=False, root=None)` returns a
`networkx.Graph` (or `DiGraph` when `directed=True`); `cluster(G)` returns
`{community_id: [node_id, ...]}`; `to_json(G, communities, path)` writes the file and returns
falsey **without writing** when the new graph has fewer nodes than an existing `graph.json` — a
deliberate shrink guard, not a failure. Delete the file to force a smaller rebuild.

Keep `graphify-out/` **outside** the evidence tree or treat it as derived: it is a regenerable
projection, not evidence. It has no hash, no retrieval timestamp, and nothing in it may be cited.
Cite the ledger row the entity came from.

## Query surface

### CLI — verified from `graphify --help` and by running it

| Command | Does |
|---|---|
| `graphify path "A" "B" --graph <graph.json>` | shortest path, printing each hop's relation and confidence |
| `graphify query "<terms>" --graph <graph.json> [--dfs] [--budget N]` | BFS (or DFS) traversal, output capped at N tokens, default 2000 |
| `graphify explain "X" --graph <graph.json>` | one node, its degree, community, and every neighbour with the edge relation |
| `graphify affected "X" --graph <graph.json> [--depth N]` | reverse traversal — what depends on X |
| `graphify cluster-only <path>` | re-cluster an existing graph without re-extracting |

`--graph` defaults to `graphify-out/graph.json` relative to the current directory.

### MCP — tool names and argument names verified from the live server

All take an optional `project_path`: an absolute path to a directory containing
`graphify-out/graph.json`. Pass it explicitly with the case directory; without it the server
answers from whatever graph it was started with, which is not your case.

| Tool | Required args | Optional args |
|---|---|---|
| `mcp__graphify__graph_stats` | — | `project_path` |
| `mcp__graphify__god_nodes` | — | `top_n` (default 10), `project_path` |
| `mcp__graphify__get_community` | `community_id` (int, 0-indexed by size) | `project_path` |
| `mcp__graphify__get_node` | `label` | `project_path` |
| `mcp__graphify__get_neighbors` | `label` | `relation_filter`, `project_path` |
| `mcp__graphify__query_graph` | `question` | `mode` (`bfs`\|`dfs`), `depth` (1-6), `token_budget`, `context_filter`, `project_path` |
| `mcp__graphify__shortest_path` | `source`, `target` | `max_hops` (default 8), `project_path` |

The same server also exposes `get_pr_impact`, `list_prs` and `triage_prs`. Those are source-repo
features and have nothing to do with a case.

## Where it will mislead you

- **Confidence vocabulary collision.** graphify's `EXTRACTED` / `INFERRED` / `AMBIGUOUS` is an
  extraction-provenance tag, not an Admiralty grade. `graph_stats` reporting "EXTRACTED: 86%" says
  86% of edges were copied out of the file — it says nothing about reliability or credibility.
  Never carry a graphify confidence word into `findings.md`, and never let it stand in for a grade.
  Grades come from `41-confidence.md` and live on the entity, not the edge.
- **A `candidate_group` edge is not a link.** In graphify it is an ordinary edge and both
  `shortest_path` and `god_nodes` will happily route through it. A path that crosses an
  `AMBIGUOUS` hop asserts nothing about the real world — the identity is unresolved, which is the
  whole point of the group. Read the confidence on every hop the tool prints, and drop any path
  that leans on one.
- **Node matching is case-folded substring, no stemming, no synonyms.** A near-miss query returns
  nothing rather than something approximate. `graphify path` prints an explicit warning when the
  match was ambiguous — treat that warning as "this is the wrong node" until you check.
- **"No path found" means disconnected, not unrelated.** A case graph is normally several
  components. Observed on the fixture: the infrastructure component and the corporate component had
  no edge between them, so the shortest-path query correctly returned nothing. That is a finding
  for `gaps.md`, not an error.
- **Degree is not importance.** `god_nodes` ranks by edge count. In a case that mostly means "the
  entity you collected most around", which is a fact about your collection, not about the network.
  Say so if it reaches a report.
- **`/graphify` on a folder silently skips files whose names look like credential stores** —
  `.env`, `.pem`/`.key`, `id_rsa`, and load-bearing `credential`/`secret`/`password`/`token` in the
  filename. A case note named `credentials.md` would vanish from the corpus without an error. The
  conversion above avoids this entirely by never scanning the directory.

## Case discipline still applies

Building the graph is a derivation step, not a collection step. Log it as one ledger row with
`"action":"finding"`, `"source":"graphify"`, `"mode":"passive"`, and a `query` that names the scope
question it advances. It touches nothing external — no network, no target, no third party.

Anything a graph query changes your mind about goes back into the case the normal way: the entity
or event row it came from, its grade, and its source. A community boundary, a path, or a centrality
ranking is a **hypothesis**, and it enters `findings.md` only after `40-analysis.md` has been
applied to it and it has been graded on the underlying evidence — never on the strength of the
graph drawing it.
