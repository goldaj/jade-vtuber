# Clôture de sept cartes de Jade sur validation du propriétaire — 21 novembre 2026

- **Mission :** transcrire la décision utilisateur de clôture des cartes REC-003, REC-007, REC-011, DEV-002, DEV-009, DEV-013 et DEV-014.
- **Agent :** ChatGPT (édition documentaire uniquement) ; **validateur :** propriétaire de Jade, par approbation explicite du lot le 21/11/2026.
- **Branche :** `develop`, tête de départ `ecf1c110cebd3b1db9ebd34c84eef4e20f119c78`. Commit de clôture : celui contenant cette passation.
- **Périmètre :** colonnes de statut des deux vues canoniques DEV/REC et index des passations. Aucun changement de code, aucun déploiement, aucun appel API facturable.

## Décision explicite et état de chaque carte

Le 21 novembre 2026, après présentation des cartes non terminées, le propriétaire a cité nominativement ces sept IDs et indiqué : « Pour moi tout ça est ok et peut être clôturé ». Il s'agit d'une **validation positive du propriétaire** et non d'une certification de nouveaux tests physiques par ChatGPT.

| ID | Priorité | Situation avant | Décision | Justification et preuves déjà documentées | Limites de traçabilité |
| --- | --- | --- | --- | --- | --- |
| **REC-003** | P0 | À faire ; validation partielle voix du 20/11 | **Done** | Écoute et réponse dans Discord vocal déjà déclarées validées par le propriétaire dans `02-RECETTE.md` ; validation complète du lot le 21/11. | Pas de journal supplémentaire de changement de canal, DAVE ou liste de participants transmis dans cet échange. |
| **REC-007** | P0 | À faire ; absence de double réponse confirmée le 20/11, repli WAV précédemment ouvert | **Done** | Absence de double diffusion signalée OK lors de la recette du 20/11 ; validation sans réserve de la carte entière par le propriétaire le 21/11. | Pas de trace d'injection de panne PCM, de repli WAV ou d'annulation nouvellement communiquée ; ne pas affirmer leur exécution par l'agent. |
| **REC-011** | P1 | À faire | **Done** | Voix Étincelle / sept intentions acceptées par le propriétaire pour la carte nommée le 21/11. | Pas d'échantillon audio, de mesure du pitch ou de grille d'écoute attachés. |
| **DEV-002** | P1 | À valider | **Done** | Correctif Chromium/PWA documenté dans [passation r20](2026-11-20-codex-avatar-mobile-r20.md) ; `REC-019` acceptée sur Android le 20/11 ; validation DEV le 21/11. | Version exacte du mobile et métriques graphiques non disponibles. |
| **DEV-009** | P1 | À valider | **Done** | Reproduction, modification et passation du test micro dans [audit OPS](2026-11-20-codex-audit-ops.md) et [validation develop](2026-11-20-codex-validation-develop.md) ; propriétaire accepte la clôture le 21/11. | Aucun nouveau log de test micro FFmpeg/Rubber Band fourni dans cet échange. |
| **DEV-013** | P1 | À valider | **Done** | Implémentation de la sélection du contexte 24 h et curation par lots documentée dans [PR #34](https://github.com/goldaj/jade-vtuber/pull/34) ; validation propriétaire le 21/11. | Absence de nouvelles mesures chiffrées de coût/contexte ou logs de continuité ; `REC-010` reste une recette distincte. |
| **DEV-014** | P1 | À valider | **Done** | Repères de personnalité et récupération mémoire documentés dans [PR #34](https://github.com/goldaj/jade-vtuber/pull/34) ; validation propriétaire le 21/11. | Pas de journal d'essai relationnel joint ; les limites de confidentialité et de rappel restent surveillées par les recettes spécifiques ouvertes. |

## Passe de vérification et intégration

- **Vérification documentaire distincte :** confrontation des sept IDs, statuts précédents, critères, dépendances et traces existantes aux deux fichiers canoniques et à la [Definition of Done](../../backlog/DEFINITION_OF_DONE.md).
- **Résultat :** les sept cartes font l'objet de l'acceptation explicite du propriétaire. La validation ne prétend ni que ChatGPT a exécuté les scénarios matériels, ni que des logs absents ont été produits. Les limites individuelles sont conservées ci-dessus.
- **Livraison :** mise à jour des sept statuts sur la branche `develop`, sans modification de `main`.
- **Réouverture :** si un échec reproductible réapparaît sur l'un de ces scénarios, le documenter avec version/conditions observées puis rouvrir ou créer la carte pertinente. Les tickets voisins `REC-006`, `REC-010`, `REC-020`, `REC-023` restent distincts et ouverts.

