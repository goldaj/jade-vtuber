# Passation — transfert de six améliorations et dédoublonnage du catalogue (22/11/2026)

**Dépôt :** `goldaj/jade-vtuber` · **branche :** `develop` · **nature de l'intervention :** documentation/backlog uniquement, sans exécution du code, appel facturé, action sur le PC ni modification de `main`.

## Décision du propriétaire

Transférer les idées suivantes du catalogue prospectif vers la backlog opérationnelle pour les développeurs :

| Idée d'origine | Ticket unique canonique | Priorité | Statut initial | Périmètre restant |
| --- | --- | --- | --- | --- |
| RTE-15 | [DEV-021](../../backlog/01-DEVELOPPEMENT.md) | P1 | À faire | État global unique, actions ciblées intercanaux et séparation des audiences ; le runtime et les conversations de base existent déjà. |
| NRM-10 | [DEV-022](../../backlog/01-DEVELOPPEMENT.md) | P2 | À faire | Rappel pertinent et sécurisé au-delà du contexte sélectif déjà livré par DEV-013. |
| MEM-01 | [DEV-023](../../backlog/01-DEVELOPPEMENT.md) | P1 | À faire | Cache mémoire anticipé par présence, identité vérifiée, TTL, invalidation. |
| LAT-01 | [DEV-024](../../backlog/01-DEVELOPPEMENT.md) | P0 | À faire | Temps de réponse réellement perçu, métriques par canal et coût, au-delà de DEV-008. |
| NEW-17 | [DEV-025](../../backlog/01-DEVELOPPEMENT.md) | P2 | À faire | Sujets et destinataires multiples, au-delà de la sélection hybride déjà validée en REC-027. |
| NEW-36 | [DEV-026](../../backlog/01-DEVELOPPEMENT.md) | P1 | À faire | Personnalité durable et corrigeable, au-delà des repères ponctuels déjà livrés en DEV-014. |

Toutes ces cartes précisent **besoin, critères, tests, non-régression et dépendances** dans la vue [DEV](../../backlog/01-DEVELOPPEMENT.md). Les priorités du catalogue ont été conservées, pas augmentées arbitrairement.

## Audit de dédoublonnage du catalogue

**État initial :** 192 lignes d'idées actives dans 11 thèmes. **État final :** 109 lignes dans 10 thèmes actifs, donc **83 retraits**. Les 6 transferts ci-dessus font partie des 83 ; les **77 autres** sont des recouvrements de backlog/fonctions livrées ou des sous-périmètres déjà couverts par une idée prospective plus large. Les références d'ID d'origine ne doivent pas être réattribuées.

| Fichier du catalogue | Entrées retirées (nombre) | Justification et destination canonique / valeur conservée |
| --- | --- | --- |
| 01-LATENCE-VOIX | `LAT-01, LAT-05, LAT-06, LAT-07, LAT-09, LAT-16, LAT-18` (7) | LAT-01 → DEV-024. Pool TTS, PCM Discord/mobile, première implémentation early voice et mesures de voix déjà suivis par DEV-006/007/008, REC-006/011/029/030 et le code ; nouvelles pistes VAD, débit, annulation non-mobile et moteur alternatif restent. |
| 02-MEMOIRE-PRESENCE | `MEM-01, MEM-02, MEM-03, MEM-04, MEM-06, MEM-07, MEM-09, MEM-10, MEM-11, MEM-13, MEM-18` (11) | MEM-01 et ses exigences L1/L2, PC/mobile/Discord, TTL, invalidation → DEV-023 ; rappel, index et scopes → DEV-022 ; état SQLite déjà présent et isolations/liaisons suivies en REC-021/022 ; continuité intercanal → DEV-021. Maintien des personnes annoncées, présence de serveur optionnelle, qualité de curation, correction/export et mémoire publique future. |
| 03-CANAUX-ROUTAGE | `RTE-02, RTE-03, RTE-04, RTE-09, RTE-11, RTE-13, RTE-15` (7) | RTE-15 et redirection autorisée → DEV-021 ; TTS écrit et repli WAV corrigés (DEV-003/005, REC-006/007), sécurité/diffusion intercanaux suivies REC-005 Bloqué, filtrage visuel conservé dans VIS-13. Routeur complet RTE-01 et ordonnancement non bloquant RTE-05 restent prospectifs. |
| 04-AVATAR-VISIBILITE | `VIS-08, VIS-09, VIS-11, VIS-12` (4) | Intentions nettoyées, variantes A/B et rendu r20 déjà acceptés (REC-018/019/020) ; rig/14 motions/contrat r21 suivis en ART-001 à ART-012 et DEV-001. Filtrage et suspension des calculs visuels restent hors backlog. |
| 05-ARCHITECTURE-IA | `ARC-02, ARC-03, ARC-04, ARC-06, ARC-07, ARC-08, ARC-09, ARC-12` (8) | Interopérabilité et séparation des modules déjà portées par ARC-13/14/15 et NRM-01 ; comparaison voix par LAT-17, annulation par RTE-08, mesures par DEV-024 ; sélection locale/personnalité de base déjà codées et suivies (DEV-013/014, REC-027). Conserve les extensions modulaires réellement distinctes. |
| 06-PRODUIT-MOBILE | `UX-01, UX-02, UX-03, UX-04, UX-05, UX-06, UX-07, UX-08, UX-09, UX-11, UX-12, UX-13, UX-15, UX-16` (14) | Installation/launcher, authentification Tailscale, PWA texte/voix/r20, streaming mobile et démo sont dans OPS/REC/DEV existants. Maintenance remote → DEV-020 ; défaut rideau spécifique → DEV-010. Le projet de décor est intégré en première version ; Authenticator UX-17 et reconnexion UX-10 restent. |
| 07-QUALITE-EXPLOITATION | `QUA-01, QUA-02, QUA-03, QUA-04, QUA-05, QUA-07, QUA-08, QUA-09, QUA-12, QUA-13, QUA-15, QUA-16, QUA-17` (13) | Recettes E2E, confidentialité, latences, mémoire, SDK/licences, branches et contrôle documentaire déjà dans OPS/REC et DEV-024 ; protections develop contradictoires avec l'arbitrage propriétaire « develop libre ». Restent la rotation/ACL des archives, reproductibilité CI, supervision, rollback, exploitation Windows, tous plus précis qu'un doublon. |
| 08-MODELE-2D | `ART-01` à `ART-12` (12) | Ensemble du rig, physique, corps, motions, bundle et tests r21 suivi en ART-001 à ART-012 / DEV-001 ; intentions r20 REC-020. Fiche 08 conservée **sans idée active** pour la traçabilité. |
| 09-PERCEPTION-MULTIMODALE | **Aucun retrait** (0) | Images, vidéo et réaction visuelle consentie réellement nouveaux et hors backlog. |
| 10-NORMALISATION-DONNEES-MEMOIRE | `NRM-09, NRM-10, NRM-12` (3) | Recherche, rappel, filtrage de portée, invalidation et effacement → DEV-022 et DEV-023 ; contraintes de mémoire existantes dans REC-021/025. Reste la normalisation non triviale des événements et des faits, avec migrations futures. |
| 11-CAPACITES-COMPORTEMENT-CONTROLE | `NEW-10, NEW-11, NEW-17, NEW-36` (4) | NEW-10 déjà couvert par la politique sociale hybride (REC-027), NEW-11 par DEV-021, NEW-17 → DEV-025, NEW-36 → DEV-026. NEW-18 (retours explicites) reste une fonction différente ; NEW-16 a été **resserré** aux initiatives programmées futures, hors saluts déjà livrés. |
| **Total** | **83 entrées retirées** | **109 entrées encore actives** |

## Garde-fous de cohérence

- **Pas de suppression d'une idée au seul motif que son nom ressemble à une autre.** Les fonctionnalités déjà livrées et leurs évolutions futures ont été différenciées. Les extensions réellement distinctes restent dans le catalogue, même avec des dépendances proches.
- Les formulations historiques obsolètes dans les anciennes études peuvent subsister hors du catalogue actif ; **le code de `develop` et les statuts de la vue canonique priment**. L'index [README](../../backlog/README.md) est une vue de priorité, pas une deuxième colonne de statut.
- Les cartes `Bloqué` liées au micro physique PC/Twitch/OBS restent bloquées. Aucun retour à `Done` ni déblocage automatique.
- Si un agent estime qu'un élément supprimé couvre en réalité une exigence nouvelle non spécifiée, il doit comparer le diff Git historique, le code et les tickets actifs, puis proposer **une exigence résiduelle distincte** plutôt que ressusciter automatiquement l'idée d'origine.
- Ce travail est un **audit documentaire et de recoupements fonctionnels**, appuyé sur les descriptions du backlog et les modules concernés de `develop` ; il ne remplace pas un audit exhaustif ligne à ligne des fonctions, ni des tests d'intégration sur le PC.

**Documentation mise à jour :** [backlog DEV](../../backlog/01-DEVELOPPEMENT.md), [index backlog](../../backlog/README.md), [catalogue central](../../ameliorations/README.md), [guides agents](../../../AGENTS.md) et thèmes du catalogue.
