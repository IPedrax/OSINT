# FORMAT.md — verified file formats for this plugin

Ground truth for every file format this repo uses. Every fact is cited. Anything not cited is
marked `UNVERIFIED` and must not be relied on.

## Source authority

| Tag | Source | Notes |
|---|---|---|
| `[PR]` | `https://code.claude.com/docs/en/plugins-reference` | Fetched 2026-07-27 |
| `[PM]` | `https://code.claude.com/docs/en/plugin-marketplaces` | Fetched 2026-07-27 |
| `[SK]` | `https://code.claude.com/docs/en/skills` | Fetched 2026-07-27 |
| `[SA]` | `https://code.claude.com/docs/en/sub-agents` | Fetched 2026-07-27 |
| `[ECC]` | `~/.claude/plugins/cache/ecc/ecc/2.0.0/` | Working install, inspected locally |
| `[PT]` | `~/.claude/plugins/cache/ponytail/ponytail/4.8.4/` | Working install, inspected locally |
| `[AAS]` | `~/.claude/plugins/marketplaces/anthropic-agent-skills/` | Working install, inspected locally |
| `[CLI]` | `claude plugin validate` / `claude plugin list --json --available`, Claude Code **2.1.71** on this machine | Runtime behavior, run against these manifests |

`[CLI]` outranks the docs where they disagree. The docs describe the current release; this machine
runs 2.1.71. See section 8.1.

**Doc host moved.** `docs.claude.com/en/docs/claude-code/<page>` returns `301` to
`code.claude.com/docs/en/<page>`. `slash-commands` no longer exists as its own page; it now
resolves to the `skills` page. Cite the new host.

---

## 1. `.claude-plugin/plugin.json`

Location is fixed: `<plugin-root>/.claude-plugin/plugin.json`. Only this file belongs in
`.claude-plugin/`; every component directory sits at the plugin root `[PR]`.

The manifest is **optional**. Omit it and components are auto-discovered from default
locations, with the plugin name derived from the directory name `[PR]`.

### Keys

| Key | Type | Req | Effect |
|---|---|---|---|
| `name` | string | Yes (if manifest present) | Kebab-case, no spaces. The namespace prefix for every component. The only required key `[PR]` |
| `$schema` | string | **Do not use** | Docs call it an ignored editor-validation field `[PR]`. On CC 2.1.71 it is a **hard validation error**: `root: Unrecognized key: "$schema"`, `Validation failed` `[CLI]`. Omitted from this plugin |
| `displayName` | string | No | UI label. Not used for namespacing. Requires CC v2.1.143+ `[PR]` |
| `version` | string | No | Semver. **Pins the cache key** — users receive changes only when this string changes. Omit and the git commit SHA is used instead `[PR]` |
| `description` | string | No | Shown in `/plugin` and marketplace listings `[PR]` |
| `author` | object | No | `{name, email?, url?}` `[PR]` |
| `homepage` | string | No | Docs URL `[PR]` |
| `repository` | string | No | Source URL `[PR]` |
| `license` | string | No | SPDX identifier `[PR]` |
| `keywords` | array | No | Discovery tags `[PR]` |
| `defaultEnabled` | boolean | No | `false` installs the plugin disabled. Requires CC v2.1.154+ `[PR]` |
| `skills` | string\|array | No | Extra skill dirs. **Adds to** the default `skills/` scan `[PR]` |
| `commands` | string\|array | No | **Replaces** the default `commands/` scan `[PR]` |
| `agents` | string\|array | No | **Replaces** the default `agents/` scan `[PR]` |
| `hooks` | string\|array\|object | No | Path or inline config `[PR]` |
| `mcpServers` | string\|array\|object | No | Path or inline config `[PR]` |
| `lspServers`, `outputStyles`, `workflows` | string\|array | No | Not used by this plugin `[PR]` |
| `userConfig` | object | No | Values prompted at enable time; `{type,title,description}` required per key `[PR]` |
| `dependencies` | array | No | Other plugins required, optional semver constraint `[PR]` |
| `experimental.themes`, `experimental.monitors` | string\|array | No | Schema may change between releases `[PR]` |

Docs state that unrecognized top-level keys are **ignored** at load and reported as warnings by
`claude plugin validate`, and that only wrong *types* are hard errors `[PR]`. **That is not true on
CC 2.1.71**, where an unrecognized key fails validation outright `[CLI]`. Treat the key table above
as a closed set until the floor version is known.

### Verified example

`[PT]` `ponytail/.claude-plugin/plugin.json`, a working install:

```json
{
  "name": "ponytail",
  "version": "4.8.4",
  "description": "Lazy senior dev mode. Forces the simplest, shortest solution that actually works: YAGNI, stdlib first, no unrequested abstractions.",
  "author": {
    "name": "Dietrich Gebert",
    "url": "https://github.com/DietrichGebert"
  },
  "hooks": "./hooks/claude-codex-hooks.json"
}
```

### Gotchas

- All component paths must be **relative and start with `./`** `[PR]`. Absolute paths and `../`
  traversal fail: installed plugins are copied into `~/.claude/plugins/cache` and anything
  outside the plugin root is not copied `[PR]`.
- Declaring `commands` or `agents` *replaces* the default directory. To keep the default and
  add more, list it: `"commands": ["./commands/", "./extras/"]` `[PR]`.
- Do not declare a component path for a directory you have not created. A `commands` path that
  exists but holds no `.md` files logs `Warning: No commands found in plugin ... custom directory` `[PR]`.
- Setting `version` means you **must** bump it on every release. Pushing commits without a bump
  leaves users on the cached copy and `/plugin update` reports "already at the latest version" `[PR]`.

---

## 2. `.claude-plugin/marketplace.json`

Location: `<repo-root>/.claude-plugin/marketplace.json` `[PM]`.

### Top level

| Key | Type | Req | Effect |
|---|---|---|---|
| `name` | string | Yes | Kebab-case. Public-facing: users type `plugin@<this>`. One marketplace per name per user; re-adding the same name replaces the first `[PM]` |
| `owner` | object | Yes | `{name}` required; `email`, `url` optional `[PM]` |
| `plugins` | array | Yes | Plugin entries `[PM]` |
| `$schema` | string | No | Ignored at load. No canonical marketplace schema URL is documented — `UNVERIFIED` `[PM]`. Unlike `plugin.json`, `marketplace.json` tolerates it on 2.1.71 `[PT]` |
| `description` | string | No | Docs call this the current spelling with `metadata.description` as back-compat `[PM]`. **On 2.1.71 it is the reverse:** a top-level-only `description` warns `metadata.description: No marketplace description provided`; moving it under `metadata` passes clean `[CLI]`. Use `metadata.description` |
| `version` | string | No | Manifest version; also accepted under `metadata` `[PM]` |
| `metadata.pluginRoot` | string | No | Base dir prepended to relative plugin sources `[PM]` |
| `allowCrossMarketplaceDependenciesOn` | array | No | Marketplaces this one's plugins may depend on `[PM]` |
| `renames` | object | No | Former name to current name, or `null` if removed. CC v2.1.193+ `[PM]` |

### Plugin entry

Required: `name`, `source`. An entry may also carry **any** `plugin.json` metadata key, plus the
marketplace-only keys `source`, `category`, `tags`, `strict`, `relevance`, `defaultEnabled` `[PM]`.

### Source types

| Source | Shape | Fields |
|---|---|---|
| Relative path | string, must start with `./` | Resolved against the **marketplace root**, not `.claude-plugin/`. No `..` `[PM]` |
| `github` | object | `repo` (`owner/repo`), `ref?`, `sha?` `[PM]` |
| `url` | object | `url` (git URL), `ref?`, `sha?` `[PM]` |
| `git-subdir` | object | `url`, `path`, `ref?`, `sha?`. Sparse clone `[PM]` |
| `npm` | object | `package`, `version?`, `registry?` `[PM]` |

When both `ref` and `sha` are set, `sha` is the effective pin `[PM]`.

### Self-hosting: the repo is both plugin and marketplace

`"source": "./"` points the entry at the marketplace root, so one repo ships one plugin and its
own catalog. Verified in three working installs: `[ECC]`, `[PT]`, `[AAS]`.

```json
{
  "name": "ponytail",
  "owner": { "name": "Dietrich Gebert", "url": "https://github.com/DietrichGebert" },
  "plugins": [
    {
      "name": "ponytail",
      "description": "Forces the laziest solution that works. YAGNI, stdlib first, one line over fifty.",
      "source": "./",
      "category": "productivity"
    }
  ]
}
```

### Gotchas

- **`source: "./"` changes `skills` path semantics.** Everywhere else `skills` *adds* to the
  default `skills/` scan. For an entry whose source resolves to the marketplace root, listing
  specific subdirectories **replaces** the default scan, and the listed paths become the complete
  set. Listing `./skills/` itself keeps the full scan. If none of the listed paths exist, the
  default scan runs `[PM]`. This plugin therefore declares **no** `skills` key in either manifest.
- `strict` defaults to `true`, meaning `plugin.json` is the authority and the marketplace entry
  may supplement it. `strict: false` makes the marketplace entry the *entire* definition, and a
  `plugin.json` that also declares components is then a load-failing conflict `[PM]`.
- Version resolution order for the *effective* version: `plugin.json` `version`, then marketplace
  entry `version`, then git commit SHA, then `unknown` `[PM]`. But the **pre-install** listing reads
  the marketplace entry only: with no `version` there, `claude plugin list --json --available`
  reports `version: null` for this plugin even though `plugin.json` sets `0.1.0`; adding it to the
  entry makes the listing report `0.1.0` `[CLI]`. Both manifests therefore carry the version, and
  **both must be bumped together** on every release.
- Relative-path sources do **not** resolve if a user adds the marketplace by direct URL to the
  `marketplace.json` file, because only that file is downloaded. Git-source or local-directory
  adds work `[PM]`.
- Reserved marketplace names cannot be used, including `anthropic-agent-skills`,
  `claude-plugins-official`, `agent-skills`, `first-party-plugins`, `healthcare`, and names that
  impersonate official sources. Reserved names are re-checked on every load `[PM]`.

### Install flow

```
/plugin marketplace add ./OSINT        # or owner/repo, or a git URL
/plugin install osint@osint
/reload-plugins
```

`[PM]`. Non-interactive equivalents: `claude plugin install <plugin>@<marketplace> [-s user|project|local]` `[PR]`.

---

## 3. `skills/<name>/SKILL.md`

Default location `skills/`, auto-discovered, no declaration needed `[PR]`. A skill is a
**directory** containing `SKILL.md` plus optional supporting files `[SK]`.

**Custom commands have been merged into skills.** `commands/deploy.md` and
`skills/deploy/SKILL.md` both create `/deploy` and behave the same. Skills add supporting files,
invocation control, and model-initiated loading `[SK]`.

### Frontmatter

YAML between `---` markers. **All fields are optional**; only `description` is recommended `[SK]`.

| Key | Req | Effect |
|---|---|---|
| `name` | No | For a **plugin** skill, sets the last segment of the command name. Defaults to the directory name `[SK]` |
| `description` | Recommended | What it does and when to use it. Drives model-initiated loading. `description` + `when_to_use` are **truncated at 1,536 characters** in the skill listing — put the key use case first `[SK]` |
| `when_to_use` | No | Extra trigger phrases, appended to `description`; counts toward the 1,536 cap `[SK]` |
| `argument-hint` | No | Autocomplete hint, e.g. `[case-slug]` `[SK]` |
| `arguments` | No | Named positional args for `$name` substitution. Space-separated string or YAML list `[SK]` |
| `disable-model-invocation` | No | `true` stops Claude from auto-loading it; manual `/name` only. Also stops preloading into subagents. Default `false` `[SK]` |
| `user-invocable` | No | `false` hides it from the `/` menu. Default `true` `[SK]` |
| `allowed-tools` | No | Pre-approved tools for the invoking turn only. Space/comma string or YAML list `[SK]` |
| `disallowed-tools` | No | Tools removed while the skill is active `[SK]` |
| `model` | No | Model for the rest of the turn; or `inherit` `[SK]` |
| `effort` | No | `low`\|`medium`\|`high`\|`xhigh`\|`max` `[SK]` |
| `context` | No | `fork` runs it in a forked subagent context `[SK]` |
| `agent` | No | Which subagent type to use when `context: fork` `[SK]` |
| `background` | No | Only with `context: fork`. `false` waits for the result in-turn. Default `true`, CC v2.1.218+ `[SK]` |
| `hooks` | No | Hooks scoped to this skill's lifecycle `[SK]` |
| `paths` | No | Globs limiting automatic activation to matching files `[SK]` |
| `shell` | No | `bash` (default) or `powershell` for inline shell injection `[SK]` |

Booleans accept `yes`/`no`/`on`/`off`/`1`/`0` in any case as well as `true`/`false`, in CC
v2.1.218+ `[SK]`, `[PR]`.

### Verified example

`[PT]` `ponytail/skills/ponytail-audit/SKILL.md`:

```yaml
---
name: ponytail-audit
description: >
  Whole-repo audit for over-engineering. Like ponytail-review, but scans the
  entire codebase instead of a diff: a ranked list of what to delete, simplify,
  or replace with stdlib/native equivalents. Use when the user says "audit this
  codebase", "audit for over-engineering", "what can I delete from this repo",
  "find bloat", "ponytail-audit", or "/ponytail-audit". One-shot report, does
  not apply fixes.
---
```

Note the YAML folded scalar (`>`) for a multi-line description, and the trigger phrases written
verbatim as a user would type them.

### Namespacing and invocation

| Layout | Command name |
|---|---|
| `<plugin>/skills/<dir>/SKILL.md` | Frontmatter `name`, else the directory name, prefixed by plugin: `/osint:osint-infra` `[SK]` |
| `<plugin>/commands/<file>.md` | File name without extension, prefixed by plugin: `/osint:osint-scope` `[SK]`, `[ECC]` |
| `<plugin>/SKILL.md` at plugin root | Frontmatter `name`, plugin directory name as fallback `[PR]` |

In a plugin skill the frontmatter `name` replaces only the **last segment**; the plugin prefix
stays. Bare `/<name>` also works unless another command already owns it. Before v2.1.216 the
frontmatter name replaced the whole command name `[SK]`.

Plugin skills cannot collide with personal or project skills because of the namespace `[SK]`.

### Supporting files

`references/`, `assets/`, `scripts/`, templates — all optional, none auto-loaded. Claude reads
them **only if `SKILL.md` names them and says when to load them** `[SK]`. This is the whole
mechanism behind CONTRACT.md's reference-index requirement.

Substitutions available inside skill content:

| Placeholder | Resolves to |
|---|---|
| `${CLAUDE_SKILL_DIR}` | The directory holding this `SKILL.md`. For plugin skills, the skill's own subdirectory, **not** the plugin root `[SK]` |
| `${CLAUDE_PLUGIN_ROOT}` | The plugin's install directory. Substitutes anywhere in skill and agent content `[PR]` |
| `${CLAUDE_PROJECT_DIR}` | Project root `[PR]`, `[SK]` |
| `$ARGUMENTS`, `$ARGUMENTS[N]`, `$N`, `$name` | Invocation arguments. If `$ARGUMENTS` is absent, args are appended as `ARGUMENTS: <value>` `[SK]` |

`${CLAUDE_PLUGIN_ROOT}` **changes on every plugin update**. Never write state there; use
`${CLAUDE_PLUGIN_DATA}` (`~/.claude/plugins/data/<id>/`) for anything that must survive `[PR]`.

### Gotchas

- Once a skill loads, its body **stays in context across turns**. Every line is a recurring
  token cost, which is why CONTRACT.md caps SKILL.md length and pushes detail into `references/` `[SK]`.
- Skill *descriptions* are always-on context even when the skill never fires. `claude plugin
  details osint` reports the always-on and on-invoke token cost per component `[PR]`.
- Live change detection covers `SKILL.md` text only. Changes to `hooks/`, `.mcp.json`, `agents/`,
  and `output-styles/` need `/reload-plugins` `[SK]`, `[PR]`.

---

## 4. `commands/<name>.md`

A flat markdown file. Same frontmatter set as skills `[SK]`. No supporting-file directory, no
progressive disclosure — that is the reason to prefer `skills/` for anything with references.
Docs recommend `skills/` for new plugins `[PR]`.

Verified example, `[ECC]` `ecc/commands/code-review.md`:

```yaml
---
description: Code review — local uncommitted changes or GitHub PR (pass PR number/URL for PR mode)
argument-hint: [pr-number | pr-url | blank for local review]
---
```

That file is installed and live on this machine as `/ecc:code-review` with exactly that
description, which confirms both the frontmatter shape and the `<plugin>:<filename>` namespacing.
Note the absence of a `name` key: for a `commands/*.md` file the **file name** is the command name.

### Naming collision — read before creating files

`commands/<x>.md` and `skills/<x>/SKILL.md` inside the same plugin both resolve to `/osint:<x>`.
PLAN.md section 1 specifies **both** `commands/osint.md` and `skills/osint/SKILL.md`, which
collide. Docs state that where a skill and a command share a name, the skill takes precedence
`[SK]`, so the command file would be shadowed — silently, with no error. Rename one side. Every
other PLAN.md pair is distinct.

---

## 5. `agents/<name>.md`

Default location `agents/`, auto-discovered `[PR]`. Markdown body is the agent's system prompt.

| Key | Req | Effect |
|---|---|---|
| `name` | Yes | Lowercase and hyphens. Hooks receive it as `agent_type`. **Filename need not match** `[SA]` |
| `description` | Yes | When Claude should delegate to it `[SA]` |
| `tools` | No | Allowlist. Inherits all subagent-available tools if omitted. If no entry resolves to a real tool the subagent fails to launch `[SA]` |
| `disallowedTools` | No | Denylist applied to the inherited or specified set `[SA]` |
| `model` | No | `sonnet`\|`opus`\|`haiku`\|`fable`\|full model ID\|`inherit`. Default `inherit` `[SA]` |
| `effort` | No | `low`\|`medium`\|`high`\|`xhigh`\|`max` `[SA]` |
| `maxTurns` | No | Turn ceiling before the subagent stops `[SA]` |
| `skills` | No | Skills preloaded into the subagent's context in full at startup `[SA]` |
| `memory` | No | `user`\|`project`\|`local` persistent memory scope `[SA]` |
| `background` | No | `true` always runs it as a background task `[SA]` |
| `isolation` | No | Only valid value is `worktree` `[PR]`, `[SA]` |

**Not supported for plugin-shipped agents, for security reasons:** `hooks`, `mcpServers`,
`permissionMode`. They are silently ignored `[PR]`, `[SA]`.

Verified example, `[ECC]` `ecc/agents/architect.md`:

```yaml
---
name: architect
description: Software architecture specialist for system design, scalability, and technical decision-making. Use PROACTIVELY when planning new features, refactoring large systems, or making architectural decisions.
tools: ["Read", "Grep", "Glob"]
model: opus
---
```

`tools` accepts a YAML list as above `[ECC]` or a comma-separated string, e.g.
`tools: Read, Grep, Glob, Bash` `[SA]`.

Plugin agents appear in the `@`-mention typeahead under the scoped name `osint:osint-collector` `[PR]`.

Background subagents keep only a fixed built-in tool subset regardless of the `tools` field:
`Read`, `Grep`, `Glob`, `Bash`, `PowerShell`, `Edit`, `Write`, `NotebookEdit`, `WebFetch`,
`WebSearch`, `TodoWrite`, `Skill`, `ToolSearch`, `EnterWorktree`, `ExitWorktree`, `Monitor`,
`TaskStop`, `SendMessage`, `Artifact`. Everything else is stripped, with no error unless the
list resolves to nothing `[SA]`. A collector agent that relies on any other built-in tool must
not run in the background.

---

## 6. `hooks/hooks.json`

Default location `hooks/hooks.json`, auto-discovered; may instead be declared inline in
`plugin.json` `[PR]`.

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"${CLAUDE_PLUGIN_ROOT}\"/scripts/format-code.sh"
          }
        ]
      }
    ]
  }
}
```

`[PR]`. Hook types: `command`, `http`, `mcp_tool`, `prompt`, `agent` `[PR]`.

Events relevant to this plugin, verbatim from `[PR]`:

| Event | Fires |
|---|---|
| `SessionStart` | When a session begins or resumes |
| `UserPromptSubmit` | When a prompt is submitted, before Claude processes it |
| `PreToolUse` | Before a tool call executes. Can block it |
| `PostToolUse` | After a tool call succeeds |
| `SubagentStart` / `SubagentStop` | When a subagent is spawned / finishes |
| `Stop` | When Claude finishes responding |
| `SessionEnd` | When a session terminates |

Event names are case-sensitive: `PostToolUse`, not `postToolUse` `[PR]`.

### Gotchas

- Shell-form hook commands must double-quote the path variable: `"${CLAUDE_PLUGIN_ROOT}"/scripts/x.sh`.
  Prefer exec form with `args` so each path is one argument with no quoting `[PR]`.
- `${user_config.*}` is **rejected** in any field that runs through a shell — hook shell commands,
  monitor commands, MCP `headersHelper`. Read `CLAUDE_PLUGIN_OPTION_<KEY>` from the hook
  environment instead `[PR]`.
- Hooks run unsandboxed at the user's trust level. A hook that blocks writes outside `cases/`
  (PLAN.md section 1) is a `PreToolUse` matcher on `Write|Edit`.

---

## 7. Auto-discovery summary

Nothing in the table below needs declaring in `plugin.json` `[PR]`:

| Component | Default path | Declared? |
|---|---|---|
| Manifest | `.claude-plugin/plugin.json` | n/a, optional |
| Skills | `skills/<name>/SKILL.md` | Auto |
| Commands | `commands/<name>.md` | Auto |
| Agents | `agents/<name>.md` | Auto |
| Hooks | `hooks/hooks.json` | Auto |
| MCP servers | `.mcp.json` | Auto |
| Executables added to Bash `PATH` | `bin/` | Auto |
| Skill support files | anywhere under the skill dir | Referenced from `SKILL.md` only |

Consequence for this repo: `plugin.json` carries metadata only. `skills/osint/assets/` and
`skills/osint/scripts/` are invisible to Claude Code until `SKILL.md` names them.

CC v2.1.140+ warns in `claude plugin list` and the `/plugin` detail view when a plugin has both a
default folder and a manifest key that replaces it — the folder is ignored but the plugin still
loads `[PR]`.

---

## 8. Validation

```
claude plugin validate .
claude plugin list --json
claude --debug
```

`validate` checks `plugin.json`, skill/agent/command frontmatter, and `hooks/hooks.json` for
syntax and schema errors. The docs also describe `claude plugin details <name>`, which prints the
component inventory and projected token cost `[PR]` — but that subcommand **does not exist on
2.1.71**: `error: unknown command 'details'` `[CLI]`. Use `claude plugin list --json` there.

`--strict`, which the docs describe for CI use, **does not exist on 2.1.71**: it exits with
`error: unknown option '--strict'` `[CLI]`. Do not put it in a build script yet.

`validate` picks one manifest per invocation. Pointed at this repo it validates
`marketplace.json` and never mentions `plugin.json`, so a broken `plugin.json` passes unnoticed.
To check the plugin manifest, copy it to a scratch directory that has no `marketplace.json` and
validate that `[CLI]`. Both manifests in this repo pass, and the entry resolves as
`osint | ./ | 0.1.0` `[CLI]`.

### 8.1 Installed version is behind the docs

This machine runs Claude Code **2.1.71** `[CLI]`. The docs carry version gates above that floor,
so the following are documented but **unavailable here**. Do not use them, and do not assume a
reader has them:

| Feature | Needs | Source |
|---|---|---|
| `displayName` in either manifest | 2.1.143 | `[PR]`, `[PM]` |
| `defaultEnabled` | 2.1.154 | `[PR]`, `[PM]` |
| `relevance` in a marketplace entry | 2.1.152 | `[PM]` |
| `renames` map | 2.1.193 | `[PM]` |
| Boolean frontmatter as `yes`/`no`/`on`/`off`/`1`/`0` | 2.1.218 | `[SK]`, `[PR]` |
| `background: false` on a `context: fork` skill | 2.1.218 | `[SK]` |
| Frontmatter `name` replacing only the last command segment | 2.1.216 | `[SK]` |
| Directory-qualified nested skill names | 2.1.203 | `[SK]` |
| `claude plugin prune` | 2.1.121 | `[PR]` |
| `claude plugin validate --strict` | unknown, not in 2.1.71 | `[CLI]` |
| `claude plugin details <name>` | unknown, not in 2.1.71 | `[CLI]` |

Two consequences for authoring:

- Write booleans as `true` / `false` only.
- Set frontmatter `name` **equal to the skill's directory name**. Before 2.1.216 a differing
  `name` replaced the whole command name and dropped the plugin prefix from the menu `[SK]`; when
  the two match, old and new behavior are identical. CONTRACT.md section 2 already requires this,
  and it is the right call for exactly this reason.

---

## 9. Corrections to CONTRACT.md section 2

CONTRACT.md is binding on style and discipline. On the mechanics of frontmatter it is slightly
off, in one direction that is harmless and one that is limiting.

1. **"starts with exactly this frontmatter" over-states the requirement.** Every skill
   frontmatter field is optional; `description` is documented as *Recommended*, not required, and
   `name` defaults to the directory name `[SK]`. The `name` + `description` pair CONTRACT.md
   mandates is valid and is the right convention here — in a plugin skill `name` sets the last
   command segment, so declaring it makes the command name independent of the install path. Keep
   writing it. Just do not read "exactly" as a schema constraint.

2. **The 1,536-character cap is unstated and binding.** `description` plus `when_to_use` is
   truncated at 1,536 characters in the skill listing `[SK]`. A description written to be matched
   on trigger vocabulary can hit that. Put the primary use case and the strongest trigger phrases
   first.

3. **`disable-model-invocation` is required to express PLAN.md's own design.** PLAN.md section 1
   calls `skills/osint/SKILL.md` "the only one that auto-triggers broadly". The only way to stop
   a department skill from auto-firing is `disable-model-invocation: true` `[SK]`. CONTRACT.md
   section 2 permits keys that this file documents as valid, so the full table in section 3 above
   is the authority. Recommended set for this plugin: `name`, `description` everywhere;
   `disable-model-invocation` on department skills; `argument-hint` where a skill takes a case
   slug or selector; `allowed-tools` nowhere, since an OSINT plugin should not pre-approve tools.

4. **`when_to_use` is a better home for trigger phrases than a bloated `description`.** It is a
   real, documented key `[SK]`. CONTRACT.md section 2 forbids it by omission; it should not.

Not a section 2 issue, but the same class of defect — see section 4 above: PLAN.md section 1
specifies both `commands/osint.md` and `skills/osint/SKILL.md`, which resolve to the same
`/osint:osint` and silently shadow each other.

---

## 10. Unverified

- Neither `$schema` URL was fetched. `[PT]` ships
  `https://anthropic.com/claude-code/marketplace.schema.json` in `marketplace.json`;
  `[PR]` quotes `https://json.schemastore.org/claude-code-plugin-manifest.json` for `plugin.json`.
  Both are `UNVERIFIED` as live URLs, and the second is rejected outright at 2.1.71 `[CLI]`, so
  this plugin uses neither.
- The Claude Code version floor this plugin actually needs. 2.1.71 accepts both manifests `[CLI]`;
  the per-field gates in section 8.1 are from the docs, not tested downward.
- Whether a `commands/*.md` file and a same-named `skills/<name>/SKILL.md` inside one **plugin**
  produce a warning or fail silently. The precedence rule is documented for the personal and
  project levels `[SK]`; the plugin-internal case is inferred, not confirmed.
- Every hook event name in section 6 is quoted from `[PR]` and none were fired on 2.1.71. Some
  events in the full docs table are newer than this install; confirm an event fires before
  depending on it.
