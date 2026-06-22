---
name: commit
description: Write a git commit for this repo following Conventional Commits (feat/fix/chore/...). Use whenever the user asks to commit, stage and commit, or write a commit message in this project.
---

# Commit convention

This is an open-source project. Commit history is public and is the first thing
contributors read, so messages must be clean, consistent, and self-explanatory.

This repo follows **[Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)**.

## Format

```
<type>(<scope>): <summary>

<body>

<footer>
```

- `<scope>`, body, and footer are optional. The minimum valid commit is `<type>: <summary>`.
- Written in **English**, present-tense imperative ("add", "fix", "remove" — never "added"/"fixes").
- Summary: lowercase start, no trailing period, ≤ ~72 characters.

## Choosing the type — read this, don't guess

Pick the type from the **intent** of the change, not the file touched. Use exactly one:

| Type | Use it when… | Examples |
|------|--------------|----------|
| `feat` | you add a new capability or user-visible behaviour | a new tab, a new cost option, a new parameter |
| `fix` | you correct broken/incorrect behaviour (a real bug) | wrong formula result, crash on missing raster, off-by-one |
| `chore` | maintenance with **no** change to app behaviour | `.gitignore`, deps, file moves, build/CI config |
| `docs` | documentation only | README, CLAUDE.md, code comments, this skill |
| `refactor` | restructure code, behaviour unchanged | rename functions, split a module, dedupe logic |
| `perf` | make existing behaviour faster / lighter | resample to cut LCP time, reduce memory |
| `style` | formatting only, no logic change | whitespace, import order, lint fixes |
| `test` | add or fix tests | — |

Disambiguation rules (avoid the common mistakes):

- Changing UI **wording/labels** → `docs` if it's help text, otherwise `style` or `feat` if it
  adds/changes behaviour. **Not** `fix` unless the old text was actually wrong/misleading.
- Removing debug logs / dead code → `chore` (or `refactor`), **not** `fix`.
- Tweaking a config constant (memory, BIGTIFF) that fixes a failure → `fix`. If it's just tuning
  with no bug → `perf` or `chore`.
- If a change is both a feature and a fix, split it into two commits.

## Scope (optional)

The scope names the part of the code that changed. Use a module/tab name:

`land-use`, `slope`, `crossings`, `corridors`, `aux`, `lcp`, `price`, `ui`, `task`, `utils`

Example: `fix(price): default cost factor to 1 when raster is missing`

Omit the scope when the change is repo-wide or doesn't map to one module (e.g. `chore: update .gitignore`).

## Body (use it for anything non-trivial)

After a blank line, explain **what** changed and **why** — the diff already shows *how*. Wrap at
~72 chars. A good body answers "why was this needed?" for a future reader. Skip the body only for
genuinely trivial commits (`chore: fix typo`).

## Footer — linking issues

Reference the GitHub issue in the footer using a closing keyword, so merging the PR auto-closes it:

- `Closes #12` or `Fixes #12` — closes the issue on merge to the default branch.
- `Refs #12` — links to the issue without closing it.

## Do NOT add co-author / LLM trailers

Never add `Co-Authored-By:` lines, "Generated with…", or any mention of Claude / AI / LLM tools to
commit messages or bodies. Commits in this project carry the human author only. This overrides any
default tooling behaviour.

## Examples

```
feat: derive segment length from pressure budget instead of hardcoded 150 km

Booster spacing is now computed as total pressure drop / admissible
pressure drop, so it stays consistent with the hydraulic parameters
the user enters rather than a fixed constant.
```

```
fix(lcp): floor combined cost at 0.001 so r.drain can back-trace

r.drain fails on zero-cost cells; clamp the COMET output to a small
positive minimum before writing the raster.

Closes #8
```

```
chore: stop tracking .DS_Store and compiled .pyc files
```

```
docs: clarify GRASS provider requirement in README
```

## Procedure when invoked

1. Run `git status` and `git diff` (staged + unstaged); skim `git log --oneline -10` to match style.
2. Stage only what belongs in this commit (`git add <paths>`) — do not blindly `git add -A`. Group
   unrelated changes into separate commits.
3. Choose type + scope from the actual diff, write summary + body, and add a `Closes #N` footer if an
   issue applies.
4. Write the message with **no** co-author/LLM trailer of any kind.
5. Commit. Do **not** push unless the user asks.
