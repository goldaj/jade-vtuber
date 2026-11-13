# Instructions du projet Jade

Avant toute modification, lire [l’index des conversations](docs/conversations/INDEX.md), puis les instructions de cette page et les documents liés au domaine concerné. Le journal est partiel : conserver les décisions successives, distinguer verbatim et résumé et ne jamais y copier de secrets, identifiants privés ou sorties brutes d’outils.

## Dépôt et configuration

Ce dépôt rassemble le moteur et les sources de Jade. Respecter les branches et le travail existants ; vérifier l’état du dépôt avant toute modification. Les anciennes instructions sont conservées à titre historique dans [l’archive](docs/archives/AGENTS-avant-nouveau-depot.md).

Les travaux hors production se font sur `develop` dans ce dépôt public. `main`
reste la branche destinée aux versions de production ; son existence ne signifie
pas qu’une production est déjà active. Les changements validés de `develop` ne
sont fusionnés dans `main` que sur demande explicite du propriétaire, à renouveler
pour chaque fusion. Il a demandé la fusion après la présente vérification et le
redéploiement ; les prochains travaux se poursuivront sur `develop`.

La contre-revue Astra du dépôt public est consignée dans le
[rapport de reprise Terra](docs/migration/2026-11-02/08-ASTRA-CONTROLE-DEPOT-PUBLIC.md).
Les consignes de relais de cette revue sont historiques ; appliquer les
instructions courantes du paragraphe Runtime ci-dessous pour la reprise actuelle.

Ne jamais committer de secrets, fichiers de configuration privés, enregistrements ni transcriptions. La configuration privée est externe au dépôt et peut être sélectionnée avec `JADE_SECRETS_FILE`. Ne pas divulguer son contenu. Ne pas activer de connecteur, microphone ou appel payant sans demande explicite.

Sous Windows, privilégier `D:\Codex` pour les outils, caches, temporaires et nouveaux espaces de travail ; respecter les chemins établis et jonctions de compatibilité. Ne pas perturber d’autres services.

## Runtime

La revue MVP du 10 novembre et le relais courant sont dans
[ASTRA-REVUE-MVP-20261110.md](docs/gpt6-jade/ASTRA-REVUE-MVP-20261110.md).
Cette revue est terminée. Le propriétaire a ensuite autorisé Astra à résoudre
la panne DAVE et confirmé la réponse vocale réelle. Le relais courant est le
[plan de réduction de latence](docs/gpt6-jade/PLAN-LATENCE-20261110.md). Le
propriétaire a demandé sa réalisation sous Terra puis un lancement local pour
ses essais Discord sur téléphone. Le partage vidéo et les nouveaux résultats
doivent être confirmés par une recette réelle ; ne pas les déclarer validés à
partir des seuls tests simulés.

Python ; STT et TTS OpenAI uniquement ; dialogue interchangeable. Par défaut, la démo et les tests restent hors ligne. La validation repose sur `python -m unittest discover -s tests -v` et `python -m compileall -q src main.py`. Distinguer les tests simulés des essais réels. Consigner les résultats observés et leurs limites dans `docs/gpt6-jade/TASKS.md`.

## Ressources 2D

Conserver les sources et les objets Git LFS. Lire `jade-modeling/MODEL_GUIDE.md`, `jade-modeling/CONTINUATION.md` et les documents de coordination 2D avant de les modifier. Exécuter `python jade-modeling/verify_assets.py` après récupération des objets LFS. Le propriétaire décide du périmètre des travaux visuels et des revues Astra.

## Feuille de route voix et téléphone (3 novembre 2026)

La spécification courante pour l'usage oral naturel de Jade **sans obligation de prononcer son nom**, le MVP Discord avec avatar visible et le futur client mobile audio/vidéo est dans [ROADMAP-MVP-DISCORD-PRODUIT-MOBILE.md](docs/gpt6-jade/ROADMAP-MVP-DISCORD-PRODUIT-MOBILE.md). Codex doit la lire avant tout travail sur Discord vocal, la pertinence conversationnelle, VTube Studio, la sortie audiovisuelle ou l'interface mobile. Elle distingue les fonctions déjà codées de celles qui restent à développer et à recetter ; aucune fusion main automatique.
