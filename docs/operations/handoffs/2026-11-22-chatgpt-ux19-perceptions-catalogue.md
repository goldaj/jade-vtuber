# Passation ChatGPT : arbitrages catalogue et backlog (22 novembre 2026)

**Portée** : décisions exclusivement documentaires sur `develop`, aucun changement d'application, de fournisseur, de configuration, de modèle, de token ou de branche `main`.

## Décisions confirmées du propriétaire

1. **NEW-30** : supprimer la portée « quiz / devinettes / mini-jeux / sondages Discord ». Ne garder comme idée prospective **que les sondages Twitch**, déclenchés si le compte et l'API le permettent, selon les autorisations de la chaîne. Le travail Twitch reste explicitement suspendu ; aucune réalisation demandée.
2. **NEW-19** : **abandonner** les profils comportementaux multiples. Jade conserve une **personnalité unique**, indépendamment des plateformes. Les règles d'audience, de confidentialité et de disponibilité ne créent pas des personnalités alternatives.
3. **NEW-16** : remplacer l'idée générique d'initiative planifiée par un **rappel/notification d'événement utile** : message Discord ciblé, ou notification sur l'application mobile si la plateforme et le consentement le permettent. Stocker à terme date/fuseau/destinataire autorisé, modification et annulation, reprises et déduplication ; ne pas affirmer une livraison non prouvée. Une notification simple ne nécessite pas d'appel LLM. **Ce n'est pas un ticket de développement pour le moment.**
4. **NEW-12** : **retirer** du catalogue actif, car la recherche Internet est déjà implémentée et marquée **Done** dans `REC-038`. Ne pas réouvrir une seconde US de recherche.
5. **UX-19** : transférer en **DEV-032 (P2, À qualifier)** ; **discuter et cadrer avec le propriétaire avant toute implémentation**. Besoin : documents/fichiers créés à la demande, pièces jointes téléchargeables dans le chat de la PWA, accès privé et durée de vie contrôlés. Les formats, capacités de génération, règles de stockage, UX et éventuels coûts ne sont pas encore arbitrés. Première fonctionnalité à cadrer ; **interdiction d'entamer les développements sur cette décision seule**.
6. **PER-01**, **PER-02** et **PER-03** : transférer respectivement en **DEV-033, DEV-034, DEV-035 (P2, À qualifier)**, sans développement. Ensemble des capacités : recevoir volontairement les images sur les canaux compatibles, comprendre leur contenu, réagir dans la conversation autorisée. Préserver l'ordre des images et les limites de perception. Le contrôle de consentement `PER-04` reste dans le catalogue comme garde-fou à appliquer, pas comme fonction livrée.
7. **Règle permanente de gouvernance** : toute idée explicitement transférée au backlog, déjà satisfaite par une carte Done ou explicitement écartée doit être **absente des lignes actives du catalogue**. L'historique Git et la passation permettent de comprendre ce qu'elle est devenue ; ne pas re-proposer ces idées comme si elles étaient encore à faire.

## Mise à jour de la comptabilité

| Emplacement | Avant | Après | Détail |
| --- | ---: | ---: | --- |
| Prospectives NEW actives | 32 | 30 | NEW-12 et NEW-19 retirées ; NEW-16 et NEW-30 reformulées |
| Prospectives mobile | 5 | 4 | UX-19 → DEV-032 |
| Prospectives perception | 10 | 7 | PER-01/02/03 → DEV-033/034/035 |
| Catalogue global | 110 | **104** | 21 idées P1 inchangées ; 6 P2 retirées |
| Cartes DEV | 19 | **23** | Quatre nouvelles P2 non commencées |
| Backlog global | 85 | **89** | Quatre nouvelles cartes au statut « À qualifier » |

## Ce qui reste à décider pour UX-19

Lors de la **prochaine discussion de cadrage**, établir les cas d'usage prioritaires et formats, le mécanisme de demande par Jade (texte, commande explicite ou outil), les données sources autorisées, l'affichage des pièces jointes et leur téléchargement, l'authentification et l'expiration des fichiers, les limites de taille, les erreurs et le mode de gestion des frais éventuels. **Aucune décision technique ne doit être présumée** avant cet échange.

## Contrôles

- Les lignes `NEW-12`, `NEW-19`, `UX-19`, `PER-01`, `PER-02`, `PER-03` sont supprimées des **tableaux actifs** de leurs thèmes.
- `NEW-16` et `NEW-30` demeurent actives, avec les seuls périmètres décidés.
- Les quatre cartes DEV sont uniques dans le backlog et dans l'index P2 ; aucune nouvelle carte de recette créée.
- Aucune modification de code, tests, utilisateurs, connecteurs ou configuration pendant cette mission ; les tests CI de documentation et le scan des secrets peuvent confirmer la non-régression documentaire.
