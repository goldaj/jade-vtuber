> Note d’actualité — document historique. Les décisions ultérieures du propriétaire et les instructions actuelles du dépôt priment ; consulter l’index des conversations.

# Codex execution plan: private Jade to eventual public-source release

**NOT AUTHORIZED TO EXECUTE DESTRUCTIVE STEPS YET.** First complete PR #1
integration/review. This lot supplies code and a roadmap, not an instruction
to delete known secrets or open the repository. Every stage requires logs of
real observations and owners.

## M0. Freeze and inventory (read only, high priority)
- [ ] Inspect all current refs/PRs/tags/releases and LFS; preserve a complete
  private mirror, Git LFS objects, models and local external dotenv under
  separate secure access; record encrypted backup, checksums and restore test.
- [ ] Identify all credentials, login IDs, private server/device addresses,
  annotations in prompts/voice transcripts, sensitive old commit messages,
  artifacts, workflow logs and generated caches. Never paste values into PRs.
- [ ] Reconcile branch source names/master/speechtotext-discord and confirm all
  known leaks with a specialist scanning tool in a protected environment.
- [ ] Inventory art rights and source/provenance, including native Cubism/Krita,
  motion physics, textures, API-generated images and third-party dependencies.

## M1. Separate live configuration (non-destructive)
- [ ] Review this PR's allowlisted public-profile loader against all Settings.
- [ ] Exercise environment precedence and legacy token refresh offline; test
  Windows paths, missing profile, malformed/sensitive TOML, absent private prompt.
- [ ] For each user identity and connector, document private env mapping,
  token scope, separate development/production keys and secure local storage.
- [ ] Move only after backup verified, with a one-time migration report of
  hashes/paths **not secret values**; no credential in Git issue/PR.
- [ ] Keep access to old private repository and model data throughout.

## M2. Separately package sources, persona and art (functional completeness)
- [ ] Run preview tool and inspect all exported Python/config/fixture contents
  manually; no automatic public push; fresh temp checkout and test offline.
- [ ] Replace private prompt with approved generic prompt; support a persona
  plugin loaded from JADE_PROMPT_FILE or JADE_ASSETS_ROOT on owner machines.
- [ ] Extract art to private artifact store or separate PRIVATE Git LFS repo,
  with per-release manifests, content checksums, access rights and fallbacks.
  Avoid automatic clone/submodule that exposes private URLs or credentials.
- [ ] Test app boots without Jade's art (console/offline), plus optional
  private art installation separately on actual machine.
- [ ] Audit scripts under jade-modeling/** for relative/private file paths and
  license dependencies, only refactor them in a separate approved workstream.
- [ ] Review every hardcoded identity, channel/guild ID, hostname, client ID,
  OAuth callback, local filesystem path and generated screenshot.

## M3. Credential incident remediation (manual, service owner)
- [ ] Rotate/revoke OpenAI project keys and review usage/billing.
- [ ] Revoke Twitch OAuth access/refresh, rotate client secret, reauthorize with
  least scopes, confirm refresh works using external dotenv.
- [ ] Rotate Discord bot token, inspect privileged permissions and consent.
- [ ] Renew VTS local plugin token, phone HTTP bearer, remaining legacy
  ElevenLabs or other service secrets ever committed; verify revocation.
- [ ] Inspect every connected account for unexpected usage after historic leak.
- [ ] Never write replacement credentials to a Git repo or release artifact.

## M4. Create PUBLIC from a clean history-free snapshot (preferred)
- [ ] Prefer a brand-new repository containing only individually approved
  files and **no historical Git objects or LFS pointers**. Leave current
  goldaj/jade-ai-vtuber PRIVATE as preserved archive unless a separate
  approved retention decision says otherwise.
- [ ] If retaining original repo URL is mandatory, coordinate a specialist
  git-filter-repo history rewrite in a disposable mirror, force pushes with
  explicit owner sign-off, ref/tag cleanup, PR, fork, cache, collaborator and
  LFS handling; handle already cloned histories. Never blindly filter an
  active Codex tree.
- [ ] Run complete scan on clean fresh clone across all refs and all exported
  assets; use gitleaks / trufflehog / equivalent with rules + manual review,
  include commit messages, release files and CI traces.
- [ ] Approve explicit software license and separate artistic/IP asset rights.
- [ ] Fresh-install, offline tests, provider opt-in tests after credential
  rotation, least-privilege CI, independent reviewer and final owner's approval.

## M5. Publication gate and rollback
- [ ] All machine gates in 04-RELEASE-GATES.json reviewed, marked with
  evidence external to Git, no failed/unknown gate.
- [ ] Publish only after user explicitly authorizes. Do not expose original
  private repo history, test files, browser recordings or secret scans.
- [ ] Verify externally that public clone cannot retrieve private history,
  files, old refs, LFS or artifacts.
- [ ] Rollback is not just flipping visibility: once published, assume any
  secret copied to caches is compromised; revoke and inform owners.

## Acceptance at current GPT6 handoff
- [x] Isolated branch/PR, no changes to existing secret values or histories.
- [x] Public-vs-private setting layer and external private prompt hook.
- [x] Basic current-tree scanner and future history-path blocker.
- [x] Allowlist export preview, no publication, no LFS copy, synthetic tests.
- [ ] CI at final contributor HEAD green and Codex review recorded (PR CI attempts at 28 Oct reported failure with zero steps/logs unavailable; NOT validated).
- [ ] Actual backups, real credential rotations, full-history scan, rights
      clearance, clean public repo and publication: ALL FUTURE MANUAL WORK.
