> Note d’actualité — document historique. Les décisions ultérieures du propriétaire et les instructions actuelles du dépôt priment ; consulter l’index des conversations.

# Jade modular configuration and non-loss migration

## Effective configuration hierarchy

1. OS/process environment (highest priority).
2. Selected external dotenv through JADE_SECRETS_FILE or existing private
   default path, with legacy ignored .env fallback preserved for compatibility.
3. Optional PUBLIC-safe TOML selected by JADE_PROFILE (simple slug in
   config/profiles/) or JADE_PROFILE_FILE (explicit custom path).
4. Original Settings defaults, unchanged if no profile is selected.

No profile is loaded unless explicitly selected. The public TOML whitelist
permits only model IDs, voice, timeouts, queue sizes, general feature toggles,
audio mode, subtitle path and loopback port. **No API keys, OAuth, guild/channel
identifiers, bot names, private persona or private assets** are legal profile
settings; loading an unknown/sensitive key fails closed and does not print its value.

No operation downloads assets or contacts a provider on config read. Services
stay disabled until explicit runtime flags AND connector config; --live is still
required for paid OpenAI. STT/TTS stay OpenAI-only. Do not commit token-bearing
profiles or copy JADE_SECRETS_FILE into repository root.

## Safe examples (Windows PowerShell)

  $env:JADE_PROFILE = "offline"
  python main.py
  python main.py --preflight

  $env:JADE_SECRETS_FILE = "$env:USERPROFILE\Documents\Codex-Private\ai-vtuber-project\.env"
  $env:JADE_PROFILE = "fast-openai"
  $env:JADE_PROMPT_FILE = "$env:USERPROFILE\Documents\Codex-Private\jade\prompts\character.txt"
  python main.py    # remains offline unless --live explicitly selected

Or set JADE_ASSETS_ROOT to a private folder containing prompts/chat.txt.
If both JADE_PROMPT_FILE and JADE_ASSETS_ROOT are set, JADE_PROMPT_FILE wins.
If neither is configured, the existing prompt_chat.txt is used; therefore the
refactor continues working without any migration. When an explicit private
prompt is configured but absent or empty, Jade fails rather than silently
using the public persona. Prompt contents and private path values are not logged.

## Future profile layout (not moved today)

  <public checkout>/
    src/, tests/, main.py, pyproject.toml, config/profiles/
    prompt_chat.txt   # neutral PUBLIC sample, not historical personal prompt
    README.md         # public template reviewed by owner
  <private location OUTSIDE checkout>/
    secrets/.env
    prompts/chat.txt
    art/live2d/...    # ownership/licensing review first
    instances/<device>/...  # user/device settings
    archives/...      # encrypted offline archive, not git tracked

JADE_ASSETS_ROOT is only a prompt-level runtime hook today; it does NOT relocate
the extensive jade-modeling scripts and Cubism sources automatically. Those
scripts contain their own paths/dependencies and require a separate engineering
migration before a public art-free checkout can build the model.

## Export preview, NOT publication

  python tools/jade_publication_audit.py --working-tree
  python tools/jade_publication_audit.py --history
  python tools/jade_publication_export.py --destination ../jade-public-preview
  python tools/jade_publication_export.py --destination ../jade-public-preview --write

The export is **opt-in**, no existing destination may be overwritten, no output
inside the source repo, no .git folder/history, no jade-modeling, no original
prompt_chat.txt or internal docs. It builds a neutral README and prompt and
includes a PREVIEW_NOT_FOR_PUBLICATION warning. It is not a deployable release,
does not grant a license, and does not clear all history/secrets or code rights.

## Limitations and follow-ups

- The basic content scanner recognizes common patterns and sensitive tracked
  file names, NOT arbitrary encoded/custom secrets, historical inline values,
  commit messages, screenshots, art metadata or deleted LFS blobs.
- The --history check uses reachable object path names, not secret contents.
  Run a specialist full-history scan with protected findings outside Git and
  a separate all-ref/LFS review before public publication.
- Future users need a fresh public-friendly setup guide and a separately
  approved license. Any visible personal names/IDs require independent review.
- Optional private asset plugin/registry may later enumerate persona, visual
  models, voice config and connectors, but no model art or private references
  are copied automatically in this contribution.
