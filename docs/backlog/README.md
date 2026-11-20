# Backlog opérationnel de Jade — source de vérité

## REPRISE PRIORITAIRE — première lecture au prochain token Codex

**Demandé par le propriétaire le 18 novembre 2026.** Cette liste est un **point d'entrée de reprise**, pas un second backlog ni une modification des P0/P1/P2. **Les cartes et leurs statuts canoniques restent dans les quatre vues** ci-dessous ; les références sont les mêmes. Toute intervention suit la [DoD](DEFINITION_OF_DONE.md). Ne pas marquer Done sans preuves et validation explicite par Codex ou le propriétaire.

| Ordre de reprise | Cartes existantes | Actions encore impossibles depuis le chat et prérequis |
| ---: | --- | --- |
| **1** | **OPS-001** | Sur le vrai PC Windows, vérifier `git status`, travaux locaux des agents, chemins sur D:, processus Jade et fichiers privés **avant toute synchronisation** ; ne rien effacer ni écraser. |
| **2** | **OPS-002, OPS-003, OPS-004, OPS-005, OPS-006** | Mettre à jour `develop` en avance rapide, vérifier Git LFS, dépendances, launcher installé et configuration privée, puis exécuter les tests et `--preflight --all-channels`. Ne pas afficher les secrets ni lancer des appels payants sans autorisation. |
| **3** | **REC-001 à REC-010, puis REC-011 à REC-025 selon dépendances** | Faire la **recette matérielle réelle** : Discord écrit/vocal, micro, streaming/repli audio et confidentialité en premier ; ensuite Twitch, SQLite, Android/Tailscale/SDK, r20, latence/coût. Utiliser le [format de preuve rapide](02-RECETTE.md#compte-rendu-de-recette-rapide) ; les tests simulés de CI ne suffisent pas. Une fuite constatée conditionne **DEV-003**, une incompatibilité Web r20 constatée conditionne **DEV-002**. |
| **4** | **OPS-013, OPS-014** | Nettoyer les **branches Git distantes** via une session Codex ayant les permissions : [audit du 18 novembre](../handbook/BRANCH_MAINTENANCE.md#audit-cible-du-18-novembre-2026). **14 branches ancêtres vérifiées**, 8 divergentes à examiner, 1 résultat indéterminé. Recontrôler pointes et PR avant chaque suppression ; ne jamais supprimer `develop`, `main` ou du travail unique. |
| **5** | **OPS-017** | Examiner avec droits d'administration la **protection minimale de `main`** (par exemple éviter suppression et force-push accidentels), sans imposer automatiquement une PR obligatoire et **sans modifier la visibilité publique**. Confirmer le réglage souhaité avec le propriétaire avant toute mutation de gouvernance ; le connecteur chat n'a pas l'action d'administration. |
| **6** | **OPS-015, OPS-016** | Sur D: et les objets Git LFS réels, examiner redondances artistiques, fichiers historiquement sensibles et provenance/licences ; éviter les suppressions sans preuve et toute exposition de secrets. |
| **Parallèle, jalon B** | **ART-001 à ART-012, DEV-001** | Reprendre le modèle r21 à partir des checkpoints natifs ; traiter notamment les UV/export plein pied, les assets et 14 motions. Ce chantier reste parallèle au jalon A, sans prétendre avoir validé Cubism/VTube Studio depuis le chat. |

**À ne pas recommencer :** le contrôle CI des liens et fichiers de `docs/backlog`, la simplification des règles de commit, cette file de reprise et le format de recette sont traités dans la présente intervention. Vérifier les [Actions GitHub](https://github.com/goldaj/jade-vtuber/actions) sur le dernier SHA avant de les considérer validés par la CI ; ne pas relancer un chantier logiciel déjà codé par simple absence de recette.

## Focus de travail léger (limite indicative : 3 tâches réellement « En cours »)

**Photographie du 18 novembre : 0 carte marquée « En cours ». Le lot DEV-003/005–008 du 19 novembre est suivi dans la vue DEV.** Les prochaines cartes à prendre sont **OPS-001**, puis **OPS-002** et **OPS-003** une fois le poste inventorié. `OPS-005` et `OPS-006` viennent ensuite selon leurs dépendances. Ne pas écrire « En cours » tant qu'un agent n'a pas commencé effectivement.

**Règle pratique :** viser au plus **trois tâches en cours simultanément**, sans en faire un verrou automatique ; les autres restent « À faire », « À qualifier » ou « Bloqué ». Mettre à jour la colonne **Statut** de la vue canonique, pas ce texte historique. Pas de cadence Scrum obligatoire ni de tableau parallèle.

---

**Référence :** `goldaj/jade-vtuber` · branche `develop` · créé le 18 novembre 2026.
**Périmètre :** tâches identifiées pour livrer, installer, recetter et maintenir **la Jade déjà en chantier**. **Ne pas confondre** avec les [185 idées prospectives](../ameliorations/README.md), qui restent un catalogue distinct, ni avec les archives historiques.
**Photographie GitHub initiale :** aucune issue ni PR ouverte au relevé du 18 novembre ; les modules existants demeurent **codés** même sans recette physique. Les dernières CI hors ligne et le scan des secrets ont réussi au SHA `01c7551f8b4f4aae22e7e42a5a090fc05fbaac99`. Le PC, les clés et les comptes n'ont pas été inspectés par cet audit.

## Organisation retenue par le propriétaire

**Un backlog opérationnel unique et quatre vues de travail**, sans quatre listes indépendantes à synchroniser :

| Type | Vue | Objet | Nombre actuel |
| --- | --- | --- | ---: |
| `DEV` | [Développement](01-DEVELOPPEMENT.md) | Câblage r21, anomalies, mémoire explicite et quick wins | 11 |
| `REC` | [Recette](02-RECETTE.md) | Tests de validation sur machines et comptes réels des fonctionnalités **déjà implémentées** | 25 |
| `OPS` | [Installation/Ops](03-INSTALLATION-OPS.md) | Préparer PC/Android, dépendances, comptes, sécurité, maintenance Git et passations | 17 |
| `ART` | [Production 2D](04-PRODUCTION-2D.md) | Finir le dessin/rig/physique/animations/export r21 | 12 |
| **Total** | | **Tâches uniques identifiées, incluant les quick wins du 19 novembre** | **65** |

**Definition of Done officielle :** [lire les règles de clôture](DEFINITION_OF_DONE.md). Toute carte n'est **Done** que si les cinq exigences sont satisfaites, dont validation explicite par **Codex (tous ses modèles et sous-agents) OU le propriétaire**, **au moins un des deux**. L'intervention humaine n'est plus obligatoire si Codex a validé. La présence du code ou d'une CI verte ne clôture pas à elle seule une recette physique.

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

### P0 · 21 tâches

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
| 14 | DEV-004 | A | Masquer les réponses privées dans les sous-titres OBS WAV | [DEV](01-DEVELOPPEMENT.md) |
| 15 | DEV-011 | A | Demande naturelle de souvenir ordinaire ; Jade décide seule des Core Memories | [DEV](01-DEVELOPPEMENT.md) |
| 16 | REC-008 | A | Commandes silence/reprise et interruption | [REC](02-RECETTE.md) |
| 17 | REC-006 | A | PCM Discord progressif sous --all-channels | [REC](02-RECETTE.md) |
| 18 | REC-007 | A | Repli WAV et absence de double diffusion | [REC](02-RECETTE.md) |
| 19 | REC-009 | A | Arbitrage multi-conversations | [REC](02-RECETTE.md) |
| 20 | REC-010 | A | Latence et coût d'une session réelle | [REC](02-RECETTE.md) |
| 21 | DEV-003 | A | Corriger la sortie indésirable du repli WAV s'il se produit réellement | [DEV](01-DEVELOPPEMENT.md) |

### P1 · 37 tâches

| Rang | ID | Jalon | Tâche | Vue |
| ---: | --- | --- | --- | --- |
| 22 | OPS-012 | A | Sauvegarder SQLite avant migration ou recette mémoire | [OPS](03-INSTALLATION-OPS.md) |
| 23 | REC-021 | A | Mémoire SQLite, Core et autobiographie | [REC](02-RECETTE.md) |
| 24 | REC-025 | A | Sauvegarde/restauration et droit à l'effacement | [REC](02-RECETTE.md) |
| 25 | OPS-009 | A | Configurer Tailscale Serve privé | [OPS](03-INSTALLATION-OPS.md) |
| 26 | REC-014 | A | PWA Android texte et authentification | [REC](02-RECETTE.md) |
| 27 | OPS-010 | A | Installer les dépendances Live2D Web de la PWA | [OPS](03-INSTALLATION-OPS.md) |
| 28 | REC-019 | A | Avatar Web Android r20 | [REC](02-RECETTE.md) |
| 29 | REC-015 | A | PWA Android voix et micro | [REC](02-RECETTE.md) |
| 30 | REC-016 | A | PWA arrière-plan, connexion et réseau mobile | [REC](02-RECETTE.md) |
| 31 | REC-017 | A | TTS mobile désactivé | [REC](02-RECETTE.md) |
| 32 | OPS-011 | A | Préparer OAuth et authentification Twitch | [OPS](03-INSTALLATION-OPS.md) |
| 33 | REC-012 | A | Twitch IRC réel | [REC](02-RECETTE.md) |
| 34 | REC-013 | A | API HTTP locale authentifiée | [REC](02-RECETTE.md) |
| 35 | REC-011 | A | Voix Étincelle et sept intentions | [REC](02-RECETTE.md) |
| 36 | REC-018 | A | Avatar r20 Windows en rendu réel | [REC](02-RECETTE.md) |
| 37 | REC-020 | A | Variantes d'intention A/B | [REC](02-RECETTE.md) |
| 38 | REC-022 | A | Liaisons des comptes Discord/Twitch avec Goldaj | [REC](02-RECETTE.md) |
| 39 | REC-023 | A | Résilience des canaux et arrêt propre | [REC](02-RECETTE.md) |
| 40 | DEV-002 | A | Corriger une éventuelle incompatibilité SDK Live2D Web Android | [DEV](01-DEVELOPPEMENT.md) |
| 41 | ART-001 | B | Aligner la reprise Codex avec l'avancement artistique v31 | [ART](04-PRODUCTION-2D.md) |
| 42 | ART-002 | B | Identifier et sécuriser les sources r20/r21 | [ART](04-PRODUCTION-2D.md) |
| 43 | ART-003 | B | Corriger les UV et construire un atlas plein pied | [ART](04-PRODUCTION-2D.md) |
| 44 | ART-004 | B | Réparer les raccords cheveux, épaules, cou et vêtements | [ART](04-PRODUCTION-2D.md) |
| 45 | ART-005 | B | Corriger le clignement et les yeux | [ART](04-PRODUCTION-2D.md) |
| 46 | ART-006 | B | Finaliser tête, regard et rig du corps plein pied | [ART](04-PRODUCTION-2D.md) |
| 47 | ART-007 | B | Finaliser les physiques cheveux, oreilles et vêtements | [ART](04-PRODUCTION-2D.md) |
| 48 | ART-008 | B | Créer idle, expressions et règles de transitions r21 | [ART](04-PRODUCTION-2D.md) |
| 49 | ART-009 | B | Créer 14 motions corporelles originales | [ART](04-PRODUCTION-2D.md) |
| 50 | ART-010 | B | Réconcilier les sources éditables KRA/PSD avec le rig r21 | [ART](04-PRODUCTION-2D.md) |
| 51 | ART-011 | B | Créer le bundle r21 versionné et réutilisable | [ART](04-PRODUCTION-2D.md) |
| 52 | DEV-001 | B | Raccorder les 14 vraies motions r21 au runtime Jade | [DEV](01-DEVELOPPEMENT.md) |
| 53 | ART-012 | B | Importer, calibrer et recetter r21 dans VTube Studio | [ART](04-PRODUCTION-2D.md) |
| 54 | DEV-005 | A | Routage sans TTS pour Discord/Twitch/HTTP écrits | [DEV](01-DEVELOPPEMENT.md) |
| 55 | DEV-006 | A | Hotkey VTS asynchrone, sans retarder la voix | [DEV](01-DEVELOPPEMENT.md) |
| 56 | DEV-007 | A | Pool Realtime TTS partagé entre WAV et PCM | [DEV](01-DEVELOPPEMENT.md) |
| 57 | DEV-008 | A | Jalons de latence multi-canaux sans contenu privé | [DEV](01-DEVELOPPEMENT.md) |
| 58 | DEV-009 | A | Stabiliser le test micro synthétique avec Rubber Band | [DEV](01-DEVELOPPEMENT.md) |

### P2 · 7 tâches

| Rang | ID | Jalon | Tâche | Vue |
| ---: | --- | --- | --- | --- |
| 59 | REC-024 | A | Seule Démo Express distribuée | [REC](02-RECETTE.md) |
| 60 | OPS-015 | B | Étudier les redondances artistiques et outils inutiles | [OPS](03-INSTALLATION-OPS.md) |
| 61 | OPS-016 | Transverse | Vérifier secrets historiques, LFS, licences et provenance | [OPS](03-INSTALLATION-OPS.md) |
| 62 | OPS-014 | Transverse | Auditer les branches divergentes | [OPS](03-INSTALLATION-OPS.md) |
| 63 | OPS-013 | Transverse | Nettoyer les branches déjà intégrées | [OPS](03-INSTALLATION-OPS.md) |
| 64 | OPS-017 | Transverse | Réviser les protections de branches et fermer les passations | [OPS](03-INSTALLATION-OPS.md) |
| 65 | DEV-010 | B | Empêcher l'animation du rideau de déformer le cadre de la fenêtre mobile | [DEV](01-DEVELOPPEMENT.md) |

## Workflow et statut canonique

La [Definition of Done officielle](DEFINITION_OF_DONE.md) est obligatoire sur **DEV, REC, OPS et ART**. La colonne **Statut** de chaque vue thématique est la **seule source de vérité opérationnelle du statut** ; ce tableau central est une vue de priorités. Chaque carte conserve aussi une *situation initiale* (à recetter, besoin de PC, conditionnelle, etc.), qui n'est pas son avancement.

| Statut | Règle |
| --- | --- |
| **À qualifier** | Fait matériel, périmètre ou anomalie encore à établir. |
| **À faire** | Travail recensé mais non démarré ; prérequis parfois manquants. |
| **En cours** | Réalisation ou tests réellement engagés. |
| **À valider** | Réalisation et preuves disponibles ; validation Codex **OU** propriétaire attendue, ainsi que l'intégration/traçabilité encore applicable. |
| **Bloqué** | Dépendance empêchant de progresser ; consigner le blocage et son déblocage prévu. |
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
