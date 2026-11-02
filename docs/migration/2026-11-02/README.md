# Jade — dossier de migration revu par Astra, prêt pour Terra

**État du 2 novembre 2026 : préparation terminée, exécution du runtime différée.** Le propriétaire confirme qu’il n’y a **pas de production active**. `develop` est la cible d’intégration proposée ; le premier lancement durable constituera une nouvelle mise en service, pas une migration d’un service existant.

## Lire dans cet ordre

**Revue Astra terminée :** [l’avis et les étapes précisées](06-ASTRA-REVIEW.md) ont guidé les corrections Terra ; le dossier initial ci-dessous conserve l’état de l’audit.

**Exécution Terra :** les correctifs du runtime sont réalisés et testés ; l’essai réel micro a été reporté par le propriétaire. Reprendre avec [l’état et la recette restante](07-REPRISE-RECETTE.md). Les formulations ci-dessous décrivent l’état du dossier au moment de l’audit initial.

1. [Branches, ascendance et traitement du legacy](01-BRANCHES.md).
2. [Défauts, corrections à prévoir et incertitudes](02-AUDIT.md).
3. [Plan d’exécution, configuration et retour arrière](03-PLAN.md).
4. [Validation réellement observée](04-VALIDATION.md).
5. [Passation Astra → Terra et critères de décision](05-RELAY.md).
6. [État machine lisible](snapshot.json), [journal et couverture](../../conversations/INDEX.md).

Les deux scripts de [reproduction](repros/) sont des **constats de défauts sur la baseline**, pas des tests de non-régression : leur résultat favorable signifie que le défaut décrit est encore présent. Ils utilisent des données synthétiques et ne contactent aucun service.

## Résultat de la revue rapide

La refonte apporte un cœur asynchrone avec queue bornée, une mémoire par conversation, des interfaces séparées, la voix OpenAI exclusivement dans le chemin actif, des connecteurs opt-in et une démo hors ligne. Ces fondations méritent d’être conservées. Les **51 tests existants passent** sous Python 3.11 Windows dans un venv neuf ; le préflight et la compilation passent aussi.

Huit défauts supplémentaires sont reproduits avec des doubles synthétiques : coordination micro/parole, annulation audio, arrêt non borné, accumulation de sessions, saturation Twitch, épuisement des emplacements des locuteurs Discord, fuite de workers lors d’une connexion vocale échouée et exécution tardive d’une requête HTTP expirée. La revue du code ajoute des défauts de séquencement des sorties, de politique de mentions Discord, de fermeture des dépendances du preview public et un test fournisseur trompeur. Les preuves et le degré de confirmation sont détaillés dans l’audit.

## Ce qui a été corrigé dans cette intervention

**Aucun défaut du runtime n’a été corrigé**, conformément à la demande de préparer d’abord la revue Astra et de réserver les travaux réels à Terra. Les corrections effectuées sont documentaires :

- La passation désignait encore la PR #1 et la branche de refonte initiale : des renvois actifs pointent désormais vers la PR #2 consolidée et le présent dossier.
- L’affirmation du 29 octobre selon laquelle la branche consolidée contient tout `develop` est datée : six commits, uniquement documentaires, sont désormais propres à `develop`. Le nouveau relevé conserve les dates et les anciens constats.
- « Toutes les branches à fusionner » est traduit en une matrice de traitement : cinq ancêtres n’ont aucun travail exclusif, la branche rebuild est contenue dans la branche consolidée, et le WIP Discord demande une réconciliation fonctionnelle plutôt qu’une fusion brute.
- L’absence d’index de conversation commun est corrigée, avec sources, rôles et lacunes explicites, et un lien depuis `AGENTS.md`.
- La première production est distinguée de l’intégration Git : aucune production n’est actuellement à préserver ou à basculer selon la réponse du propriétaire.

## État sauvegardé

- Copie d’audit : `D:\Codex\projects\jade-migration-20261102`.
- Branche locale documentaire : `codex/migration-audit-20261102`, créée sur `df544ed78976096c522912a56ef9086c554e52ac`.
- Clone applicatif historique inchangé : `C:\Users\<utilisateur>\Desktop\ai_vtuber_project\jade-project`, propre sur `474ad9a` avant/après audit.
- Aucun changement de `main.py`, `src/`, `tests/`, du manifeste ou des workflows. Aucun changement de `jade-modeling/**`, aucune récupération des gros objets LFS et aucun contrôle visuel revendiqué.
- Aucune fusion, aucun push, aucun déploiement, aucune rotation de secret, aucune publication ni suppression de branche.

Le dossier est local et privé. Le dépôt historique contient toujours des identifiants dans son ancien historique. La préparation à une éventuelle publication reste un chantier distinct, avec ses propres conditions ; elle n’est pas requise pour intégrer proprement le runtime dans le dépôt privé.
