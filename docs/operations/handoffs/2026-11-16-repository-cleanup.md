# Passation — rangement du dépôt Jade (16 novembre 2026)

- Agent : ChatGPT (revue architecture, développement, DevOps, documentation, sécurité)
- Départ : `develop` au `5368f008b8970532702ceac1e50ca6b60fd5c1d7`
- Branche de travail : `chore/develop-repository-cleanup-20261116`
- Objectif : garder la seule Démo Express, relocaliser sans casser le renderer r20, organiser les archives, créer un canal de collaboration pérenne et réduire neuf obligations documentaires à une.

## Modifications structurantes

1. Démonstrations `demo/reelle/` et `demo/windows/` retirées ; renderer autonome déplacé dans `src/jade_runtime/avatar_renderer.py` et appel mis à jour ; tests réellement utiles conservés/renommés.
2. `.idea/` retiré du suivi, `.gitignore` renforcé ; workflows de rebuild concentrés sur `develop` et `main`.
3. 83 fichiers historiques ou de référence déplacés sous `docs/history/` ou `docs/operations/reference/` ; liens réécrits selon leur nouvelle position.
4. Entrée canonique [`AGENTS.md`](../../../AGENTS.md), communication par fichiers de mission sous ce dossier et discussion PR, journal technique unique [`CHANGELOG.md`](../CHANGELOG.md).
5. Origine et statut public clarifiés, modèle r21/r20 préservé.

## Suite / vérifications

- Vérifier la compilation, les tests unitaires, le preflight et la commande `scripts/check_docs.py` via CI de la PR.
- Sur le PC Jade : vérifier le launcher, l'ouverture du renderer r20, les assets LFS et l'essai express avec une fenêtre interactive.
- Vérifier les liens Markdown après déplacement et traiter les éventuels liens textuels vers les anciens chemins.
- Contrôler séparément l'historique Git/LFS, les droits des assets et tout secret avant de considérer la publication sûre. Le dépôt actuel est public, ce qui ne constitue pas une autorisation/licence.

Une archive datée n'est pas une consigne active. Le code au SHA de la branche demeure la référence des fonctions.
