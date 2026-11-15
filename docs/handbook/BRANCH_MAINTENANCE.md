# Nettoyage prudent des branches pour Codex : test/intent-all-channels-20261115

Le connecteur GitHub de l'assistant ne permet pas la suppression de branche. Codex devra faire `git fetch --prune origin`, contrôler l'ascendance de chaque ref vis-à-vis de `origin/develop` et ses PR/travaux récents, puis seulement envisager `git push origin --delete <branche>`. Ne jamais effacer main ou develop.

Candidats **ancêtres vérifiés de develop** : docs/codex-pc-mobile-onboarding-20261115 ; feat/jade-autobiographical-memory-20261115 ; feat/jade-discord-unified-conversations-20261115 ; feat/jade-persistent-memory-core-20261115 ; feat/jade-private-mobile-pwa-20261115 ; feat/jade-windows-launcher-20261115 ; fix/jade-unified-always-on-20261115 ; review/jade-mobile-memory-integration-20261115. Refaire les vérifications avant suppression.

**Branches divergentes à ne pas supprimer sans audit :** docs/jade-persistent-memory-identity-20261115 ; feat/turn-conversation-logs-20261115 ; test/intent-all-channels-20261115. Celle-ci apporte deux commits de tests/doc pouvant être utiles à develop ; les comparer avant suppression. La documentation qu'elle contient appartient uniquement à ce code ancien.
