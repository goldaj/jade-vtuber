# Catalogue des améliorations prospectives de Jade

**Référence :** `goldaj/jade-vtuber`, branche `develop`, état consolidé au **22 novembre 2026**. Ce catalogue contient uniquement des **propositions encore distinctes** ; elles ne constituent pas un ordre de développement, une recette en attente ni une autorisation de coûts API ou de mise en production. Le [backlog opérationnel](../backlog/README.md) est la source de vérité pour les travaux acceptés, les recettes, les OPS et le modèle 2D r21.

## État après dédoublonnage

- **192 idées initialement identifiées** dans 11 thèmes le 21/11/2026 (dont ajouts du 20 et du 21 novembre).
- **83 entrées retirées du catalogue actif** le 22/11/2026 : six transférées dans DEV, les autres déjà couvertes par une carte de backlog, par le code actuellement livré, ou absorbées dans une autre idée prospective conservée. Le détail des décisions figure dans [la passation de dédoublonnage](../operations/handoffs/2026-11-22-catalogue-dedoublonnage.md).
- **109 idées prospectives après le dédoublonnage**, puis **4 perspectives complémentaires distinctes** consignées le 22/11/2026 après arbitrage de limites techniques : **113 idées prospectives actives**, dans 10 thèmes. Les identifiants retirés ne sont **pas** réattribués ; la version précédente reste consultable dans l'historique Git.
- Les six idées explicitement promues par le propriétaire sont maintenant **une carte DEV chacune** : `RTE-15 → DEV-021`, `NRM-10 → DEV-022`, `MEM-01 → DEV-023`, `LAT-01 → DEV-024`, `NEW-17 → DEV-025`, `NEW-36 → DEV-026`. Aucune n'a été développée dans le cadre de ce transfert documentaire.

## Idées encore actives par thème

| Thème | Document | Propositions actives | Périmètre restant |
| --- | --- | ---: | --- |
| Latence, voix | [01-LATENCE-VOIX.md](01-LATENCE-VOIX.md) | 14 | VAD Discord/PC, cache de prompt, qualité TTS, mesures côté lecteur et rapprochement des coûts, moteur vocal alternatif |
| Mémoire et présence | [02-MEMOIRE-PRESENCE.md](02-MEMOIRE-PRESENCE.md) | 7 | Personnes annoncées, présence serveur à arbitrer, mémoire partagée, curation qualitative et contrôles avancés |
| Canaux, concurrence | [03-CANAUX-ROUTAGE.md](03-CANAUX-ROUTAGE.md) | 11 | Routeur de sortie, tour non bloquant, annulation étendue, livraison, extensions Discord et intentions intercanaux avancées |
| Avatar, visibilité | [04-AVATAR-VISIBILITE.md](04-AVATAR-VISIBILITE.md) | 10 | Rendu conditionnel à la visibilité, filtrage par audience et économies GPU |
| Architecture IA | [05-ARCHITECTURE-IA.md](05-ARCHITECTURE-IA.md) | 9 | Moteurs/fournisseurs échangeables, contrats de modules, tests et comparaison de modèles |
| Produit, mobile | [06-PRODUIT-MOBILE.md](06-PRODUIT-MOBILE.md) | 4 | Reconnexion, Authenticator, client alternatif et solde prépayé si source officielle accessible |
| Qualité, exploitation | [07-QUALITE-EXPLOITATION.md](07-QUALITE-EXPLOITATION.md) | 5 | Protection des anciennes archives, robustesse CI, tableau de supervision, rollback, exploitation Windows |
| Perception multimodale | [09-PERCEPTION-MULTIMODALE.md](09-PERCEPTION-MULTIMODALE.md) | 10 | Photos, capture consentie, vidéo, temporalité, réactions et budgets |
| Données et normalisation | [10-NORMALISATION-DONNEES-MEMOIRE.md](10-NORMALISATION-DONNEES-MEMOIRE.md) | 10 | Contrats d'événements, données structurées, provenance, migrations |
| Capacités et comportement | [11-CAPACITES-COMPORTEMENT-CONTROLE.md](11-CAPACITES-COMPORTEMENT-CONTROLE.md) | 33 | Sécurité, outils, vie sociale avancée, évolution de personnalité expérientielle, multimodal, autonomie et interactions |
| **Total** | | **113** | |

## Évolutions différées acceptées le 22/11/2026

**Décision produit :** maintenir les solutions actuellement implémentées et les limites explicitement acceptées, sans acharnement ni chantier supplémentaire. Réserver **quatre améliorations distinctes, toutes P3 / D**, pour une étude éventuelle :

| ID prospectif | Plus-value réellement nouvelle | Prérequis de réexamen |
| --- | --- | --- |
| [RTE-18](03-CANAUX-ROUTAGE.md) | Compréhension d'actions intercanaux en langage libre, au-delà des commandes explicites de **DEV-021** | Consentement, destination non ambiguë, droits, contrôle des erreurs, coût/latence acceptables |
| [NEW-37](11-CAPACITES-COMPORTEMENT-CONTROLE.md) | Évolution expérientielle réévaluée dans la durée, au-delà des repères mémoriels de **DEV-026** | Choix autonome de Jade, réversibilité, absence de polling LLM sans interlocuteur, évaluation comportementale fiable |
| [LAT-21](01-LATENCE-VOIX.md) | Constater côté lecteur le premier signal utile effectivement programmé/consommé, au-delà des jalons de **DEV-024** | Preuve technique réalisable ; **ne jamais confondre signal lu et audition physique certaine** |
| [LAT-22](01-LATENCE-VOIX.md) | Estimer et rapprocher les coûts réels des tours avec des données de facturation fournisseur, au-delà des tokens de **DEV-024** | Granularité officiellement disponible ; coût **exact** jamais inventé quand les données manquent |

Ces quatre idées **ne rouvrent pas** DEV-021, DEV-024 ou DEV-026, **ne constituent pas un manque bloquant** pour la version actuelle et ne promettent aucune capacité physiquement impossible. Elles ne seront engagées que sur nouvelle décision du propriétaire après vérification de l'intérêt, des risques de régression et des contraintes réelles. Pas de nouvel appel IA, de changement d'autorisation ou de mise en production par cette inscription.

Le [thème 08, modèle 2D](08-MODELE-2D.md) est conservé comme **fiche d'archivage sans proposition active** : le travail artistique est déjà identifié et priorisé dans la vue [ART de la backlog](../backlog/04-PRODUCTION-2D.md).

## Règles pour les prochains agents

1. **Vérifier `develop` et les statuts canoniques avant tout ajout.** Un `Done` peut déjà être implémenté et validé, un `Bloqué` reste une carte en backlog, et une idée en apparence semblable peut parfois ajouter un périmètre réellement distinct. Ne pas recréer un travail existant.
2. **Une seule carte active pour un même travail.** Si le propriétaire décide d'engager une idée, la transférer vers la vue DEV/OPS/ART pertinente avec identifiant unique, priorité, état, dépendances, critères de recette et références historiques. Retirer sa **ligne active** du catalogue après transfert. Les recettes `REC` ne sont pas un doublon de code : les DEV terminés mais non acceptés y sont déplacés conformément à [AGENTS.md](../../AGENTS.md).
3. **Préserver seulement la valeur résiduelle des idées partiellement livrées.** Par exemple : la PWA montre déjà Jade r20, la voix mobile diffuse déjà du PCM, les décisions sociales hybrides sont codées, les souvenirs ont déjà une récupération sélective, et les repères de personnalité existent déjà. Les idées encore ouvertes précisent ce qu'elles apportent **en plus**, jamais une réimplémentation.
4. **Priorités et nature :** P0 indispensable/risque immédiat ; P1 impact élevé ; P2 amélioration structurante ; P3 option différée. `P` = nouvelle capacité, `E` = amélioration, `C` = contrôle, `D` = différée. La priorité du catalogue ne déclenche pas le développement.
5. **Respecter les contraintes existantes :** une seule instance Jade, aucune fuite de contexte entre personnes/canaux, Core Memories décidées par Jade, consentements et scopes, aucun polling LLM en veille sans interaction, pas de double TTS, pas d'appel API payant ni d'altération de `main` sans autorisation distincte.
6. **Conserver le lien historique.** Les anciennes lignes retirées sont accessibles dans Git ; ne pas réutiliser leurs ID même si une amélioration semblable est proposée plus tard.

## Références

- [Backlog opérationnel et index de priorités](../backlog/README.md)
- [Spécifications des six améliorations devenues DEV-021 à DEV-026](../backlog/01-DEVELOPPEMENT.md)
- [Passation d'audit et traçabilité des 83 suppressions](../operations/handoffs/2026-11-22-catalogue-dedoublonnage.md)
- [État technique et coordination des agents](../../AGENTS.md)
- [Plan économique historique du 21/11](PLAN-ECONOMIE-API-20261121.md) : document de conception antérieur à plusieurs livraisons, **pas** un second backlog actif.
