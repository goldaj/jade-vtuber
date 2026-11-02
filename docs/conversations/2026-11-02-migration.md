# Conversation Jade — préparation de migration, 2 novembre 2026

Date du chat : 2026-11-02, Europe/Paris. Les heures individuelles des messages ci-dessous ne sont pas fournies. Couverture : demande en cours et réponses accessibles ; aucun historique absent n’est reconstruit en verbatim.

## Utilisateur — verbatim

> gpt-6 a beaucoup bossé sur le code de Jade depuis la dernière fois où t'as regardé le code. On va temporairement laisser de côté ce qui est lié au visuel et à l'animation de l'asset 2D pour le moment.
>
> À la place, j'aimerais maintenant que tu contrôles rapidement ce qui a été fait sur la/les branche(s) dédiée(s) et que tu fasses la documentation de migration pour que pas à pas tu puisses ensuite corriger, intégrer proprement et fusionner toutes les branches vers la branche de production de Jade.
>
> Prépare tout le nécessaire, liste moi les erreurs que t'as corrigé et les doutes que tu as encore. Une fois fait et tout documenté, je te repasse sous astra pour que tu puisses faire un dernier contrôle avant de te remettre sous terra et d'effectuer les travaux réels.

## Assistant — verbatim, première réponse

> Je vais examiner les branches et les consignes du projet, puis préparer un dossier de migration avec l’ordre d’intégration, les vérifications à effectuer et les points à faire relire sous Astra. Je laisse de côté le visuel et l’animation de l’asset 2D, et je garde les modifications de code et les fusions pour l’étape suivante.

## Assistant — verbatim, points d’avancement successifs

> Le dossier ouvert contient surtout le travail sur le modèle 2D ; j’ai retrouvé le dépôt applicatif séparé et son nouveau nom, `jade-ai-vtuber`. Ses références locales semblent anciennes. Je vérifie donc les branches sur GitHub avant de définir l’ordre de migration.

> La refonte est regroupée dans la PR #2, qui contient toute l’ancienne PR #1. Depuis cette consolidation, `develop` a reçu six commits documentaires supplémentaires ; je les inclus dans le plan. J’ai créé une copie d’audit sur D: pour lancer les tests sans toucher au clone applicatif existant. La revue du code a aussi fait ressortir plusieurs défauts possibles autour de l’audio et de l’arrêt du runtime, que je vérifie.

> Les 51 tests existants passent dans l’environnement Python 3.11 isolé. Le préflight, la compilation et la démo hors ligne passent également. Les scénarios supplémentaires ont toutefois confirmé des défauts que cette suite ne couvre pas : capture micro pendant une réponse, arrêt qui attend une sortie bloquée, conservation excessive des sessions et saturation de certains connecteurs. Je les documente comme corrections à réaliser après la revue Astra.

## Assistant — verbatim, clarification affichée

> Pour fixer la dernière étape du plan : quelle branche représente aujourd’hui la production de Jade ? GitHub utilise `develop` par défaut, tandis que `master` est restée sur l’ancien code.

## Utilisateur — verbatim, réponse

> Il n’y a pas encore de production active

## Assistant — verbatim, suite des points d’avancement

> Je retiens qu’il n’y a pas encore de production active. Le plan prendra donc `develop` comme cible d’intégration, puis prévoira une première mise en service privée après recette. Il précisera aussi le sort de chaque ancienne branche : déjà absorbée, à conserver, ou à examiner sans fusionner son code.

> Le dossier contient maintenant l’ordre des corrections, la migration de configuration et le retour arrière. Les huit scénarios de défauts ont été reproduits sans compte, microphone ni audio réel. La CI du SHA audité reste en échec avant toute étape de test ; sa cause exacte reste à établir. Je termine les consignes de reprise pour Astra et la vérification des fichiers livrés.

> La documentation est vérifiée : les liens fonctionnent, les scripts livrés reproduisent les huit défauts et le diff ne contient aucun changement du runtime ni des assets. Je sauvegarde l’ensemble dans un commit local et une archive sur D:. Le clone historique et les branches distantes restent inchangés pour ta revue sous Astra.

## Instructions utilisateur disponibles — synthèse non verbatim

- Stocker les nouveaux projets, outils, caches et temporaires sous D:, en conservant les chemins établis et les jonctions existantes.
- Lire les instructions et le journal propres au projet avant une modification ; créer un index si nécessaire, indiquer les lacunes et relier cet index depuis les instructions.
- Conserver les rôles et les horodatages réels ; expurger les éléments privés ; ne jamais exporter raisonnement interne, messages système/développeur ou sorties brutes d’outils.

## Assistant — synthèse non verbatim de l’intervention

Audit d’une copie isolée du dépôt ; inventaire des neuf branches distantes et des deux PR ; comparaison avec le clone applicatif historique sans le modifier. Lecture des six commits documentaires supplémentaires de la branche cible. Installation d’un environnement Python séparé, tests existants et reproductions synthétiques des défauts de concurrence et de connecteurs. Documentation et scripts de reproduction seulement : aucun correctif du runtime, aucune fusion, aucun déploiement, aucun appel de service payant et aucune manipulation du modèle 2D.

Les résultats vérifiés et les limites figurent dans [le dossier de migration](../migration/2026-11-02/README.md). Cette synthèse relate les actions de l’assistant ; elle n’est pas présentée comme une citation du dialogue.

## Décision actuelle et suite

Le propriétaire demande cette fois une relecture manuelle sous Astra avant de revenir sous Terra pour les travaux de code et d’intégration. Cette demande est propre à cette migration ; elle ne réinstaure pas une obligation générale de double revue à chaque tâche. La cible Git proposée est `develop`. Le propriétaire confirme l’absence de production active ; la branche d’une future release et son lancement seront fixés lors de la première mise en service.
