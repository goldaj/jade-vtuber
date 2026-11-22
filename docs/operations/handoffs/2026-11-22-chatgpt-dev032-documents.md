# DEV-032 — Création et livraison de fichiers (22 novembre 2026)

## Objectif validé par Goldaj
Pièce jointe téléchargeable sur demande explicite : mobile texte / oral (oral + réponse écrite), Discord MP texte, salon texte, vocal (oral + chat texte natif au même salon). Goldaj seul par défaut avec son lien de compte Discord préexistant ; droits futurs configurables ; format explicite respecté, HTML par défaut pour code/site non précisé, ZIP multi-fichiers ; expiration au bout de 24 heures, y compris suppression des messages Discord porteurs de fichiers. Pas d'URL brute envoyée par Jade.

## État technique
Travail poussé sur `develop`, non mergé sur `main`. Nouvelle couche `src/jade_runtime/documents.py`, outil de fonction Responses, contexte documentaire dans Dialogue, modèle Reply avec pièces jointes, boucle Runtime, relais PWA/Discord, réglages et tests `tests/test_jade_documents.py`. Pas de fournisseur supplémentaire ni de fichiers stockés dans Git.

## Risques et points à valider
- **Vérifications achevées le 22/11 :** [CI Linux/Windows verte sur dc8f0fb2](https://github.com/goldaj/jade-vtuber/actions/runs/45043574769), contrôles Responses API et secrets réussis, tests unitaires de génération/permissions/rétention réussis. Une erreur de syntaxe initiale a été réparée dans `64d3c374` ; les derniers correctifs sont inclus dans `dc8f0fb2`.
- Vérifier en recette réelle les cinq parcours, la visibilité des boutons PWA, le chat natif vocal, les permissions et suppression Discord ; ne pas redemander la validation de liaison des comptes que Goldaj a déjà confirmée fonctionnelle.
- Vérifier l'expiration à 24 h, après redémarrage et en cas d'indisponibilité Discord. Copies téléchargées et caches Discord non effaçables hors contrôle de Jade.
- **Limites acceptées expressément par le propriétaire :** taille des fichiers bornée par le budget de sortie du modèle, intentionnelle ; PDF stdlib minimal en Latin-1, Unicode complet non requis pour cette US.
- Pas de conversion/lecture de fichiers entrants, pas de code généré exécuté ; dossier de sortie privé par défaut dans `D:/Jade/private/jade-documents/` sous Windows.
- Les documents publics doivent éviter la divulgation de contexte privé d'autres canaux ; validation de non-divulgation en recette.
- Un fichier créé sans livraison réussie doit être signalé comme indisponible et supprimé au plus tard à expiration. L'envoi n'est pas égal à un téléchargement effectif.

## Décision de suivi mise à jour

**DEV-032 est transférée à REC-039, statut « À valider », le 22/11/2026**, suivant la règle de suivi unique approuvée par le propriétaire. Aucune implémentation supplémentaire attendue sur le périmètre convenu. Les vérifications de confidentialité et les comportements Android/Discord réels relèvent désormais de REC-039 ; aucun test humain n'est inventé. En cas d'échec de recette, ouvrir une anomalie DEV distincte et ciblée. Tâches Twitch/OBS/microphone physique non touchées.
