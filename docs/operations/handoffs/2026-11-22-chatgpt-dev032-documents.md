# DEV-032 — Création et livraison de fichiers (22 novembre 2026)

## Objectif validé par Goldaj
Pièce jointe téléchargeable sur demande explicite : mobile texte / oral (oral + réponse écrite), Discord MP texte, salon texte, vocal (oral + chat texte natif au même salon). Goldaj seul par défaut avec son lien de compte Discord préexistant ; droits futurs configurables ; format explicite respecté, HTML par défaut pour code/site non précisé, ZIP multi-fichiers ; expiration au bout de 24 heures, y compris suppression des messages Discord porteurs de fichiers. Pas d'URL brute envoyée par Jade.

## État technique
Travail poussé sur `develop`, non mergé sur `main`. Nouvelle couche `src/jade_runtime/documents.py`, outil de fonction Responses, contexte documentaire dans Dialogue, modèle Reply avec pièces jointes, boucle Runtime, relais PWA/Discord, réglages et tests `tests/test_jade_documents.py`. Pas de fournisseur supplémentaire ni de fichiers stockés dans Git.

## Risques et points à valider
- CI Linux/Windows / tests unitaires à confirmer ; une erreur de syntaxe initiale sur les nouveaux raccordements a été corrigée dans le commit `64d3c374`.
- Vérifier en recette réelle les cinq parcours, la visibilité des boutons PWA, le chat natif vocal, les permissions et suppression Discord ; ne pas redemander la validation de liaison des comptes que Goldaj a déjà confirmée fonctionnelle.
- Vérifier l'expiration à 24 h, après redémarrage et en cas d'indisponibilité Discord. Copies téléchargées et caches Discord non effaçables hors contrôle de Jade.
- Modèle LLM plafonné à `JADE_MAX_COMPLETION_TOKENS`, un document très long peut requérir un autre chemin technique. PDF stdlib minimal en Latin-1, Unicode complet non assuré.
- Pas de conversion/lecture de fichiers entrants, pas de code généré exécuté ; dossier de sortie privé par défaut dans `D:/Jade/private/jade-documents/` sous Windows.
- Les documents publics doivent éviter la divulgation de contexte privé d'autres canaux ; validation de non-divulgation en recette.
- Un fichier créé sans livraison réussie doit être signalé comme indisponible et supprimé au plus tard à expiration. L'envoi n'est pas égal à un téléchargement effectif.

## Décision de suivi
DEV-032 `En cours`, sans déclaration `Done`. Si tout le code et ses vérifications automatiques sont validés mais que seule la recette humaine reste, transférer la même carte dans REC avec lien DEV-032, conformément aux règles d'AGENTS.md. Éviter tout doublon actif. Tâches Twitch/OBS/microphone physique non touchées.
