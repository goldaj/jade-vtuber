> Note d’actualité — document historique. Les décisions ultérieures du propriétaire et les instructions actuelles du dépôt priment ; consulter l’index des conversations.

# Jade / future public repository: Codex handoff

Created 28 October 2026. This is an isolated add-on to PR #1:
source branch codex/chat-gpt6-jade-rebuild at 410404a39fbbdecdcb7a6befc5aac47bff598ab6.
New branch: research/gpt6-jade-publication-readiness-20261028; draft PR #2.

## The owner explicitly requires
- Prepare everything feasible NOW for a possible public repository LATER.
- **Preserve all existing information, tokens, branches, code and artistic assets TODAY.**
- Codex will remove sensitive information later, after external backups and owner approval.
- Remain modular. OpenAI-only STT/TTS; keep LLM provider swappable and all live connectors opt-in.
- Do not disrupt Codex's refactor branch or other simultaneous work.

## Implemented (inspect actual diff before assimilation)
- src/utility/public_profile.py and config/profiles/*.toml: strictly allowlisted, optional non-secret profiles, preserving legacy defaults.
- src/utility/private_config.py: precedence process environment > existing external JADE_SECRETS_FILE dotenv > public profile > code defaults. Existing Twitch refresh storage preserved.
- src/jade_runtime/assets.py and main.py: JADE_PROMPT_FILE external persona, or JADE_ASSETS_ROOT/prompts/chat.txt; old prompt_chat.txt default unchanged. An explicit missing private file errors instead of falling back silently.
- tools/jade_publication_audit.py: offline current tracked-file basic scanning, optional all-reachable Git object path hygiene; neither prints secret values nor certifies public readiness.
- tools/jade_publication_export.py: optional private, no-history, allowlist-based *preview*, replacing original prompt and README with neutral templates. Must not publish automatically.
- .gitignore: additional safety patterns for future local private config and assets; does not remove any previously tracked files.
- New tests and a separate GitHub Actions workflow. Do not claim production connection tested merely because synthetic CI is green.

## Documentation
1. 01-SENSITIVE-INVENTORY.md: sensitivity classes, current/history/branch risk, untouched sources.
2. 02-CONFIG-AND-MODULARITY.md: layer precedence, external asset path, guarantees/limitations.
3. 03-CODEX-MIGRATION-PLAN.md: phase-by-phase no-loss public preparation.
4. 04-RELEASE-GATES.json: machine-readable status, ALL public-release approval gates unresolved.
5. README_PUBLIC_TEMPLATE.md: safe readme for a *snapshot only*, not the original repository.

## Explicit non-actions
No deletion of any confidential values or historic commits; no rewriting old branches,
no revoking actual provider credentials, no changing repository visibility, no
merging, no refactor-branch update, no alteration of jade-modeling/** or LFS assets,
no money/API calls, no Twitch/Discord/VTS/network access.

## Codex recovery sequence
1. Check current PR #1 state and latest refactor head and review this PR's base and delta.
2. Review/fix code tests and continue normal refactor first.
3. Run offline tests and basic scanner on the stacked branch; note that historic
   dangerous .env paths on master/speechtotext-discord remain blockers.
4. Preserve and archive secrets and art on an encrypted, access-limited medium,
   with verified manifests, WITHOUT committing backups or credential contents.
5. Perform staged migration/rotation and selective clean export per plan. Prefer
   a BRAND-NEW public repository from an audited history-free snapshot, keeping
   the current private repository as the intact historical archive.
6. Do not approve PUBLIC until rights, secret rotation, all refs/forks/cache,
   provenance, generated assets, docs, logs, CI release artifacts and fresh clone
   have been reviewed. The owner's explicit release decision is mandatory.

Test command: python -m unittest discover -s tests -v
Local hygiene: python tools/jade_publication_audit.py --working-tree
Legacy path gate: python tools/jade_publication_audit.py --history (expected BLOCKED today).
Preview dry-run: python tools/jade_publication_export.py --destination ../jade-public-preview
Preview creation (explicit, local): same command plus --write. NEVER push it automatically.

## Validation at contributor HEAD, 28 October 2026

- Static GitHub diff/paths verified. Files in this contribution are isolated.
- GitHub Actions automatically started both Jade workflows on this draft PR,
  but attempts reported failure **before exposing any executed job steps**;
  job logs endpoint returned BlobNotFound. This is NOT an assertion of test
  failure caused by the code, nor a passing CI. Tests remain **UNVERIFIED**.
- Codex: re-run locally on Python 3.11 with dependencies, inspect any traceback,
  correct bugs in this branch/after controlled import, then obtain real green
  CI on the exact final SHA. Never substitute an older green CI as evidence.
