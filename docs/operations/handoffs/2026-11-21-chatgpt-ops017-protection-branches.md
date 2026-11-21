# OPS-017 — décision de protection de branches et suivi des passations

**Date :** 21 novembre 2026. **Décideur :** propriétaire de Jade (confirmation explicite de la recommandation dans la conversation). **Branche documentaire :** `develop`. **État :** décision validée, application GitHub non effectuée.

## Décision produit et gouvernance

- **`main`** : empêcher la suppression de la branche et les mises à jour par force-push ; les pushes directs ordinaires restent possibles.
- **`develop`** : conserver les possibilités actuelles, sans nouvelles règles de protection.
- **Pull requests** : ne pas rendre les PR obligatoires.
- **Visibilité** : dépôt public inchangé ; ne pas changer `main`, le code ou les secrets pour cette décision.

## Contrôle factuel au 21/11/2026

Les réponses GitHub `GET /branches/main`, `GET /branches/develop` et `GET /rulesets` confirment : `main.protected=false`, `develop.protected=false`, aucune règle de protection de dépôt renvoyée. La connexion ChatGPT utilisée ne propose aucune action de mutation des protections / rulesets ; **aucune protection n'a été activée**. Un commit de documentation ne protège pas la branche.

**Application restante par un administrateur GitHub :** dans les paramètres du dépôt, créer une règle de branche ciblant exclusivement `main` ; interdire suppression et force-push ; ne pas imposer revue PR ni contrôle bloquant supplémentaire ; vérifier que les commits ordinaires sur `main` restent permis. Relire l'état de `main` et `develop` après activation, vérifier qu'une protection est effectivement active, puis noter la date et la règle. Éviter de lancer des commandes destructrices juste pour « tester ».

## Passations et responsabilités

- [Index des passations](README.md) relu : de nombreuses fiches sont des suivis actifs ou des preuves de décisions déjà prises ; ne pas archiver tout le dossier en bloc.
- [Passation de rangement du 16/11](2026-11-16-repository-cleanup.md) : les contrôles matériel Windows, redondances artistiques, provenance / secrets / LFS et certaines vérifications de documentation restent rattachés aux cartes OPS/ART pertinentes. Les laisser ouverts plutôt que prétendre qu'ils ont été réalisés.
- [Maintenance des branches](../../handbook/BRANCH_MAINTENANCE.md) et **OPS-013/OPS-014** : cartes marquées Done dans la backlog ; la suppression ou la revue de nouvelles branches ne doit pas être présumée sur la base d'une ancienne photographie.
- Les fiches de recette avec éléments encore ouverts restent actives, notamment REC-021 et REC-025. Les validations Done déjà consignées n'ont pas à être refaites.
- Les liens du présent document sont relatifs aux chemins existants ; aucun transfert/archivage de fiches n'a été effectué dans cette opération. Les fiches closes pourront être archivées individuellement, en mettant à jour leurs liens, après contrôle.

**Décision de statut :** OPS-017 passe de `À qualifier` à `À faire`, **pas Done**, tant que la protection `main` n'est pas appliquée et que les passations concernées n'ont pas été clôturées ou explicitement reportées avec preuves. Aucun droit administrateur GitHub ni contrôle des postes privés revendiqué.
