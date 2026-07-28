---
description: Validate the case entity graph and render it as a link chart — mermaid by default, Graphviz DOT or a plain-text adjacency summary on request. Runs graph.py --validate first and refuses to draw a chart over a case that fails, because a pretty chart of unvalidated data is worse than no chart. Checks for un-flagged duplicate identities, one-member candidate groups, invalid grades, non-canonical selector types, entities with no sources, and merges with no linking datapoint. Use when the user says "draw the link chart", "graph this case", "show me the entity graph", "validate the entities", "check the case data", "render the network", or is about to compile a report.
argument-hint: [case-slug | blank for the open case] [mermaid | dot | text]
---

# Link chart and entity validation

One script, two jobs: `${CLAUDE_PLUGIN_ROOT}/scripts/graph.py`. It is read-only — nothing in the
case directory is written by either job.

`$1` is a case slug; blank means the open case. `$2` is a format, default `mermaid` because it
renders natively in markdown, in artifacts, and in section 8 of the report template.

## 0. Find the case

Glob `${CLAUDE_PROJECT_DIR}/cases/*/scope.md`. None → `/osint:osint-scope`, nothing to draw.
Several and no slug given → list them and ask; do not assume the most recent. `CASE_DIR` below is
`${CLAUDE_PROJECT_DIR}/cases/<slug>`.

## 1. Validate — always, and always before rendering

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/graph.py" "<CASE_DIR>" --validate
```

`py -3` if `python` is not on PATH. Exit `0` clean, `1` violations found, `2` usage error, `3` the
case directory or `entities.jsonl` is unreadable.

**Exit 1 means stop.** Report the violations as the script printed them, in one block, and do not
render. Each line carries the entity id, the line number in `entities.jsonl`, the rule, and what to
do about it. Fixing them is an append: `entities.jsonl` is append-only, so a correction is a new
row carrying the same id, never an edit to an existing line.

| Rule | What it caught | Why it is not cosmetic |
|---|---|---|
| `dup-value` | Two ids, same type, same normalized value, no shared `candidate_group` | Either one thing recorded twice, or two things the case has not admitted might be the same. Both distort the chart |
| `singleton-group` | A `candidate_group` with one member | A group of one asserts nothing. Either the ambiguity resolved and the field should be null on a new row, or the sibling candidate was never recorded |
| `merge-unlinked` | An id superseded inside a group with no linking datapoint named in `notes` | A wrong merge is the most damaging error this plugin makes: it is how an uninvolved person acquires someone else's history |
| `bad-grade` | A grade outside the Admiralty set | Ungraded material is not a finding |
| `bad-type` | A `type` outside the canonical selector vocabulary | A synonym or a plural breaks every grep, pivot and join in the plugin |
| `no-sources` | Empty `sources` | Provenance or it does not exist, checked mechanically |
| `bad-record` | Malformed JSON, a bad id, a bad `candidate_group`, or a missing required key | The row cannot be validated at all, so it cannot be trusted |

A pass clears the mechanical checks only. It says nothing about whether a merge was *justified* —
that is the linking-datapoint tier table in `${CLAUDE_PLUGIN_ROOT}/references/40-analysis.md`, and
it is a human judgement.

## 2. Render

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/graph.py" "<CASE_DIR>"                  # mermaid
python "${CLAUDE_PLUGIN_ROOT}/scripts/graph.py" "<CASE_DIR>" --format dot
python "${CLAUDE_PLUGIN_ROOT}/scripts/graph.py" "<CASE_DIR>" --format text
```

| Format | Use it for |
|---|---|
| `mermaid` | Anything a human reads: chat, `findings.md`, report section 8, an artifact. Paste the source inside a ```mermaid fence |
| `dot` | Handing to Graphviz for a large graph, or to the `diagram` skill for an editable chart |
| `text` | A terminal check of nodes, groups, edges and events with no renderer in the loop |

The script prints its legend as comment lines inside the source, so a redirected file stays valid.
**Reproduce the legend as visible text under the chart** wherever the chart is shown to a reader —
a rendered diagram drops its comments, and the styling is meaning, not decoration:

- Shape is the entity class: person/account, company, infrastructure, place, artifact, crypto,
  transport, event.
- Border weight is the confidence band — thick strong, plain moderate, dashed weak. The Admiralty
  pair sits on every node and is authoritative; the band is a projection of it and never collapses
  reliability and credibility into one score.
- A `candidate_group` renders as a cluster labelled `UNRESOLVED`, with dashed member edges labelled
  `candidate group, unresolved`. Never redraw it as one node, never introduce a single name that
  stands for both members, and never carry an attribute of one member onto another.

An entity referenced by `attributed_to` or by an event's `actor_entity` that has no row of its own
renders as a flagged node reading `referenced, no entity row`. That is a collection gap showing up
in the chart; write it to `gaps.md` rather than deleting the reference.

On a large case — roughly 150+ entities, where the chart has stopped being readable and the
questions have turned structural (which sub-network, shortest chain between two entities, which
node is the hub) — `${CLAUDE_PLUGIN_ROOT}/references/60-graphify.md` documents an optional
third-party graph backend. It is optional, it is not part of this plugin, and it answers nothing
about grades or unresolved identities. Below that size it is the wrong call; this chart is enough.

## 3. Into the report

Section 8 of `${CLAUDE_PLUGIN_ROOT}/assets/report-template.md` holds the chart. Paste the generated
source over the template's example block — the checklist item "section 8 contains the generated
chart, not the template example" is checked at delivery. Edge labels in the report carry a grade
and a finding id, or the edge comes out; the raw chart carries relationship types only, so add the
grades when the chart lands in a deliverable.

## 4. Refusals

- **No chart over a failing case.** Exit 1 → report the violations, render nothing. Offer to work
  the fixes with the user instead; do not render "just to look at it".
- **No hand-editing the source to merge two nodes.** If the case cannot merge them, neither can the
  picture. Resolution is a new `entities.jsonl` row naming the datapoint.
- **No chart of a case with no scope.** Without `scope.md` there is no recorded question, and a
  graph of everything collected is the dossier the intake gate exists to prevent.
- Redact per `${CLAUDE_PLUGIN_ROOT}/references/50-reporting.md` before a chart leaves the case
  directory: node labels carry raw selector values. Entity ids are never redacted.
