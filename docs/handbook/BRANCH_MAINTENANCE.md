# Maintenance des branches de Jade

`develop` reçoit les changements courants. Le propriétaire autorise explicitement chaque mise à jour de `main`.

## Point de retour avant le nettoyage du 27 novembre 2026

La fusion `e5dd826` sur `main` contient exactement l’arbre de `develop@56eb108`. Elle réunit les historiques des deux branches et fixe l’état du produit avant le nettoyage. [Instantané GitHub](https://github.com/goldaj/jade-vtuber/commit/e5dd826)

## Retirer des branches intégrées ou arrêtées

1. Actualiser les références et relever les pointes, les PR liées et les worktrees locaux.
2. Vérifier l’ascendance. Pour une branche divergente ou fusionnée par squash, comparer aussi les changements pour repérer les apports uniques.
3. Conserver les apports à reprendre dans une archive Git vérifiée. Vérifier les fichiers non commités du worktree et conserver les sources d’art uniques.
4. Retirer les références autorisées par leur nom exact. Confirmer la liste distante après le push et inscrire le point de restauration dans la passation de nettoyage.

Les règles de protection souhaitées pour `main` concernent la suppression et le force-push. Le statut de la carte OPS-017 correspond à l’arbitrage du propriétaire. Vérifier le réglage actuel dans GitHub avant de se fonder sur sa présence. [Arbitrage OPS-017](../operations/handoffs/2026-11-21-chatgpt-ops017-protection-branches.md)

Les relevés de novembre antérieurs au nettoyage documentent les branches, les réconciliations et les résultats de test observés à leur date. [Archive des relevés](../history/audits/BRANCH_MAINTENANCE-2026-11-18.md)
