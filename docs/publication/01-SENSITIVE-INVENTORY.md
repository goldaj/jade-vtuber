> Note d’actualité — document historique. Les décisions ultérieures du propriétaire et les instructions actuelles du dépôt priment ; consulter l’index des conversations.

# Jade: conservative inventory without copying actual credentials

Status at 28 October 2026, examined through GitHub metadata and selected text
in the PRIVATE repository goldaj/jade-ai-vtuber. **No credential values are copied
to this document, new files or user-facing answer.** This inventory is NOT exhaustive.
No raw Git LFS art or complete all-history secret scan was performed.

| Class | Location/example (paths, never values) | Current action | Later Codex action |
|---|---|---|---|
| Historical .env tracked | master and speechtotext-discord branches have .env in current trees; older commits also potentially | PRESERVE original private | inventory every ref and commit; rotate secrets; use clean public repo/history rewrite only with authorization |
| Historical inline tokens | older src/utility/credentials.py, plus possible archived code and commit messages | DO NOT expose, inspect values or delete | full-history token scan and rotations, human review of revoked token types |
| Current private credentials | %USERPROFILE%/Documents/Codex-Private/ai-vtuber-project/.env via src/utility/private_config.py, or explicit JADE_SECRETS_FILE | KEEP file and access controls | support OS process/env, secret store; account-by-account migration |
| OpenAI access | OPENAI_API_KEY | private dotenv/process only | rotate/revoke and verify billing/project permissions |
| Twitch auth | TWITCH_TOKEN, TWITCH_REFRESH_TOKEN, TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET, TWITCH_BOT_LOGIN, TWITCH_CHANNEL | no changes to OAuth flow; channel/login treated as private identities | revoke old auth, verify bot permissions, refresh-token save and scopes |
| Discord auth and IDs | DISCORD_TOKEN, DISCORD_GUILD, DISCORD_VOICE_CHANNEL | no changes to identity or consent | rotate bot token and review intents, private guild/channel IDs |
| VTube Studio | JADE_VTS_TOKEN, local VTS authorization; VTS model export and settings | no changes | re-authorize, keep model and credentials private unless rights cleared |
| Local phone/API | JADE_HTTP_TOKEN, access policy, Tailscale Serve, device/network identity | localhost only, no port opened | rotate token, scope ACLs, HTTPS, consent and publication architecture |
| Legacy unused provider | ELEVENLABS_API_KEY, voice ID and related history | DO NOT reintroduce non-OpenAI STT/TTS | revoke historical provider secrets, delete from new public snapshot |
| Personality and memory | prompt_chat.txt, potential chat logs, recordings, captions, private context | allow external JADE_PROMPT_FILE/JADE_ASSETS_ROOT | review every prompt, memory, interaction history, transcript, recordings |
| Art, models and exports | jade-modeling/** (large LFS assets, r21 source and r20 runtime, manifests and native Cubism/Krita files) | preserve ALL; excluded from default public code preview | rights/licensing/provenance audit, choose private art repository or approved distribution |
| Developer/environment metadata | .idea/**, local paths in docs and scripts, user/device names | no deletions | sanitize public docs and build scripts, exclude proprietary local paths |
| Supply chain and archive | old branches, PR discussions, historical blobs, Git LFS, artifacts/releases, remote clones/forks, caches | keep private | scan/rotate/purge/review all release surfaces |
| Licensing | README/current project no blanket redistribution grant, jade-modeling/PROVENANCE.md | no license invented | owner approves software and each asset redistribution license |

## Observed without reading secret values
- Refactor CURRENT tree: .env.example exists; no tracked root .env found in its 271 file paths. credentials.py now loads from environ. This DOES NOT prove that past commits are clean.
- develop CURRENT tree: no tracked root .env found in 256 paths.
- master CURRENT tree: root .env and credentials.py present.
- speechtotext-discord CURRENT tree: root .env and credentials.py present.
- Existing PRIVATE_CONFIGURATION.md states a local vault and protected Git backup
  were created previously; treat this as historical documentation, verify locally,
  do not claim access to that vault through GitHub.

## Boundary
Do not remove old branches/commits, delete creative material or overwrite
environment files in this lot. A clean tree is NOT enough: Git history and LFS
objects can remain retrievable. Never make the existing private repository public
as an experiment.
