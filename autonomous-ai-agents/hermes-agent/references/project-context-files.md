# Project Context Files

Hermes injects project-level instructions into the system prompt by reading context files from the working directory. Source of truth: `agent/prompt_builder.py::build_context_files_prompt`. **Only ONE project context TYPE is loaded per session** — the first type found wins, in this order:

| File (in priority order) | Discovery | Use when |
|---|---|---|
| `.hermes.md` / `HERMES.md` | Nearest match walking parents up to the git root (no git root → cwd only) | You want Hermes-specific rules that live above the cwd and inherit downward |
| `AGENTS.md` / `agents.md` / `AGENTS.override.md` | **Merged chain: git root → cwd** — every directory on that path contributes its first name match, labelled with its own provenance; identical content deduped. Outside a git repo (or with a single match): cwd only | Portable agent instructions that also work in Claude Code, Codex, Cursor — and monorepos (root + per-package files) |
| `CLAUDE.md` / `claude.md` | Cwd only | Same as AGENTS.md, Claude-flavored |
| `.cursorrules` / `.cursor/rules/*.mdc` | Cwd only | Migrating from Cursor |

Within a directory the first of `AGENTS.override.md` / `AGENTS.md` / `agents.md` wins — the override name lets a developer keep a personal, typically-gitignored file next to the committed instructions. `SOUL.md` (in `$HERMES_HOME`) is independent and always loaded when present — it sets the agent's identity, not project rules.

### Pick the right one

- **Use `.hermes.md`** when you want Hermes-specific behavior that lives above the cwd (root + subtree), or when you want rules to inherit from a parent directory. The parent walk stops at the git root, so a home-level `.hermes.md` won't leak into every project (a git repo's root is the boundary).
- **Use `AGENTS.md`** when the same project will also be worked on by other agents (Codex, Claude Code, OpenCode). Those tools read `AGENTS.md` too, and Hermes' merged git-root→cwd chain means a monorepo root file plus per-package files all apply to a session started in a package.
- **Nested/area files are also delivered on demand.** Loading above happens at startup; separately, `agent/subdirectory_hints.py` appends a directory's `AGENTS.override.md` / `AGENTS.md` / `agents.md` / `CLAUDE.md` / `claude.md` / `.cursorrules` **into the tool result** the first time a tool touches a path in it (`read_file`, `terminal` with `cd`/`pushd`, any tool with a `path`/`file_path`/`workdir` arg). That text lands in a tool result, not the system prompt, so prompt caching survives. Cap: 32 KiB per file (head+tail kept past that, with a WARNING in the log), ancestor walk bounded to 5 levels — which is why area files should stay well under ~8k.
- **Don't put project rules in `~/.hermes/AGENTS.md`** (or any other home-level location). When Hermes runs with that directory as cwd, the file loads — but only for that one directory. For cross-project context, use `SOUL.md` (in `$HERMES_HOME`, identity-only) or install a skill via `hermes skills install`.

### Size and truncation

Each context file is capped at 20,000 characters (`CONTEXT_FILE_MAX_CHARS`); the merged AGENTS.md chain is capped as a whole too, so a deep monorepo cannot multiply the budget. Longer files get **head + tail** truncated (the middle is dropped, with a `[...truncated...]` marker and a WARNING naming the path). For large project rules, prefer splitting into a root file plus area files (delivered on demand, see above) or skills over cramming one file.

A cwd that was chosen as a FALLBACK inside the Hermes install tree is deliberately denied system-prompt authority (so the desktop's default cwd cannot load hermes-agent's own contributor `AGENTS.md`); an explicitly configured cwd is honored verbatim.

### Security

All context files pass through the threat-pattern scanner before reaching the system prompt. Patterns matching prompt injection or promptware are replaced with a `[BLOCKED: ...]` placeholder. This means an `AGENTS.md` containing obvious injection attempts won't reach the model — the scanner blocks the content, not the file, so the rest of the file still loads.

### Disable for one session

`hermes --ignore-rules` skips auto-injection of all project context files (`.hermes.md`, `AGENTS.md`, `CLAUDE.md`, `.cursorrules`) **and** `SOUL.md` identity, plus user config, plugins, and MCP servers. Use it to isolate whether a problem is your setup or Hermes itself.

### Example: a small `.hermes.md`

```markdown
# My Project

Hermes: when working in this repo, follow these rules.

## Build
- Always run `make test` before declaring a change done.
- Use `uv run` for Python, not `pip install`.

## Style
- Prefer `pathlib.Path` over `os.path`.
- No `print()` in production code — use the `logger`.
```

That file at `/home/me/projects/myrepo/.hermes.md` is auto-loaded when Hermes runs in any subdirectory of `/home/me/projects/myrepo`, but not when it runs in `/home/me/other-project`.
