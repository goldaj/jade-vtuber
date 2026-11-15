# Nettoyage des branches : contexte feat/turn-conversation-logs-20261115

La suppression directe de refs GitHub est indisponible dans les outils de cette session. Codex devra appliquer `git fetch --prune`, vérifier `git merge-base --is-ancestor <ancienne_br> origin/develop` et l'absence de travail/PR actifs, puis éventuellement `git push origin --delete <ancienne_br>`. Ne jamais supprimer main ou develop.

Huit pointes ancêtres de develop au contrôle : `docs/codex-pc-mobile-onboarding-20261115`, `feat/jade-autobiographical-memory-20261115`, `feat/jade-discord-unified-conversations-20261115`, `feat/jade-persistent-memory-core-20261115`, `feat/jade-private-mobile-pwa-20261115`, `feat/jade-windows-launcher-20261115`, `fix/jade-unified-always-on-20261115`, `review/jade-mobile-memory-integration-20261115`. Recontrôler toutes les pointes avant suppression.

**Branches divergentes à protéger jusqu'à revue** : `docs/jade-persistent-memory-identity-20261115`, `feat/turn-conversation-logs-20261115`, `test/intent-all-channels-20261115`. Celle-ci est l'une d'elles : environ 10 commits propres, portant notamment sur des tests et modules de journalisation. Reprendre tout apport non intégré à develop avant d'envisager une suppression.
