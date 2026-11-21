# Definition of Done officielle — Jade

**Statut : ADOPTÉE par le propriétaire le 18 novembre 2026.** Applicable aux tâches du [backlog opérationnel](README.md) sur `develop` (`DEV`, `REC`, `OPS`, `ART`). Ne pas confondre cette règle avec les critères d'acceptation individuels d'une carte, ni avec le [catalogue des améliorations futures](../ameliorations/README.md).

## Principe non négociable

Une tâche est **Done** uniquement quand **les cinq conditions ci-dessous sont remplies**, chacune selon sa nature :

1. **Réalisation complète** : tous les critères d'acceptation **applicables** de la carte sont satisfaits, que la tâche consiste à développer, recetter, configurer, documenter, dessiner ou produire un asset. Le code déjà implémenté reste implémenté même quand une recette dédiée n'est pas encore terminée.
2. **Tests pertinents et preuves** : les vérifications adaptées au travail ont été réellement effectuées et leurs résultats notés (réussites, échecs, limites). Vérifier les régressions liées à ce qui change, sans exiger par principe toute la suite du dépôt pour une simple documentation. **Ne jamais déclarer « testé sur PC », « testé sous Android », « validé dans Cubism/VTS » ou « approuvé » sans observation réelle ou preuve vérifiable.**
3. **Validation explicite par au moins l'un des deux** :
   - **Codex**, entendu comme **l'outil/écosystème Codex, quel que soit le modèle utilisé (Terra, Astra, Sol, etc.) ou le sous-agent compétent** ; **ou**
   - **le propriétaire de Jade**, par confirmation explicite.
   
   **Un seul de ces deux validateurs suffit**, sans obligation de validation humaine, sans revue systématiquement imposée par un autre modèle et sans double approbation. La vérification doit être une **passe explicite distincte de la réalisation**, avec une conclusion positive sur les résultats et les critères. L'auteur peut conduire cette passe via Codex, mais une contre-revue par un autre sous-agent/modèle est conseillée pour les changements sensibles, **non imposée**. **ChatGPT en mode conversationnel n'est pas, à lui seul, le validateur « Codex »** ; son compte rendu peut fournir des éléments de preuve, mais ne vaut pas approbation automatique.
4. **Intégration applicable** : les changements qui concernent le dépôt sont commités et intégrés dans **`develop`** avec le bon état, sans écraser les travaux d'autrui. Pour une tâche purement locale (installation PC, configuration privée, recette physique), le résultat est correctement appliqué et reproductible sur son environnement autorisé ; **aucun commit fictif n'est exigé**. La clôture sur `develop` **n'autorise pas de fusion vers `main`**.
5. **Traçabilité et documentation adaptée** : identifiant et statut de carte, résultat, vérifications, preuve de validation (qui, quand, sur quelle version/quel environnement), liens de commits/PR ou de passation si disponibles, limites et documentation réellement impactée sont à jour. Pour les changements techniques, suivre le [journal technique](../operations/CHANGELOG.md) et les consignes d'[AGENTS.md](../../AGENTS.md) ; ne pas modifier des guides sans rapport juste pour remplir une case.

**Aucune condition ne peut être remplacée par une simple affirmation « l'agent a fini »**, un merge ancien, un test simulé non représentatif ou la présence du code. Une validation en lot est autorisée si **chaque identifiant** couvert est explicitement cité et possède sa propre justification et ses preuves.

## Application par type de carte

| Type | « Réalisée » signifie | Tests/preuves attendus (selon pertinence) |
| --- | --- | --- |
| **DEV — Développement** | Correctif/fonction prévu(e) effectivement codé(e), livré(e) et raccordé(e) au runtime ; tests ciblés et régressions pertinentes ; défaut réel établi pour une carte conditionnelle | Tests de code, comportements observables, diff/commit, résultat CI si applicable, limites connues |
| **REC — Recette** | Scénarios d'acceptation exécutés dans l'environnement requis, sans prétendre que le code était absent avant ces essais | Résultats des scénarios sur vrai PC, Discord, Twitch, PWA, appareil audio ou SDK lorsque la carte les exige ; environnement et constat |
| **OPS — Installation/exploitation** | Configuration, opération ou analyse effectivement effectuée et résultat démontré ; secrets conservés hors du dépôt | Commande/vérification non sensible, état avant/après, preuve d'intégrité et de non-régression si pertinente |
| **ART — Production 2D** | Source, rig, motion ou export demandé(e) produit(e), conservé(e) et utilisable conformément aux critères de la carte | Rendu observé, validation native Cubism/VTS quand requise, inventaire d'assets, version du modèle, captures non sensibles ou résultat équivalent |

**Règle de routage des recettes adoptée le 21 novembre 2026 :** pour les cartes `REC`, tenter ou planifier d'abord la recette automatisée lorsque les scénarios sont automatisables dans un environnement autorisé. Si une recette nécessite inévitablement une observation humaine, du matériel ou des comptes réels impossibles à contrôler automatiquement pour cette validation, mettre **directement `À valider`** sans créer une attente fictive `À faire`. Préciser les scénarios à réaliser par le validateur, le motif du routage, les tests automatiques éventuellement disponibles et les limites. **`À valider` indique alors une action de recette manuelle encore à réaliser, pas une recette déjà exécutée ni une approbation.** Ne jamais substituer ce routage à la correction d'un bug ou au déblocage d'un prérequis. Une partie automatisable restante peut être exécutée sans créer de seconde carte. Les cinq conditions de `Done` restent inchangées.

**Cas particuliers** :
- Une tâche de **recette en attente** n'annule pas le statut « fonctionnalité codée » sur `develop` : seule la carte de recette reste ouverte.
- Si la carte **conditionnelle** concerne une anomalie non reproductible/absente, la requalifier et la **classer sans suite avec justification** ; ne pas inventer une correction et ne pas marquer « Done » comme si du développement avait été réalisé.
- Si le scénario `REC` nécessite une vérification humaine non automatisable, laisser la carte **ouverte en `À valider`** avec le test manuel attendu et les limites de preuve. Si une dépendance indispensable empêche même sa réalisation manuelle, utiliser **Bloqué** et documenter le déblocage. Une CI verte ne remplace pas la recette matérielle prévue.
- Si le périmètre ou les critères doivent changer, le consigner/faire arbitrer avant clôture ; ne pas transformer silencieusement un échec en réussite.
- La vérification indépendante est **recommandée** pour les risques de confidentialité, de données, de coût, de déploiement ou les changements structurels, mais **pas une sixième condition obligatoire**.
- Un accord pour classer Done n'est **pas** une autorisation implicite d'activer un microphone, d'appeler une API payante, de supprimer des fichiers/branches ou de déployer vers main.

## Workflow officiel

| Statut | Définition / transition |
| --- | --- |
| **À qualifier** | Périmètre, fait matériel ou défaut allégué à confirmer. |
| **À faire** | Travail connu, non commencé ; prérequis éventuellement encore à préparer. |
| **En cours** | Réalisation et tests engagés ; relever l'agent et la version. |
| **À valider** | Pour DEV/OPS/ART : réalisation et preuves disponibles, acceptation attendue. **Pour REC non automatisable : recette manuelle à effectuer par le validateur**, même en l'absence de nouvelle preuve matérielle ; ce statut ne préjuge pas du résultat. Dans tous les cas, attend validation explicite de Codex ou du propriétaire, selon les preuves adaptées, avant Done. |
| **Bloqué** | Dépendance réelle empêche la suite ; enregistrer cause, impact et prochain déblocage. Peut survenir à toute phase. |
| **Done** | Les **cinq conditions** ci-dessus sont vérifiées et la preuve de validation est consignée. |
| **Classée sans suite** | Cas exceptionnel pour tâche devenue sans objet/abandonnée après justification ; **ne signifie pas Done**. |

Les [quatre vues du backlog](README.md) portent l'état de chaque carte. Le tableau de rang global est une vue d'ordre et de priorité, **pas une seconde source de statut**. Ne jamais passer une carte en Done pour « vider la colonne ».

## Trace minimale lors de la clôture

Dans la ligne de backlog **mettre le statut à `Done`** et joindre une référence à la passation ou à la PR qui contient, pour chaque ID clôturé :

- **Réalisation** : résultat et critères d'acceptation satisfaits, ou mention explicite de chaque critère non applicable.
- **Preuves** : tests exécutés, environnement, branche/SHA ou version d'asset, résultats observés et limites ; ne pas inclure de secrets, données de mémoire, transcriptions privées ni fichiers personnels.
- **Validation** : **Codex (modèle/sous-agent ou session vérificatrice identifié si connu) OU propriétaire**, décision positive explicite, date et référence vérifiable. Si le même agent a réalisé et vérifié, distinguer clairement sa passe de revue.
- **Livraison** : commit/PR `develop` si applicable ; sinon l'état concret du PC, service ou asset ; documentation et passation impactées.

**Un seul validateur suffit même lorsque plusieurs tâches sont clôturées dans un lot**, mais le lot doit nommer tous les IDs qu'il valide. Un simple « OK global » sans identification des cartes ou sans résultats pertinents est insuffisant.

## Règles de gouvernance

- [AGENTS.md](../../AGENTS.md) demeure le point d'entrée des agents ; [AGENT_COORDINATION.md](../operations/AGENT_COORDINATION.md) définit la transmission et la mise à jour du travail.
- L'accès à `develop` et l'autorisation de modifier `main`, les fichiers privés, les comptes ou le PC sont des sujets **distincts** de la Definition of Done.
- Le propriétaire peut valider directement une tâche depuis des preuves suffisantes, sans attendre Codex. Inversement Codex peut valider sans intervention du propriétaire, si toutes les preuves requises existent réellement.
- La DoD s'applique **à partir de son adoption**, sans réécrire rétroactivement les preuves des anciennes PR ni déclarer Done les tâches initialement ouvertes.
