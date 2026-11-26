# Backlog opérationnel de Jade — source de vérité

**Arbitrage du 21/11/2026 :** les cartes exigeant le **microphone physique local du PC**, **Twitch** ou **OBS** sont suspendues en `Bloqué` jusqu'à nouvel ordre. Ce n'est **pas** une suspension générale des travaux sur Windows ni des tests Discord/Android/mémoire. Les sous-tests indépendants restent possibles, mais les cartes mixtes ne sont pas closes. [Passation](../operations/handoffs/2026-11-21-chatgpt-suspension-micro-twitch-obs.md).

**Recettes automatisées du 21/11/2026 :** `REC-021` et `REC-025` ont maintenant **des tests d'acceptation exécutés avec succès sous Linux et Windows**, [CI sur le SHA `955ca2e255`](https://github.com/goldaj/jade-vtuber/actions/runs/44947197393). **Mise à jour du 22/11/2026 :** les deux cartes sont maintenant **`Done` sur validation expresse du propriétaire**, avec réserves documentées ; aucune inspection nouvelle des archives privées n'est affirmée pour REC-025. La vue [REC](02-RECETTE.md#compte-rendu-des-recettes-automatiques-rec-021-et-rec-025-21-novembre-2026) décrit les preuves.

**Clôtures du 22/11/2026 :** `REC-021` (mémoire SQLite), `REC-025` (sauvegarde/restauration ciblée) et `REC-027` (sélection sociale hybride) sont **`Done`** par décision explicite du propriétaire. Réserves et preuves dans la [vue REC](02-RECETTE.md#clôture-propriétaire-du-22-novembre-2026--rec-021-rec-025-rec-027). `REC-020` (variantes d'intention A/B) a également été clôturée en **`Done`** sur validation explicite du propriétaire le 22/11/2026, [détails et réserves dans la vue REC](02-RECETTE.md#clôture-propriétaire-du-22-novembre-2026--rec-020).

**Recherche Internet Tavily (22/11) : REC-038 (P1) est `Done`**, après validation explicite du propriétaire attestant que Jade se connecte et recherche sur Internet. Les tests automatiques dédiés sont réussis ; les scénarios complémentaires non observés restent consignés comme réserves dans [la vue REC](02-RECETTE.md).

## REPRISE PRIORITAIRE — validations du 22 novembre 2026

**Priorité du 26 novembre 2026.** Le propriétaire valide le jeu mobile de Sérieuse et Enjouée et lance [ART-013](04-PRODUCTION-2D.md), P0, pour faire des oreilles une composante du jeu de Jade. Ce lot précède la reprise des dix variantes restantes.

**REC-031, REC-032, REC-033 et REC-034 sont `Done`**, après acceptation explicite du propriétaire. REC-032 l'était déjà à la suite de la validation mémoire ; REC-031/033/034 viennent d'être clôturées. Les limites documentées sont **acceptées pour cette version et ne sont pas déclarées corrigées**.

| Ordre | Ticket encore à valider | Vérification prioritaire |
| ---: | --- | --- |
| 1 | **REC-036** (P1) | Personnalité durable et cohérence entre sessions. |
| 2 | **REC-035** (P2) | Interventions en groupe, avec fils parallèles encore partiellement gérés. |
| 3 | **REC-037** (P2) | Configurer le superviseur Windows indépendant, puis tester redéploiement et redémarrage via PWA Android. |
| En parallèle | **DEV-010** (Done), **OPS-015** (Bloqué), ART-001 à ART-012 | DEV-010 clôturé le 22/11/2026 ; OPS-015 suspendu jusqu'à disponibilité de tokens Codex suffisants et décision de reprise du propriétaire ; travaux ART distincts. |

**NEW-20 est maintenant suivi dans DEV-031 (P2, En cours), pour des explications d'indisponibilité sans appel LLM supplémentaire.**

**DEV-032 (UX-19) → REC-039 (P2, Done le 22/11/2026)** : génération de fichiers mobile et Discord, en texte et vocal, intégrée sur `develop`. **Le propriétaire confirme explicitement après recette réelle que l'ensemble de l'US fonctionne**. Les deux parcours mobiles avaient été vérifiés avant le correctif ; les trois parcours Discord ont été acceptés globalement après activation du mode `all` par défaut. [Statut canonique REC-039](02-RECETTE.md). Aucun DEV-032 actif en parallèle. DEV-033/034/035 (PER-01/02/03, images) restent « À qualifier ». **NEW-16 (P2) est prise en charge dans [DEV-036](01-DEVELOPPEMENT.md), statut « En cours »** : rappels persistants, push Android en arrière-plan et ouverture ciblée codés ; recette réelle Android et configuration Web Push restent ouvertes ; l'idée n'est plus active dans le catalogue prospectif et les autres idées supprimées ne sont pas réintroduites.

**Lot vocal mobile — cadrage du 26/11 :** [REC-042](02-RECETTE.md) conserve la recette du PTT déjà livré. **DEV-040** porte le bouton Live ON/OFF dans Profil et la bascule ; **DEV-041** la voix originale. Le socle, l’audio, la fermeture au kill, le pont Jade, la restitution et les budgets sont répartis dans **DEV-046 à DEV-051**. [Plan et feuille de route prêts à coder](PLAN-LIVE-MOBILE.md) · [Critères canoniques des US](01-DEVELOPPEMENT.md#lot-p1-mobile--dialogue-vocal-naturel-et-économique-25-novembre-2026). **Prochaine étape de développement : DEV-046**, puis supervision/coûts avant exposition. Mobile uniquement, paramètre Discord réservé OFF ; cette passe a préparé la backlog sans implémentation ni appel facturé.

**Transferts du 23/11 : DEV-037 (NEW-29, sous-titres mobiles, P2) et DEV-038 (NEW-38, autonomie fonctionnelle, P1) sont À qualifier, sans développement lancé. Les deux anciennes idées ont été retirées du catalogue actif.**

**Lot mobile du 26/11 :** [REC-041](02-RECETTE.md) (P1, ancienne DEV-042) couvre la recette Android du zoom et du déplacement du r21. [DEV-043](01-DEVELOPPEMENT.md#dev-043--service-jade-indépendant-du-pc) et [DEV-044](01-DEVELOPPEMENT.md#dev-044--application-android-installable) (P2) couvrent la continuité sur VPS et le client Android. [REC-043](02-RECETTE.md) (P3, ancienne UX-20) couvre la recette de la secousse du r21. [Décisions et ordre proposé](../operations/handoffs/2026-11-26-codex-backlog-mobile.md)

**Quick wins engagés le 22/11 : DEV-027 (VIS-04) et DEV-028 (RTE-12) sont en développement sur `develop`.** **Élargissement validé le même jour : DEV-029 (VIS-07) en développement, DEV-030 (LAT-10) À faire.** Les idées prospectives correspondantes sont retirées de la liste active, sans duplication. La CI mémoire en cours de remise au vert est suivie séparément.

**Microphone physique du PC, Twitch et OBS restent suspendus** dans leurs cartes concernées. [Décision et limites](../operations/handoffs/2026-11-22-validation-rec031-rec033-rec034.md).

## Focus de travail léger (limite indicative : 3 tâches réellement « En cours »)

**Mise à jour du 22/11 :** les anciennes DEV-021 à DEV-026 sont suivies en REC-031 à REC-036. **REC-031/032/033/034 sont Done** sur validation du propriétaire ; **REC-035/036 restent À valider**. DEV-020 est REC-037, également À valider. Les réserves acceptées n'ont pas été réparées par ce changement de statut.

**Règle pratique :** viser au plus **trois tâches en cours simultanément**, sans en faire un verrou automatique ; les autres restent « À faire », « À qualifier » ou « Bloqué ». Mettre à jour la colonne **Statut** de la vue canonique, pas ce texte historique. Pas de cadence Scrum obligatoire ni de tableau parallèle.

---

**Référence :** `goldaj/jade-vtuber` · branche `develop` · créé le 18 novembre 2026.
**Périmètre :** tâches identifiées pour livrer, installer, recetter et maintenir **la Jade déjà en chantier**. **Ne pas confondre** avec les [97 idées prospectives restantes](../ameliorations/README.md), qui restent un catalogue distinct, ni avec les archives historiques.
**Photographie GitHub initiale :** aucune issue ni PR ouverte au relevé du 18 novembre ; les modules existants demeurent **codés** même sans recette physique. Les dernières CI hors ligne et le scan des secrets ont réussi au SHA `01c7551f8b4f4aae22e7e42a5a090fc05fbaac99`. Le PC, les clés et les comptes n'ont pas été inspectés par cet audit.

## Organisation retenue par le propriétaire

**Un backlog opérationnel unique et quatre vues de travail**, sans quatre listes indépendantes à synchroniser :

| Type | Vue | Objet | Nombre actuel |
| --- | --- | --- | ---: |
| `DEV` | [Développement](01-DEVELOPPEMENT.md) | Travaux de code, anomalies et développements déjà clôturés | 36 |
| `REC` | [Recette](02-RECETTE.md) | Acceptations des fonctionnalités codées, dont les anciennes cartes DEV déplacées | 43 |
| `OPS` | [Installation/Ops](03-INSTALLATION-OPS.md) | Préparer PC/Android, dépendances, comptes, sécurité, maintenance Git et passations | 16 |
| `ART` | [Production 2D](04-PRODUCTION-2D.md) | Finir le dessin/rig/physique/animations/export r21 | 13 |
| **Total** | | **Cartes uniques dans la vue priorisée ; OPS-012 est classée sans suite, hors vue** | **108** |

**Definition of Done officielle :** [lire les règles de clôture](DEFINITION_OF_DONE.md). Toute carte n'est **Done** que si les cinq exigences sont satisfaites, dont validation explicite par **Codex (tous ses modèles et sous-agents) OU le propriétaire**, **au moins un des deux**. L'intervention humaine n'est plus obligatoire si Codex a validé. La présence du code ou d'une CI verte ne clôture pas à elle seule une recette physique.

Les sous-tâches de recette et les étapes matérielles restent séparées lorsqu'elles fournissent une preuve indépendante. Une anomalie constatée ouvre une carte `DEV` liée à `REC` ; pas de duplication du développement livré. Les fichiers thématiques sont **canoniques pour le détail et le statut de chaque carte** ; la présente vue fournit le classement global. Lorsqu'une carte change de priorité, mettre à jour le détail puis le rang ici.

**Règle simple du propriétaire (21/11/2026) :** si une fonctionnalité est déjà développée et que seule son acceptation reste à faire, une **seule carte REC** porte le statut `À valider`. Pas de double suivi DEV Done / REC À valider. Anciens identifiants : `DEV-011 → REC-026`, `DEV-015 → REC-027`, `DEV-016 → REC-028`, `DEV-017 → REC-029`, `DEV-018 → REC-030`. Les cartes DEV encore à développer, bloquées ou Done restent inchangées.

## Deux jalons produit

### A · Jade actuelle opérationnelle

Une instance `--all-channels` réellement utilisable, son, Discord écrit/vocal, Twitch, micro PC, accès HTTP local et PWA Android, mémoire opt-in et rendu r20, avec tests des audiences, des coupures, du coût et des limites constatées. **Le r21 final n'est pas bloquant pour ce jalon.** Une preuve matérielle reste à collecter ; les fonctionnalités sont néanmoins codées dans `develop`.

### B · Jade visuellement aboutie

Modèle r21 plein pied utilisable, rig/physique, 14 motions propres, bundle exporté, intégration au runtime et calibration VTube Studio avec vérifications visuelles. Le travail peut progresser en parallèle du jalon A ; ne jamais effacer ni dévaloriser les checkpoints natifs v30/v31.

## Priorisation : valeur métier et dépendances

**P0** = débloque l'usage réel de la version actuelle ou traite un risque immédiat de confidentialité/fiabilité. **P1** = fort impact sur les fonctions importantes ou livraison r21. **P2** = améliorations utiles mais non indispensables au jalon A, ainsi que l'entretien, la documentation, les démonstrations et la gouvernance.

Le tri vise d'abord l'utilisabilité, puis le nombre de canaux concernés, l'impact d'un échec, les dépendances et seulement ensuite l'effort. **Le rang est une proposition de séquencement, pas un planning de sprint ni une permission de passer outre les prérequis.** Une carte conditionnelle (`DEV-002`, `DEV-003`) n'est pas une preuve qu'un bug s'est produit.

## Vue globale ordonnée

### P0 · 24 tâches

| Rang | ID | Jalon | Tâche | Vue |
| ---: | --- | --- | --- | --- |
| 1 | ART-013 | B | Faire vivre les oreilles du r21 au repos et dans les sept intentions | [ART](04-PRODUCTION-2D.md) |
| 2 | OPS-001 | A | Sécuriser l'état local avant intervention | [OPS](03-INSTALLATION-OPS.md) |
| 3 | OPS-002 | A | Mettre à jour develop et les assets LFS | [OPS](03-INSTALLATION-OPS.md) |
| 4 | OPS-003 | A | Installer/contrôler le socle Windows | [OPS](03-INSTALLATION-OPS.md) |
| 5 | OPS-005 | A | Préparer la configuration privée de tous les connecteurs | [OPS](03-INSTALLATION-OPS.md) |
| 6 | OPS-004 | A | Installer/actualiser le launcher réel | [OPS](03-INSTALLATION-OPS.md) |
| 7 | OPS-006 | A | Exécuter la validation technique locale | [OPS](03-INSTALLATION-OPS.md) |
| 8 | OPS-007 | A | Préparer le chemin microphone et lecture audio | [OPS](03-INSTALLATION-OPS.md) |
| 9 | OPS-008 | A | Préparer Discord texte/vocal et DAVE | [OPS](03-INSTALLATION-OPS.md) |
| 10 | REC-001 | A | Démarrer Jade entière en une instance | [REC](02-RECETTE.md) |
| 11 | REC-002 | A | Discord écrit et messages privés | [REC](02-RECETTE.md) |
| 12 | DEV-019 | A | Corriger les MP Discord écrits : réponse privée et identité réelle de chaque auteur | [DEV](01-DEVELOPPEMENT.md) |
| 13 | REC-003 | A | Discord vocal réel | [REC](02-RECETTE.md) |
| 14 | REC-004 | A | Microphone PC réel | [REC](02-RECETTE.md) |
| 15 | REC-005 | A | Isolation des sorties et confidentialité | [REC](02-RECETTE.md) |
| 16 | DEV-004 | A | Masquer les réponses privées dans les sous-titres OBS WAV | [DEV](01-DEVELOPPEMENT.md) |
| 17 | REC-026 | A | Demande naturelle de souvenir ordinaire ; Jade décide seule des Core Memories | [REC](02-RECETTE.md) |
| 18 | REC-008 | A | Commandes silence/reprise et interruption | [REC](02-RECETTE.md) |
| 19 | REC-006 | A | PCM Discord progressif sous --all-channels | [REC](02-RECETTE.md) |
| 20 | REC-007 | A | Repli WAV et absence de double diffusion | [REC](02-RECETTE.md) |
| 21 | REC-009 | A | Arbitrage multi-conversations | [REC](02-RECETTE.md) |
| 22 | REC-010 | A | Latence et coût d'une session réelle | [REC](02-RECETTE.md) |
| 23 | DEV-003 | A | Corriger la sortie indésirable du repli WAV s'il se produit réellement | [DEV](01-DEVELOPPEMENT.md) |
| 24 | REC-034 | Transverse | Mesure du temps réellement perçu, du coût et des p50/p95 par canal | [REC](02-RECETTE.md) |

### P1 · 62 tâches

| Rang | ID | Jalon | Tâche | Vue |
| ---: | --- | --- | --- | --- |
| 25 | REC-042 | A | Valider le push-to-talk classique mobile pendant l’appui (ancienne DEV-039) | [REC](02-RECETTE.md) |
| 26 | DEV-046 | A | Socle API Live, configuration par canal et Discord désactivé | [DEV](01-DEVELOPPEMENT.md) |
| 27 | DEV-048 | A | Cycle de vie, kill Android et fermeture fournisseur confirmée | [DEV](01-DEVELOPPEMENT.md) |
| 28 | DEV-051 | A | Budgets Live persistants et mesures de coût/latence | [DEV](01-DEVELOPPEMENT.md) |
| 29 | DEV-049 | Transverse | Personnalité, mémoire, histoire et délégations Live dans Jade | [DEV](01-DEVELOPPEMENT.md) |
| 30 | DEV-047 | A | Audio mobile Live, réveil local, pré-roll et interruption | [DEV](01-DEVELOPPEMENT.md) |
| 31 | DEV-050 | A | Chat, pièces jointes et avatar synchronisé sur le Live | [DEV](01-DEVELOPPEMENT.md) |
| 32 | DEV-040 | A | Activer le Live dans Profil et intégrer la bascule classique/Live | [DEV](01-DEVELOPPEMENT.md) |
| 33 | DEV-041 | A | Voix française originale de Jade par prompt | [DEV](01-DEVELOPPEMENT.md) |
| 34 | REC-031 | Transverse | Conscience unique Jade et actions intercanaux autorisées | [REC](02-RECETTE.md) |
| 35 | REC-033 | Transverse | Cache mémoire anticipé par présence et identité vérifiée | [REC](02-RECETTE.md) |
| 36 | REC-036 | Transverse | Personnalité durable, cohérente et corrigible | [REC](02-RECETTE.md) |
| 37 | REC-021 | A | Mémoire SQLite, Core et autobiographie | [REC](02-RECETTE.md) |
| 38 | DEV-012 | A | Donner au LLM de Jade le contrôle conscient et confirmé des écritures mémoire L2/L3 | [DEV](01-DEVELOPPEMENT.md) |
| 39 | REC-025 | A | Sauvegarde/restauration et suppression ciblée | [REC](02-RECETTE.md) |
| 40 | OPS-009 | A | Configurer Tailscale Serve privé | [OPS](03-INSTALLATION-OPS.md) |
| 41 | REC-014 | A | PWA Android texte et authentification | [REC](02-RECETTE.md) |
| 42 | OPS-010 | A | Installer les dépendances Live2D Web de la PWA | [OPS](03-INSTALLATION-OPS.md) |
| 43 | REC-019 | A | Avatar Web Android r20 | [REC](02-RECETTE.md) |
| 44 | REC-015 | A | PWA Android voix et micro | [REC](02-RECETTE.md) |
| 45 | REC-016 | A | PWA arrière-plan, connexion et réseau mobile | [REC](02-RECETTE.md) |
| 46 | REC-017 | A | TTS mobile désactivé | [REC](02-RECETTE.md) |
| 47 | OPS-011 | A | Préparer OAuth et authentification Twitch | [OPS](03-INSTALLATION-OPS.md) |
| 48 | REC-012 | A | Twitch IRC réel | [REC](02-RECETTE.md) |
| 49 | REC-013 | A | API HTTP locale authentifiée | [REC](02-RECETTE.md) |
| 50 | REC-011 | A | Voix Étincelle et sept intentions | [REC](02-RECETTE.md) |
| 51 | REC-018 | A | Avatar r20 Windows en rendu réel | [REC](02-RECETTE.md) |
| 52 | REC-020 | A | Variantes d'intention A/B | [REC](02-RECETTE.md) |
| 53 | REC-022 | A | Liaisons des comptes Discord/Twitch avec Goldaj | [REC](02-RECETTE.md) |
| 54 | REC-023 | A | Résilience des canaux et arrêt propre | [REC](02-RECETTE.md) |
| 55 | DEV-002 | A | Corriger une éventuelle incompatibilité SDK Live2D Web Android | [DEV](01-DEVELOPPEMENT.md) |
| 56 | ART-001 | B | Aligner la reprise Codex avec l'avancement artistique v31 | [ART](04-PRODUCTION-2D.md) |
| 57 | ART-002 | B | Identifier et sécuriser les sources r20/r21 | [ART](04-PRODUCTION-2D.md) |
| 58 | ART-003 | B | Corriger les UV et construire un atlas plein pied | [ART](04-PRODUCTION-2D.md) |
| 59 | ART-004 | B | Réparer les raccords cheveux, épaules, cou et vêtements | [ART](04-PRODUCTION-2D.md) |
| 60 | ART-005 | B | Corriger le clignement et les yeux | [ART](04-PRODUCTION-2D.md) |
| 61 | ART-006 | B | Finaliser tête, regard et rig du corps plein pied | [ART](04-PRODUCTION-2D.md) |
| 62 | ART-007 | B | Finaliser les physiques cheveux, oreilles et vêtements | [ART](04-PRODUCTION-2D.md) |
| 63 | ART-008 | B | Créer idle, expressions et règles de transitions r21 | [ART](04-PRODUCTION-2D.md) |
| 64 | ART-009 | B | Créer 14 motions corporelles originales | [ART](04-PRODUCTION-2D.md) |
| 65 | ART-010 | B | Réconcilier les sources éditables KRA/PSD avec le rig r21 | [ART](04-PRODUCTION-2D.md) |
| 66 | ART-011 | B | Créer le bundle r21 versionné et réutilisable | [ART](04-PRODUCTION-2D.md) |
| 67 | DEV-001 | B | Raccorder les 14 vraies motions r21 au runtime Jade | [DEV](01-DEVELOPPEMENT.md) |
| 68 | ART-012 | B | Importer, calibrer et recetter r21 dans VTube Studio | [ART](04-PRODUCTION-2D.md) |
| 69 | DEV-005 | A | Routage sans TTS pour Discord/Twitch/HTTP écrits | [DEV](01-DEVELOPPEMENT.md) |
| 70 | DEV-006 | A | Hotkey VTS asynchrone, sans retarder la voix | [DEV](01-DEVELOPPEMENT.md) |
| 71 | DEV-007 | A | Pool Realtime TTS partagé entre WAV et PCM | [DEV](01-DEVELOPPEMENT.md) |
| 72 | DEV-008 | A | Jalons de latence multi-canaux sans contenu privé | [DEV](01-DEVELOPPEMENT.md) |
| 73 | DEV-009 | A | Stabiliser le test micro synthétique avec Rubber Band | [DEV](01-DEVELOPPEMENT.md) |
| 74 | DEV-013 | ECO | Contexte historique 24 h sélectif et curation mémoire par lots | [DEV](01-DEVELOPPEMENT.md) |
| 75 | DEV-014 | ECO | Personnalité évolutive tirée des souvenirs autorisés | [DEV](01-DEVELOPPEMENT.md) |
| 76 | REC-027 | ECO | Participation sociale hybride locale et LLM optionnel | [REC](02-RECETTE.md) |
| 77 | REC-028 | ECO | Initiatives spontanées sur événement sans relance si ignorée | [REC](02-RECETTE.md) |
| 78 | REC-029 | ECO | Audio mobile PCM WebSocket et réponse progressive | [REC](02-RECETTE.md) |
| 79 | REC-030 | ECO | VAD locale et annulation mobile | [REC](02-RECETTE.md) |
| 80 | REC-038 | A | Recherche Internet Tavily interchangeable et journal privé exhaustif | [REC](02-RECETTE.md) |

| 81 | DEV-027 | A | Suspendre le rendu Live2D mobile hors écran | [DEV](01-DEVELOPPEMENT.md) |
| 82 | DEV-028 | Transverse | Confirmer les livraisons et fins de lecture dans les journaux | [DEV](01-DEVELOPPEMENT.md) |
| 83 | DEV-029 | A | Hystérésis du rendu Live2D mobile et reprise neutre (VIS-07) | [DEV](01-DEVELOPPEMENT.md) |
| 84 | DEV-030 | A | Harmonisation des délais TTS et lecture audio (LAT-10) | [DEV](01-DEVELOPPEMENT.md) |
| 85 | DEV-038 | Transverse | Connaissance des capacités et initiative autonome de Jade (NEW-38, P1) | [DEV](01-DEVELOPPEMENT.md) |
| 86 | REC-041 | B | Valider le zoom et le déplacement tactile de Jade r21 (ancienne DEV-042) | [REC](02-RECETTE.md) |

### P2 · 21 tâches

| Rang | ID | Jalon | Tâche | Vue |
| ---: | --- | --- | --- | --- |
| 87 | REC-032 | Transverse | Recherche de souvenirs ciblée, pertinente et sécurisée | [REC](02-RECETTE.md) |
| 88 | REC-035 | Transverse | Compréhension des apartés et fils de discussion de groupe | [REC](02-RECETTE.md) |
| 89 | REC-024 | A | Seule Démo Express distribuée | [REC](02-RECETTE.md) |
| 90 | OPS-015 | B | Étudier les redondances artistiques et outils inutiles | [OPS](03-INSTALLATION-OPS.md) |
| 91 | OPS-016 | Transverse | Vérifier secrets historiques, LFS, licences et provenance | [OPS](03-INSTALLATION-OPS.md) |
| 92 | OPS-014 | Transverse | Auditer les branches divergentes | [OPS](03-INSTALLATION-OPS.md) |
| 93 | OPS-013 | Transverse | Nettoyer les branches déjà intégrées | [OPS](03-INSTALLATION-OPS.md) |
| 94 | OPS-017 | Transverse | Réviser les protections de branches et fermer les passations | [OPS](03-INSTALLATION-OPS.md) |
| 95 | DEV-010 | B | Empêcher l'animation du rideau de déformer le cadre de la fenêtre mobile | [DEV](01-DEVELOPPEMENT.md) |
| 96 | REC-037 | Transverse | Choisir une branche Git et redéployer/redémarrer Jade depuis l'application mobile | [REC](02-RECETTE.md) |

| 97 | DEV-031 | Transverse | Explications d'indisponibilité sur demandes directes, PWA et client local (NEW-20) | [DEV](01-DEVELOPPEMENT.md) |

| 98 | REC-039 | A | Valider les fichiers téléchargeables PWA et Discord, texte et voix (UX-19, ancienne DEV-032) | [REC](02-RECETTE.md) |
| 99 | DEV-033 | A | Réception explicite d'images fixes par Jade (PER-01) | [DEV](01-DEVELOPPEMENT.md) |
| 100 | DEV-034 | A | Compréhension des images et du texte visible (PER-02) | [DEV](01-DEVELOPPEMENT.md) |
| 101 | DEV-035 | A | Réactions conversationnelles contextualisées aux images (PER-03) | [DEV](01-DEVELOPPEMENT.md) |
| 102 | DEV-036 | Transverse | Rappels persistants et notifications push Android (NEW-16), en cours | [DEV](01-DEVELOPPEMENT.md) |
| 103 | REC-040 | A | Valider les quatre onglets PWA, les rappels et la chambre plein écran | [REC](02-RECETTE.md) |
| 104 | DEV-037 | A | Sous-titres synchronisés de Jade dans l'application mobile (NEW-29, P2) | [DEV](01-DEVELOPPEMENT.md) |
| 105 | DEV-043 | Transverse | Faire fonctionner Jade sur VPS avec le PC éteint et le mobile sans avatar | [DEV](01-DEVELOPPEMENT.md#dev-043--service-jade-indépendant-du-pc) |
| 106 | DEV-044 | A | Livrer l’application Android installable (UX-14) | [DEV](01-DEVELOPPEMENT.md#dev-044--application-android-installable) |

| 107 | DEV-045 | B | Changer de coiffure à chaud sur Jade r21 dans l'application mobile | [DEV](01-DEVELOPPEMENT.md#dev-045--coiffures-interchangeables-en-temps-réel) |

### P3 · 1 tâche

| Rang | ID | Jalon | Tâche | Vue |
| ---: | --- | --- | --- | --- |
| 108 | REC-043 | B | Valider la réaction du r21 aux secousses du téléphone (ancienne UX-20) | [REC](02-RECETTE.md) |

### Décision classée sans suite (hors liste de priorisation)

**OPS-012 (P1, 22/11/2026)** : sauvegarde SQLite préalable aux migrations ou recettes mémoire **abandonnée sur décision du propriétaire**, sans reprise prévue à court terme. Les recettes automatisées REC-021/REC-025 ont été exécutées avec succès sur bases fictives, sans preuve d'une sauvegarde réelle de la base privée. La carte reste historiquement traçable dans la [vue OPS](03-INSTALLATION-OPS.md), mais n'est plus une tâche active et ne conditionne plus les recettes ouvertes.

## Workflow et statut canonique

**Règle de tri des recettes (décision propriétaire du 21/11/2026) :** automatisable → `À faire` / `En cours` puis preuves ; non automatisable dans l'environnement autorisé → **`À valider` directement** avec protocole manuel et limites renseignés. `À valider` n'affirme pas une recette réussie et ne vaut jamais `Done`. Les dépendances réellement bloquantes restent `Bloqué`. [Règle détaillée](DEFINITION_OF_DONE.md#application-par-type-de-carte).

La [Definition of Done officielle](DEFINITION_OF_DONE.md) est obligatoire sur **DEV, REC, OPS et ART**. La colonne **Statut** de chaque vue thématique est la **seule source de vérité opérationnelle du statut** ; ce tableau central est une vue de priorités. Chaque carte conserve aussi une *situation initiale* (à recetter, besoin de PC, conditionnelle, etc.), qui n'est pas son avancement.

| Statut | Règle |
| --- | --- |
| **À qualifier** | Fait matériel, périmètre ou anomalie encore à établir. |
| **À faire** | Travail recensé mais non démarré ; prérequis parfois manquants. |
| **En cours** | Réalisation ou tests réellement engagés. |
| **À valider** | Validation Codex **OU** propriétaire attendue ; pour les cartes `REC` non automatisables, **test manuel à exécuter** et décision attendue, sans prétendre disposer déjà des preuves. |
| **Bloqué** | Dépendance empêchant de progresser ou suspension explicite du propriétaire, avec cause et condition de reprise ; ne signifie pas échec. |
| **Done** | Cinq conditions de la [DoD](DEFINITION_OF_DONE.md) réunies, dont validation positive par au moins un des deux validateurs autorisés. |
| **Classée sans suite** | Cas devenu sans objet, abandonné ou non reproductible, avec justification ; ne vaut **pas** Done. |

**La revue Codex doit être une passe explicite, distincte de la réalisation.** Les modèles Terra/Astra/Sol et sous-agents sont des exécutants possibles de **Codex**, pas des validateurs séparés obligatoires. Une contre-revue indépendante est recommandée pour les cas sensibles, mais elle n'est pas imposée systématiquement. **ChatGPT en mode chat ne valide pas automatiquement une tâche à la place de Codex.**

Les statuts initiaux des 58 cartes sont ouverts : aucune n'est devenue Done lors de la création de cette règle. Les étiquettes de situation (`À recetter`, `À faire sur PC`, `Conditionnel`...) restent descriptives. Un défaut non reproduit se classe sans suite plutôt que d'inventer une réparation ; une fonction codée reste implémentée même quand sa carte REC est encore ouverte.

### Cartes, traçabilité et responsabilité

Chaque ligne contient un **ID stable** (`DEV-`, `REC-`, `OPS-`, `ART-`), une priorité, un jalon, un **statut**, la situation observée, le résultat attendu et les dépendances. Lorsqu'une carte est prise en charge, renseigner dans le document thématique ou la PR : responsable de réalisation, branche/SHA ou environnement, résultats et limites. **À la clôture**, la validation positive de **Codex OU du propriétaire** doit être traçable avec date et référence, via une [passation dédiée](../operations/handoffs/TEMPLATE.md) ou une PR explicitement liée à l'ID. Le validateur peut approuver plusieurs cartes en une seule passe en les nommant chacune. La vérification physique n'est pas déduite d'une CI hors ligne.

Les passations actives [entre agents](../operations/handoffs/README.md) servent à l'exécution et à la preuve, pas à maintenir un deuxième backlog. Les archives et anciennes PR sont des sources datées, non des demandes de travail automatiquement réactivées. Conserver `main` inchangée et le dépôt public ; aucune suppression de branche, activation de microphone ou modification privée sans contrôle/autorisation.

### Conditions de clôture adoptées

1. Réalisation complète selon les critères d'acceptation **applicables** à la carte.
2. Tests pertinents réellement exécutés, preuves et régressions concernées contrôlées.
3. Validation explicite par **Codex (modèle/sous-agent quelconque) OU le propriétaire**, au moins un des deux, dans une passe identifiable.
4. Intégration dans **`develop`** pour un changement de dépôt, ou application vérifiée sur le poste/service pertinent pour un travail local.
5. Traçabilité du statut, du validateur, des tests, des limites, des commits/PR et des guides affectés.

La DoD ne nécessite **ni une double validation, ni une validation humaine systématique, ni le merge vers `main`**. Les règles détaillées et les adaptations par type de tâche sont dans [DEFINITION_OF_DONE.md](DEFINITION_OF_DONE.md).

## Décision d'organisation

- **Backlog opérationnel** : ce dossier, les tâches engagées ou à recetter, les deux jalons, classement par valeur.
- **Catalogue des idées futures** : [docs/ameliorations](../ameliorations/README.md), sans création automatique de tickets de développement ou de recette.
- **Issue/PR GitHub** : à ouvrir quand une tâche est réellement prise en charge. Ne pas créer artificiellement des dizaines d'issues pour du travail non lancé.
- **Traçabilité des changements** : [AGENTS.md](../../AGENTS.md), [AGENT_COORDINATION.md](../operations/AGENT_COORDINATION.md), [CHANGELOG technique](../operations/CHANGELOG.md). Les modifications strictement documentaires ne nécessitent pas d'entrée de code inventée dans le changelog.
