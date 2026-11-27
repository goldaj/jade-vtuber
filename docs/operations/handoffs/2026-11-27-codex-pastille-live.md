# Pastille Live et micro coupé

- Codex, correctif d’affichage PWA pour REC-050, recette Android à valider. Branche `fix/mobile-live-indicator-20261127` depuis `develop@113c7d8`.
- L’interface utilisait le même bleu foncé pour la veille avec micro ouvert et pour le micro coupé. Le client publie déjà l’arrêt de la capture avant d’attendre le réseau. La pastille exploite cet état local et devient bleu clair au clic, même pendant la fin de lecture ou la fermeture distante.
- Le test d’interface vérifie les trois états, la coupure immédiate en plein écran, la fin de lecture, la fermeture et le retour au classique. La nuance à l’écran reste à observer sur Android.
- [Critères REC-050](../../backlog/02-RECETTE.md#rec-050--valider-profil-onoff-et-les-transitions-classiquelive-ancienne-dev-040) · [Architecture Live mobile](../../architecture/LIVE_MOBILE.md)

## Échanges accessibles

- **Propriétaire**, synthèse du 27 novembre. La pastille reste bleu foncé après la coupure du micro. Souhaite du bleu foncé pour la veille et du bleu clair lorsque le Live est sélectionné mais inactif. Le reste du Live fonctionne.
- **Assistant**, synthèse. Identifie deux états jusqu’alors rendus dans la même couleur. Corrige la pastille à partir de la capture locale.

Les heures individuelles ne sont pas disponibles dans ce journal.
