# Instructions du projet Jade

Avant toute modification, lire [l’index des conversations](docs/conversations/INDEX.md), puis les instructions de cette page et les documents liés au domaine concerné. Le journal est partiel : conserver les décisions successives, distinguer verbatim et résumé et ne jamais y copier de secrets, identifiants privés ou sorties brutes d’outils.

## Dépôt et configuration

Ce dépôt rassemble le moteur et les sources de Jade. Respecter les branches et le travail existants ; vérifier l’état du dépôt avant toute modification. Les anciennes instructions sont conservées à titre historique dans [l’archive](docs/archives/AGENTS-avant-nouveau-depot.md).

Ne jamais committer de secrets, fichiers de configuration privés, enregistrements ni transcriptions. La configuration privée est externe au dépôt et peut être sélectionnée avec `JADE_SECRETS_FILE`. Ne pas divulguer son contenu. Ne pas activer de connecteur, microphone ou appel payant sans demande explicite.

Sous Windows, privilégier `D:\Codex` pour les outils, caches, temporaires et nouveaux espaces de travail ; respecter les chemins établis et jonctions de compatibilité. Ne pas perturber d’autres services.

## Runtime

Python ; STT et TTS OpenAI uniquement ; dialogue interchangeable. Par défaut, la démo et les tests restent hors ligne. La validation repose sur `python -m unittest discover -s tests -v` et `python -m compileall -q src main.py`. Distinguer les tests simulés des essais réels. Consigner les résultats observés et leurs limites dans `docs/gpt6-jade/TASKS.md`.

## Ressources 2D

Conserver les sources et les objets Git LFS. Lire `jade-modeling/MODEL_GUIDE.md`, `jade-modeling/CONTINUATION.md` et les documents de coordination 2D avant de les modifier. Exécuter `python jade-modeling/verify_assets.py` après récupération des objets LFS. Le propriétaire décide du périmètre des travaux visuels et des revues Astra.
