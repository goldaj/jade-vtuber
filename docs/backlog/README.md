# Backlog opérationnel de Jade — source de vérité

**Référence :** `goldaj/jade-vtuber` · branche `develop` · créé le 18 novembre 2026.
**Périmètre :** tâches identifiées pour livrer, installer, recetter et maintenir **la Jade déjà en chantier**. **Ne pas confondre** avec les [185 idées prospectives](../ameliorations/README.md), qui restent un catalogue distinct, ni avec les archives historiques.
**Photographie GitHub initiale :** aucune issue ni PR ouverte au relevé du 18 novembre ; les modules existants demeurent **codés** même sans recette physique. Les dernières CI hors ligne et le scan des secrets ont réussi au SHA `01c7551f8b4f4aae22e7e42a5a090fc05fbaac99`. Le PC, les clés et les comptes n'ont pas été inspectés par cet audit.

## Organisation retenue par le propriétaire

**Un backlog opérationnel unique et quatre vues de travail**, sans quatre listes indépendantes à synchroniser :

| Type | Vue | Objet | Nombre initial |
| --- | --- | --- | ---: |
| `DEV` | [Développement](01-DEVELOPPEMENT.md) | Câblage r21 ou anomalies à confirmer par recette, **pas** réimplémentation de code existant | 3 |
| `REC` | [Recette](02-RECETTE.md) | Tests de validation sur machines et comptes réels des fonctionnalités **déjà implémentées** | 25 |
| `OPS` | [Installation/Ops](03-INSTALLATION-OPS.md) | Préparer PC/Android, dépendances, comptes, sécurité, maintenance Git et passations | 17 |
| `ART` | [Production 2D](04-PRODUCTION-2D.md) | Finir le dessin/rig/physique/animations/export r21 | 12 |
| **Total** | | **Tâches uniques identifiées, après reclassement du recensement initial** | **57** |

Les sous-tâches de recette et les étapes matérielles restent séparées lorsqu'elles fournissent une preuve indépendante. Une anomalie constatée ouvre une carte `DEV` liée à `REC` ; pas de duplication du développement livré. Les fichiers thématiques sont **canoniques pour le détail et le statut de chaque carte** ; la présente vue fournit le classement global. Lorsqu'une carte change de priorité, mettre à jour le détail puis le rang ici.

## Deux jalons produit

### A · Jade actuelle opérationnelle

Une instance `--all-channels` réellement utilisable, son, Discord écrit/vocal, Twitch, micro PC, accès HTTP local et PWA Android, mémoire opt-in et rendu r20, avec tests des audiences, des coupures, du coût et des limites constatées. **Le r21 final n'est pas bloquant pour ce jalon.** Une preuve matérielle reste à collecter ; les fonctionnalités sont néanmoins codées dans `develop`.

### B · Jade visuellement aboutie

Modèle r21 plein pied utilisable, rig/physique, 14 motions propres, bundle exporté, intégration au runtime et calibration VTube Studio avec vérifications visuelles. Le travail peut progresser en parallèle du jalon A ; ne jamais effacer ni dévaloriser les checkpoints natifs v30/v31.

## Priorisation : valeur métier et dépendances

**P0** = débloque l'usage réel de la version actuelle ou traite un risque immédiat de confidentialité/fiabilité. **P1** = fort impact sur les fonctions importantes ou livraison r21. **P2** = entretien, documentation, démo et gouvernance sans blocage direct du jalon A.

Le tri vise d'abord l'utilisabilité, puis le nombre de canaux concernés, l'impact d'un échec, les dépendances et seulement ensuite l'effort. **Le rang est une proposition de séquencement, pas un planning de sprint ni une permission de passer outre les prérequis.** Une carte conditionnelle (`DEV-002`, `DEV-003`) n'est pas une preuve qu'un bug s'est produit.

## Vue globale ordonnée

### P0 · 19 tâches

| Rang | ID | Jalon | Tâche | Vue |
| ---: | --- | --- | --- | --- |
| 01 | OPS-001 | A | Sécuriser l'état local avant intervention | [OPS](03-INSTALLATION-OPS.md) |
| 02 | OPS-002 | A | Mettre à jour develop et les assets LFS | [OPS](03-INSTALLATION-OPS.md) |
| 03 | OPS-003 | A | Installer/contrôler le socle Windows | [OPS](03-INSTALLATION-OPS.md) |
| 04 | OPS-005 | A | Préparer la configuration privée de tous les connecteurs | [OPS](03-INSTALLATION-OPS.md) |
| 05 | OPS-004 | A | Installer/actualiser le launcher réel | [OPS](03-INSTALLATION-OPS.md) |
| 06 | OPS-006 | A | Exécuter la validation technique locale | [OPS](03-INSTALLATION-OPS.md) |
| 07 | OPS-007 | A | Préparer le chemin microphone et lecture audio | [OPS](03-INSTALLATION-OPS.md) |
| 08 | OPS-008 | A | Préparer Discord texte/vocal et DAVE | [OPS](03-INSTALLATION-OPS.md) |
| 09 | REC-001 | A | Démarrer Jade entière en une instance | [REC](02-RECETTE.md) |
| 10 | REC-002 | A | Discord écrit et messages privés | [REC](02-RECETTE.md) |
| 11 | REC-003 | A | Discord vocal réel | [REC](02-RECETTE.md) |
| 12 | REC-004 | A | Microphone PC réel | [REC](02-RECETTE.md) |
| 13 | REC-005 | A | Isolation des sorties et confidentialité | [REC](02-RECETTE.md) |
| 14 | REC-008 | A | Commandes silence/reprise et interruption | [REC](02-RECETTE.md) |
| 15 | REC-006 | A | PCM Discord progressif sous --all-channels | [REC](02-RECETTE.md) |
| 16 | REC-007 | A | Repli WAV et absence de double diffusion | [REC](02-RECETTE.md) |
| 17 | REC-009 | A | Arbitrage multi-conversations | [REC](02-RECETTE.md) |
| 18 | REC-010 | A | Latence et coût d'une session réelle | [REC](02-RECETTE.md) |
| 19 | DEV-003 | A | Corriger la sortie indésirable du repli WAV s'il se produit réellement | [DEV](01-DEVELOPPEMENT.md) |

### P1 · 32 tâches

| Rang | ID | Jalon | Tâche | Vue |
| ---: | --- | --- | --- | --- |
| 20 | OPS-012 | A | Sauvegarder SQLite avant migration ou recette mémoire | [OPS](03-INSTALLATION-OPS.md) |
| 21 | REC-021 | A | Mémoire SQLite, Core et autobiographie | [REC](02-RECETTE.md) |
| 22 | REC-025 | A | Sauvegarde/restauration et droit à l'effacement | [REC](02-RECETTE.md) |
| 23 | OPS-009 | A | Configurer Tailscale Serve privé | [OPS](03-INSTALLATION-OPS.md) |
| 24 | REC-014 | A | PWA Android texte et authentification | [REC](02-RECETTE.md) |
| 25 | OPS-010 | A | Installer les dépendances Live2D Web de la PWA | [OPS](03-INSTALLATION-OPS.md) |
| 26 | REC-019 | A | Avatar Web Android r20 | [REC](02-RECETTE.md) |
| 27 | REC-015 | A | PWA Android voix et micro | [REC](02-RECETTE.md) |
| 28 | REC-016 | A | PWA arrière-plan, connexion et réseau mobile | [REC](02-RECETTE.md) |
| 29 | REC-017 | A | TTS mobile désactivé | [REC](02-RECETTE.md) |
| 30 | OPS-011 | A | Préparer OAuth et authentification Twitch | [OPS](03-INSTALLATION-OPS.md) |
| 31 | REC-012 | A | Twitch IRC réel | [REC](02-RECETTE.md) |
| 32 | REC-013 | A | API HTTP locale authentifiée | [REC](02-RECETTE.md) |
| 33 | REC-011 | A | Voix Étincelle et sept intentions | [REC](02-RECETTE.md) |
| 34 | REC-018 | A | Avatar r20 Windows en rendu réel | [REC](02-RECETTE.md) |
| 35 | REC-020 | A | Variantes d'intention A/B | [REC](02-RECETTE.md) |
| 36 | REC-022 | A | Liaisons des comptes Discord/Twitch avec Goldaj | [REC](02-RECETTE.md) |
| 37 | REC-023 | A | Résilience des canaux et arrêt propre | [REC](02-RECETTE.md) |
| 38 | DEV-002 | A | Corriger une éventuelle incompatibilité SDK Live2D Web Android | [DEV](01-DEVELOPPEMENT.md) |
| 39 | ART-001 | B | Aligner la reprise Codex avec l'avancement artistique v31 | [ART](04-PRODUCTION-2D.md) |
| 40 | ART-002 | B | Identifier et sécuriser les sources r20/r21 | [ART](04-PRODUCTION-2D.md) |
| 41 | ART-003 | B | Corriger les UV et construire un atlas plein pied | [ART](04-PRODUCTION-2D.md) |
| 42 | ART-004 | B | Réparer les raccords cheveux, épaules, cou et vêtements | [ART](04-PRODUCTION-2D.md) |
| 43 | ART-005 | B | Corriger le clignement et les yeux | [ART](04-PRODUCTION-2D.md) |
| 44 | ART-006 | B | Finaliser tête, regard et rig du corps plein pied | [ART](04-PRODUCTION-2D.md) |
| 45 | ART-007 | B | Finaliser les physiques cheveux, oreilles et vêtements | [ART](04-PRODUCTION-2D.md) |
| 46 | ART-008 | B | Créer idle, expressions et règles de transitions r21 | [ART](04-PRODUCTION-2D.md) |
| 47 | ART-009 | B | Créer 14 motions corporelles originales | [ART](04-PRODUCTION-2D.md) |
| 48 | ART-010 | B | Réconcilier les sources éditables KRA/PSD avec le rig r21 | [ART](04-PRODUCTION-2D.md) |
| 49 | ART-011 | B | Créer le bundle r21 versionné et réutilisable | [ART](04-PRODUCTION-2D.md) |
| 50 | DEV-001 | B | Raccorder les 14 vraies motions r21 au runtime Jade | [DEV](01-DEVELOPPEMENT.md) |
| 51 | ART-012 | B | Importer, calibrer et recetter r21 dans VTube Studio | [ART](04-PRODUCTION-2D.md) |

### P2 · 6 tâches

| Rang | ID | Jalon | Tâche | Vue |
| ---: | --- | --- | --- | --- |
| 52 | REC-024 | A | Seule Démo Express distribuée | [REC](02-RECETTE.md) |
| 53 | OPS-015 | B | Étudier les redondances artistiques et outils inutiles | [OPS](03-INSTALLATION-OPS.md) |
| 54 | OPS-016 | Transverse | Vérifier secrets historiques, LFS, licences et provenance | [OPS](03-INSTALLATION-OPS.md) |
| 55 | OPS-014 | Transverse | Auditer les branches divergentes | [OPS](03-INSTALLATION-OPS.md) |
| 56 | OPS-013 | Transverse | Nettoyer les branches déjà intégrées | [OPS](03-INSTALLATION-OPS.md) |
| 57 | OPS-017 | Transverse | Réviser les protections de branches et fermer les passations | [OPS](03-INSTALLATION-OPS.md) |

## Workflow minimal

| Statut | Signification |
| --- | --- |
| **À qualifier** | Matérialité, portée ou dépendance encore incertaine. |
| **Prêt** | Travail clarifié, responsable et prérequis confirmés ; peut être pris en charge. |
| **En cours** | Intervention réellement engagée sur la branche/l'environnement identifiés. |
| **Bloqué** | Dépendance empêchant l'exécution ; documenter le blocage et son responsable. |
| **Terminé** | Clôture motivée et vérifiable ; **Definition of Done transversale encore à convenir avec le propriétaire**. |

Les étiquettes actuelles des vues (`À recetter`, `À faire sur PC`, `Conditionnel`, `À vérifier`, etc.) décrivent **la situation initiale** et ne signifient pas qu'un agent s'est officiellement approprié la tâche. Ne pas convertir arbitrairement une fonctionnalité codée en « non développée » du seul fait d'un essai manquant.

### Cartes, traçabilité et responsabilité

Chaque ligne contient un **ID stable** (`DEV-`, `REC-`, `OPS-`, `ART-`), une priorité, le jalon, la situation initiale, le résultat observable et les dépendances. À l'ouverture réelle d'une tâche, renseigner dans le document thématique ou la PR : responsable confirmé, branche et SHA, lien d'issue/PR si créé, date, environnement non sensible, preuves et éventuels blocages. **Attribution des agents non présumée :** Codex/Terra pour l'exécution possible sur PC, propriétaires pour permissions, comptes et acceptation ; experts 2D selon disponibilité. Ne jamais réserver un agent ou un sprint sans accord.

Les [passations actives](../operations/handoffs/README.md) servent à l'exécution, pas à maintenir un deuxième backlog. Les archives et anciennes PR sont des sources datées, non des demandes de travail automatiquement réactivées. Conserver `main` inchangée et le dépôt public ; aucune suppression de branche ou modification de configuration privée sans contrôle/autorisation.

### Definition of Done : à construire ensemble ensuite

**La DoD générale n'est PAS encore adoptée.** Aucun critère de clôture transversal nouveau n'est imposé à ce stade. Les critères de chaque carte sont des **résultats attendus / critères d'acceptation proposés** ; ils ne constituent pas à eux seuls une DoD.

Lors de la discussion prévue avec le propriétaire, définir séparément ce que « terminé » exige pour `DEV`, `REC`, `OPS` et `ART` : preuves, tests pertinents, mise à jour documentaire par impact, contraintes matérielles, gestion des dérogations et responsabilité d'acceptation. Ne pas marquer les 57 lignes « terminées » sur la seule présence du code, d'une PR fusionnée ou d'une ancienne CI réussie.

## Décision d'organisation

- **Backlog opérationnel** : ce dossier, les tâches engagées ou à recetter, les deux jalons, classement par valeur.
- **Catalogue des idées futures** : [docs/ameliorations](../ameliorations/README.md), sans création automatique de tickets de développement ou de recette.
- **Issue/PR GitHub** : à ouvrir quand une tâche est réellement prise en charge. Ne pas créer artificiellement des dizaines d'issues pour du travail non lancé.
- **Traçabilité des changements** : [AGENTS.md](../../AGENTS.md), [AGENT_COORDINATION.md](../operations/AGENT_COORDINATION.md), [CHANGELOG technique](../operations/CHANGELOG.md). Les modifications strictement documentaires ne nécessitent pas d'entrée de code inventée dans le changelog.
