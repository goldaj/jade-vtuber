# État vérifiable de cette branche : main

**Base inspectée :** `main` au SHA `2f4037dbee8c7dcb36f30bcfbe3e1df182a9ac96`, avant l'ajout de ce manuel et de la Démo Express. Les éventuelles évolutions postérieures doivent mettre à jour ce document à partir du **code réel de la branche**.

## Fonctions présentes

- CLI `main.py` avec `--preflight`, `--live`, `--voice`, `--mic`, `--twitch`, `--discord`, `--discord-voice`, `--vts`, `--http`, `--avatar`.
- Moteur de dialogue asynchrone, file bornée `asyncio.Queue` avec ordre d'arrivée, historique de session non persistant, détection de déclenchement de réponse, délais/cancel/shutdown.
- Voix OpenAI STT/TTS, sortie locale ffplay, Discord écrit/vocal, Twitch IRC, VTube Studio optionnel, avatar local r20, HTTP local avec client texte, sous-titres OBS.
- Démo console hors ligne, démo Live2D réelle séparée (nécessite clé API) et Démo Express locale Windows simulée.

## Fonctions NON présentes dans main

- **Aucun** drapeau `--all-channels` ni launcher graphique Windows « tout-en-un ».
- **Aucune** PWA Android privée avec Tailscale Serve du chantier `develop`.
- **Aucune** mémoire SQLite persistante / Core Memories / autobiographie intégrée.
- **Aucun** arbitrage des tours par un modèle IA : la file est FIFO.
- **Aucune** fusion des conversations Discord texte/vocal telle que développée ultérieurement.

Ne pas importer ces caractéristiques par copier-coller de la documentation de `develop`. Le fait que d'anciens guides ou maquettes mentionnent une fonction future n'atteste pas sa présence.

## Branche de destination

La branche `develop` contient des fonctionnalités plus récentes. **Ne pas merger develop vers main** uniquement pour synchroniser les guides : cela propagerait du code et des politiques de runtime différents. Tout merge fonctionnel vers main exige une décision séparée du propriétaire. Les documents de chaque branche doivent refléter son propre état.
