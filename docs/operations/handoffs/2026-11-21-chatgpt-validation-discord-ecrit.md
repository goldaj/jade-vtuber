# Validation de l'écrit Discord — clôture DEV-019 et REC-002 (21 novembre 2026)

- **Décision :** le propriétaire de Jade a confirmé avoir testé le fonctionnement de la conversation écrite sur Discord, puis demandé explicitement de valider l'US et de la mettre en **Done**.
- **Branche de suivi :** `develop` du dépôt `goldaj/jade-vtuber`. Aucun changement du runtime ni de `main` dans cette clôture documentaire.
- **Livraison technique de référence :** [PR #35](https://github.com/goldaj/jade-vtuber/pull/35), précédemment intégrée à `develop`, concernant les réponses aux messages privés Discord (destination fiable, suivi d'envoi, logs sans contenu privé).
- **Passage en Done :** **DEV-019** (correctif des conversations écrites privées Discord) et **REC-002** (recette écrite Discord), sur acceptation du propriétaire en condition d'utilisation réelle.

## Preuves et portée

Le 20 novembre 2026, le propriétaire avait déjà validé la lecture et les réponses écrites en **salon Discord** ; le 21 novembre, un défaut de non-réponse dans les **MP Discord** avait été signalé, qualifié puis corrigé par la PR #35. Dans le présent échange du 21 novembre, le propriétaire indique : « j'ai pu tester le fonctionnement de jade en conversation écrite sur discord. On peut valider l'US et la mettre en done. »

Il s'agit d'une **validation utilisateur explicite du fonctionnement écrit Discord**, venant après le correctif des MP. Elle est retenue pour la clôture de la fonctionnalité et de sa recette correspondante. Aucun appel API, test PC, test Discord ou observation de session n'a été effectué par ChatGPT pendant cette opération de suivi.

## Limites non masquées

- Le retour ne précise pas séparément le résultat de chaque sous-scénario : salon / MP, deux comptes simultanés, cache DM absent, redémarrage, refus de permissions, texte long, non-duplication, mémoire isolée, absence de sortie vocale et absence de fuite OBS.
- Le SHA exact de la version exécutée sur le poste du propriétaire, la durée des tests et les journaux ne sont pas fournis ; le SHA de `develop` utilisé pour la **clôture documentaire** ne doit pas être confondu avec celui testé localement.
- **REC-005 reste Bloqué** : le propriétaire a explicitement reporté les tests liés à OBS ; le retour sur la conversation écrite ne prouve pas l'absence de fuite via OBS, ni ne lève la suspension. Les autres cartes liées à Twitch/micro PC restent inchangées.
- En cas de bug MP ou de confidentialité reproductible, créer ou rouvrir la carte concernée avec les conditions de reproduction, sans effacer cette validation historique.

## Contrôle documentaire distinct

Le statut antérieur de **DEV-019** et **REC-002**, la PR de correction, le compte rendu de recette du 20 novembre et la [Definition of Done](../../backlog/DEFINITION_OF_DONE.md) ont été comparés. L'acceptation positive du propriétaire est conservée comme validation fonctionnelle ; les limites de preuve sont déclarées, non inventées. Les deux statuts canoniques sont mis à jour dans les vues [développement](../../backlog/01-DEVELOPPEMENT.md) et [recette](../../backlog/02-RECETTE.md).

**Validateur :** propriétaire de Jade, le 21/11/2026. **Exécutant du suivi :** ChatGPT, édition documentaire GitHub sur `develop`.
