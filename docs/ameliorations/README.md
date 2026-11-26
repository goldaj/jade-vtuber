# Catalogue des améliorations prospectives de Jade

**Référence :** `goldaj/jade-vtuber`, branche `develop`, état consolidé au **26 novembre 2026**. Ce catalogue contient uniquement des **propositions encore distinctes** ; elles ne constituent pas un ordre de développement, une recette en attente ni une autorisation de coûts API ou de mise en production. Le [backlog opérationnel](../backlog/README.md) est la source de vérité pour les travaux acceptés, les recettes, les OPS et le modèle 2D r21.

## État après dédoublonnage

- **192 idées initialement identifiées** dans 11 thèmes le 21/11/2026 (dont ajouts du 20 et du 21 novembre).
- **83 entrées retirées du catalogue actif** le 22/11/2026 : six transférées dans DEV, les autres déjà couvertes par une carte de backlog, par le code actuellement livré, ou absorbées dans une autre idée prospective conservée. Le détail des décisions figure dans [la passation de dédoublonnage](../operations/handoffs/2026-11-22-catalogue-dedoublonnage.md).
- **109 idées prospectives après le dédoublonnage**, puis **4 perspectives complémentaires différées** et une idée mobile additionnelle consignées le 22/11/2026 : **114 idées actives avant les deux présentes inscriptions**. Avec **L2D-01 (P1)** et **NEW-38 (P2)** : **116 idées prospectives actives avant promotion de VIS-04 et RTE-12** ; après leur transfert explicite en DEV-027 et DEV-028 le 22/11/2026 : **110 idées prospectives après les retraits précédents**, puis **104 idées actives dans 11 thèmes** après les six nouvelles décisions (retraits NEW-12 et NEW-19 ; promotions UX-19 et PER-01/02/03), après promotion supplémentaire de VIS-07 et LAT-10 vers DEV-029/DEV-030. Les identifiants retirés ne sont **pas** réattribués ; la version précédente reste consultable dans l'historique Git.
- Les six idées promues ont été codées via PR #38 et suivies désormais dans **`RTE-15 → REC-031`, `NRM-10 → REC-032`, `MEM-01 → REC-033`, `LAT-01 → REC-034`, `NEW-17 → REC-035`, `NEW-36 → REC-036`**, toutes À valider. Les ID DEV-021 à DEV-026 sont historiques.

## Idées encore actives par thème

| Thème | Document | Propositions actives | Périmètre restant |
| --- | --- | ---: | --- |
| Latence, voix | [01-LATENCE-VOIX.md](01-LATENCE-VOIX.md) | 12 | VAD Discord/PC, cache de prompt, qualité TTS, mesures côté lecteur et rapprochement des coûts, moteur vocal alternatif |
| Mémoire et présence | [02-MEMOIRE-PRESENCE.md](02-MEMOIRE-PRESENCE.md) | 7 | Personnes annoncées, présence serveur à arbitrer, mémoire partagée, curation qualitative et contrôles avancés |
| Canaux, concurrence | [03-CANAUX-ROUTAGE.md](03-CANAUX-ROUTAGE.md) | 10 | Routeur de sortie, tour non bloquant, annulation étendue, livraison, extensions Discord et intentions intercanaux avancées |
| Avatar, visibilité | [04-AVATAR-VISIBILITE.md](04-AVATAR-VISIBILITE.md) | 8 | Rendu conditionnel à la visibilité, filtrage par audience et économies GPU |
| Architecture IA | [05-ARCHITECTURE-IA.md](05-ARCHITECTURE-IA.md) | 7 | Moteurs/fournisseurs échangeables, contrats de modules, tests et comparaison de modèles |
| Produit, mobile | [06-PRODUIT-MOBILE.md](06-PRODUIT-MOBILE.md) | 3 | Reconnexion, Authenticator et solde prépayé. UX-14 est suivie en DEV-044 et UX-20 en REC-043. |
| Qualité, exploitation | [07-QUALITE-EXPLOITATION.md](07-QUALITE-EXPLOITATION.md) | 5 | Protection des anciennes archives, robustesse CI, tableau de supervision, rollback, exploitation Windows |
| Pilotage volontaire du modèle 2D | [08-MODELE-2D.md](08-MODELE-2D.md) | 1 | Commandes choisies par Jade, connaissance du résultat et arbitrage avec les animations automatiques |
| Perception multimodale | [09-PERCEPTION-MULTIMODALE.md](09-PERCEPTION-MULTIMODALE.md) | 7 | Consentement des images, sources vidéo, temporalité, réactions live et budgets ; PER-01/02/03 désormais en backlog |
| Données et normalisation | [10-NORMALISATION-DONNEES-MEMOIRE.md](10-NORMALISATION-DONNEES-MEMOIRE.md) | 10 | Contrats d'événements, données structurées, provenance, migrations |
| Capacités et comportement | [11-CAPACITES-COMPORTEMENT-CONTROLE.md](11-CAPACITES-COMPORTEMENT-CONTROLE.md) | 27 | Sécurité, outils et interactions sociales encore prospectifs ; NEW-29 et NEW-38 sont en backlog |
| **Total** | | **97** | |

**Décision supplémentaire du 22/11/2026 :** NEW-20 est transférée dans [DEV-031](../backlog/01-DEVELOPPEMENT.md) (explications d'indisponibilité), tandis que NEW-25 (proposition multilingue) a été **abandonnée** à la demande du propriétaire. Une recherche sur les 11 thèmes n'a trouvé aucune autre proposition de fonctionnalité multilingue à retirer. Les fonctions et contenus existants ne sont pas modifiés par cette décision.

**Quick wins transférés au backlog le 22/11/2026 :** VIS-04 → [DEV-027](../backlog/01-DEVELOPPEMENT.md) et RTE-12 → [DEV-028](../backlog/01-DEVELOPPEMENT.md). Il reste **21 idées P1** et aucune idée P0 dans le catalogue prospectif. Les lignes retirées restent visibles dans l'historique Git, sans réutiliser leurs identifiants. Les nouveaux transferts du même jour sont **VIS-07 → [DEV-029](../backlog/01-DEVELOPPEMENT.md)** et **LAT-10 → [DEV-030](../backlog/01-DEVELOPPEMENT.md)** ; seul DEV-029 a commencé.

## Décisions produit supplémentaires du 22 novembre 2026

- **NEW-12 retirée** du catalogue actif : fonctionnalité de recherche Internet déjà livrée, tracée et validée en [REC-038](../backlog/02-RECETTE.md) (Done). Il n'y a pas de seconde idée de recherche à développer.
- **NEW-19 abandonnée** : Jade doit conserver **une seule personnalité**, sans profils personnels concurrents selon les canaux. Les règles de confidentialité et de diffusion propres aux canaux ne sont pas des personas.
- **NEW-30 recentrée exclusivement sur les sondages Twitch** ; aucun quiz, mini-jeu, devinette ou sondage Discord. L'idée reste prospective et le développement Twitch reste suspendu.
- **NEW-16 reformulée puis transférée à [DEV-036](../backlog/01-DEVELOPPEMENT.md) le 22/11/2026** : rappels et notifications d'événements, à qualifier, sans démarrage. L'ancien ID est historique et n'est plus proposé dans la liste active.
- **UX-19 → [DEV-032](../backlog/01-DEVELOPPEMENT.md)** : pièces jointes et documents téléchargeables dans le chat PWA. **PER-01/02/03 → [DEV-033/034/035](../backlog/01-DEVELOPPEMENT.md)** : recevoir, comprendre et commenter des images. Quatre cartes P2 **À qualifier**, rien n'est développé avant cadrage. UX-19 est la première à discuter avec le propriétaire.
- **Règle du propriétaire :** une idée transférée en backlog ou explicitement écartée est immédiatement retirée des **lignes actives** du catalogue et de ses décomptes. Son identifiant reste traçable dans l'historique Git et les passations, mais **ne doit plus être proposée comme idée en attente**.

**Bilan historique après NEW-16 : 103 idées actives**, dont 21 P1. **État historique au 23/11 après NEW-29 et NEW-38 : 101 idées actives, dont 21 P1**. Les deux demandes ont été déplacées vers **DEV-037 (P2)** et **DEV-038 (P1)**, toutes deux **À qualifier**, sans développement engagé. [Passation détaillée](../operations/handoffs/2026-11-22-chatgpt-ux19-perceptions-catalogue.md).

## Évolutions différées acceptées le 22/11/2026

**Décision produit :** maintenir les solutions actuellement implémentées et les limites explicitement acceptées, sans acharnement ni chantier supplémentaire. Réserver **quatre améliorations distinctes, toutes P3 / D**, pour une étude éventuelle :

| ID prospectif | Plus-value réellement nouvelle | Prérequis de réexamen |
| --- | --- | --- |
| [RTE-18](03-CANAUX-ROUTAGE.md) | Compréhension d'actions intercanaux en langage libre, au-delà des commandes explicites de **REC-031** | Consentement, destination non ambiguë, droits, contrôle des erreurs, coût/latence acceptables |
| [NEW-37](11-CAPACITES-COMPORTEMENT-CONTROLE.md) | Évolution expérientielle réévaluée dans la durée, au-delà des repères mémoriels de **REC-036** | Choix autonome de Jade, réversibilité, absence de polling LLM sans interlocuteur, évaluation comportementale fiable |
| [LAT-21](01-LATENCE-VOIX.md) | Constater côté lecteur le premier signal utile effectivement programmé/consommé, au-delà des jalons de **REC-034** | Preuve technique réalisable ; **ne jamais confondre signal lu et audition physique certaine** |
| [LAT-22](01-LATENCE-VOIX.md) | Estimer et rapprocher les coûts réels des tours avec des données de facturation fournisseur, au-delà des tokens de **REC-034** | Granularité officiellement disponible ; coût **exact** jamais inventé quand les données manquent |

Ces quatre idées **ne rouvrent pas** REC-031, REC-034 ou REC-036, **ne constituent pas un manque bloquant** pour la version actuelle et ne promettent aucune capacité physiquement impossible. Elles ne seront engagées que sur nouvelle décision du propriétaire après vérification de l'intérêt, des risques de régression et des contraintes réelles. Pas de nouvel appel IA, de changement d'autorisation ou de mise en production par cette inscription.

Le [thème 08, modèle 2D](08-MODELE-2D.md) conserve l'archivage des anciennes idées ART et accueille désormais **L2D-01**, capacité prospective de pilotage volontaire du modèle par Jade, **distincte** du travail artistique suivi dans la [backlog ART](../backlog/04-PRODUCTION-2D.md). L'amélioration transversale **NEW-38** est désormais suivie dans [DEV-038](../backlog/01-DEVELOPPEMENT.md) en P1 et ne figure plus dans les idées actives.

## Transferts du 23 novembre 2026

- **NEW-29 → [DEV-037](../backlog/01-DEVELOPPEMENT.md), P2, À qualifier** : sous-titres des paroles de Jade en direct, synchronisés avec le flux audio de l'application mobile PWA.
- **NEW-38 → [DEV-038](../backlog/01-DEVELOPPEMENT.md), P1, À qualifier** : connaissance des fonctions exécutables, retour sur les actions réelles et initiative volontaire de Jade.
- Ces deux entrées sont retirées des tableaux prospectifs actifs ; elles conservent leur identifiant historique. Pas de développement lancé.

## Transferts du 25 novembre 2026

- **LAT-17, ARC-01, ARC-05 → [DEV-040](../backlog/01-DEVELOPPEMENT.md)** (P1, À faire) : dialogue vocal GPT-Live, session économique et bascule vers le mode classique, uniquement PWA Android. Les trois lignes P2 sont retirées du catalogue actif ; le mode écrit et les autres canaux ne sont pas engagés. LAT-11/15/20 ne conservent que leur périmètre résiduel hors mode Live mobile.
- Le lot inclut DEV-039 (vrai push-to-talk classique) et DEV-041 (voix française propre à Jade). **98 idées actives, dont 21 P1**, après ces trois transferts. Aucun développement ni dépense lancé.

## Règles pour les prochains agents

1. **Vérifier `develop` et les statuts canoniques avant tout ajout.** Un `Done` peut déjà être implémenté et validé, un `Bloqué` reste une carte en backlog, et une idée en apparence semblable peut parfois ajouter un périmètre réellement distinct. Ne pas recréer un travail existant.
2. **Une seule carte active pour un même travail.** Si le propriétaire décide d'engager une idée, la transférer vers la vue DEV/OPS/ART pertinente avec identifiant unique, priorité, état, dépendances, critères de recette et références historiques. Retirer sa **ligne active** du catalogue après transfert. Les recettes `REC` ne sont pas un doublon de code : les DEV terminés mais non acceptés y sont déplacés conformément à [AGENTS.md](../../AGENTS.md).
3. **Préserver seulement la valeur résiduelle des idées partiellement livrées.** Par exemple : la PWA montre déjà Jade r20, la voix mobile diffuse déjà du PCM, les décisions sociales hybrides sont codées, les souvenirs ont déjà une récupération sélective, et les repères de personnalité existent déjà. Les idées encore ouvertes précisent ce qu'elles apportent **en plus**, jamais une réimplémentation.
4. **Priorités et nature :** P0 indispensable/risque immédiat ; P1 impact élevé ; P2 amélioration structurante ; P3 option différée. `P` = nouvelle capacité, `E` = amélioration, `C` = contrôle, `D` = différée. La priorité du catalogue ne déclenche pas le développement.
5. **Respecter les contraintes existantes :** une seule instance Jade, aucune fuite de contexte entre personnes/canaux, Core Memories décidées par Jade, consentements et scopes, aucun polling LLM en veille sans interaction, pas de double TTS, pas d'appel API payant ni d'altération de `main` sans autorisation distincte.
6. **Conserver le lien historique.** Les anciennes lignes retirées sont accessibles dans Git ; ne pas réutiliser leurs ID même si une amélioration semblable est proposée plus tard.

## Références

- [Backlog opérationnel et index de priorités](../backlog/README.md)
- [Spécifications et recettes REC-031 à REC-036](../backlog/02-RECETTE.md)
- [Passation d'audit et traçabilité des 83 suppressions](../operations/handoffs/2026-11-22-catalogue-dedoublonnage.md)
- [État technique et coordination des agents](../../AGENTS.md)
- [Plan économique historique du 21/11](PLAN-ECONOMIE-API-20261121.md) : document de conception antérieur à plusieurs livraisons, **pas** un second backlog actif.
