# Mémoire SQLite active et inscription Discord automatique — 20/11/2026

- Agent / rôle : ChatGPT, intégration code et tests.
- Carte du backlog : évolution demandée directement par le propriétaire, sans carte à clôturer automatiquement.
- Base de travail : branche `develop` à partir du commit `b9ce8d5a1bfd908c9462e7f53e7148b70d2d4965`, après le push propriétaire du 20 novembre ; branche `feat/auto-memory-discord-20261120-v2`.
- Objectif : supprimer les commandes d'inscription mémoire pour les membres du serveur Discord, et activer SQLite + curation par défaut sans configuration du chemin.
- Modifications : `config.py` (chemin privé automatique, valeurs par défaut), `main.py` (création base seulement en live), `memory_store.py` (inscription fiable + opt-out durable, schéma additif v3), `memory_service.py` (activation serveur Discord uniquement, commande oublier), `orchestrator.py` (invocation), tests, documentation et changelog.
- Sécurité / périmètre : Discord texte du serveur et vocal identifié seulement ; pas d'inscription des messages privés Discord ni de Twitch. Aucun élargissement de lecture inter-salons/interpersonnes. Suppression durable de la mémoire par identifiant de transport vérifié. La table d'exclusion retient l'identifiant Discord pour éviter une réinscription accidentelle.
- Vérifications : tests unitaires ajoutés (`tests/test_jade_memory_auto_enrollment.py`) ; CI et PC à contrôler distinctement. Aucun lancement du moteur sur le PC propriétaire effectué.
- **Passe de validation distincte :** comparer le commit final avec la dernière tête `develop`, contrôler les tests et la non-régression avec les anciens tests avant intégration. Ne pas déclarer Done sans résultat.
- Limites : les `JADE_MEMORY_ENABLED=0`/`JADE_MEMORY_CURATOR_ENABLED=0` explicites du fichier privé restent prioritaires. Une base préexistante doit garder son ancien chemin via `JADE_MEMORY_DB_PATH`. La curation peut être facturée.
- Exploitation : affichage clair dans les règles du serveur Discord avant l'arrivée/participation des utilisateurs ; préciser la conservation locale, la possibilité de `!jade-memoire oublier`, et la reprise volontaire `!jade-memoire activer`. La simple inscription au serveur ne stocke pas de souvenirs : seul un échange traité avec Jade est enregistré.
- Pas de modification du `main` ni des fichiers privés du propriétaire.
