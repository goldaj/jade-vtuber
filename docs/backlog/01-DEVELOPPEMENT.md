# Développement logiciel engagé ou conditionnel — backlog opérationnel

**Branche :** develop · **Révision :** 20 novembre 2026 · **Type :** DEV.

Au relevé du 18 novembre, aucune issue/PR de développement ouverte ; un lot de quick wins a été réalisé le 19 novembre sur une branche dédiée et soumis à validation après CI verte. **DEV-004** couvre le correctif P0 des sous-titres OBS ; il ne remplace pas la recette physique **REC-005**. Les fonctionnalités existantes ne sont pas à recoder. Ce tableau distingue un travail futur **déjà nécessaire pour livrer le r21** des **anomalies candidates qui ne deviennent du développement qu'après reproduction en recette**. Il ne reprend pas par défaut les 185 idées futures.

**Priorité :** valeur et dépendances, pas un engagement de calendrier. **DoD officielle :** [règle de clôture commune](DEFINITION_OF_DONE.md). La situation initiale décrit le constat technique ; seul **Statut** indique l'avancement. Les critères spécifiques restent distincts de la DoD. **Validation positive par Codex (tout modèle ou sous-agent) OU par le propriétaire**, sans double approbation.

| ID | Prio | Jalon | Statut | Situation initiale | Tâche | Résultat attendu / vérification | Dépend de |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **DEV-001** | P1 | B | **Bloqué** | Bloqué par assets r21 | Raccorder les 14 vraies motions r21 au runtime Jade | Lorsque les assets ART-009/011 seront prêts : contrat de motions versionné, sélection de deux motions par intention, transitions, idle/replis r20, appels Windows et PWA, tests de non-régression. Ne pas considérer les expressions r20 A/B comme 14 motions. | ART-009, ART-011, REC-020 |
| **DEV-002** | P1 | A | **À valider** | Modèle absent sur Android. Échec PixiJS sous CSP et ordre de rendu Core 6 reproduits. | Afficher le modèle r20 dans la PWA | Correctif validé dans Chromium au format mobile, essai Android REC-019 à confirmer. [Passation](../operations/handoffs/2026-11-20-codex-avatar-mobile-r20.md). | OPS-010, REC-019 |
| **DEV-003** | P0 | A | **Done** | Lecture locale parallèle identifiée dans le code ; correctif préventif explicitement demandé, sans fuite matérielle prétendue. [Validation Codex](../operations/handoffs/2026-11-20-codex-validation-develop.md) | Supprimer la lecture locale du repli WAV Discord vocal | Uniquement Discord vocal autorisé ; absence de ffplay local ; révocation annule la lecture ; tests automatisés et REC-005/007 physiques distincts. | REC-005, REC-007 |
| **DEV-004** | P0 | A | **Bloqué** | Correctif WAV intégré. Le mode Discord vocal anticipé peut encore alimenter le fichier OBS. Travail OBS différé, [reproduction et reprise](../operations/handoffs/2026-11-20-codex-validation-develop.md#anomalies-différées). | Masquer les réponses privées dans les sous-titres OBS | Les DM Discord et sources privées restent absents des sous-titres OBS pendant la lecture ; les sorties publiques conservent les sous-titres. Recette physique REC-005 ouverte. | — |
| **DEV-005** | P1 | A | **Done** | [Validation Codex](../operations/handoffs/2026-11-20-codex-validation-develop.md) | Supprimer le TTS des réponses Discord/Twitch/HTTP écrites | Réponse écrite sans TTS local/Discord ; destinations planifiées alignées ; tests sans dépenses. | — |
| **DEV-006** | P1 | A | **Bloqué** | La voix démarre indépendamment. Deux hotkeys peuvent lire simultanément sur le même WebSocket. Travail VTS différé, [reproduction et reprise](../operations/handoffs/2026-11-20-codex-validation-develop.md#anomalies-différées). | Décorréler VTS de la voix | Hotkey facultatif asynchrone, sans retard de voix, annulé à la fermeture ; tests de blocage. | — |
| **DEV-007** | P1 | A | **Done** | [Validation Codex](../operations/handoffs/2026-11-20-codex-validation-develop.md) | Partager le pool Realtime TTS entre PCM et WAV | Pool existant injecté aussi dans la synthèse tamponnée ; tests du raccordement, sans répétition facturable. | — |
| **DEV-008** | P1 | A | **Done** | [Validation Codex](../operations/handoffs/2026-11-20-codex-validation-develop.md) | Mesurer les durées multi-canaux sans donnée privée | Jalons file/mémoire/LLM/diffusion/fin/erreur via JADE_LATENCY_LOG=1 ; tests toutes plateformes, désactivé par défaut. Premier son/STT/coût physique restent REC-010. | — |
| **DEV-009** | P1 | A | **À faire** | Le test micro synthétique fournit deux échantillons PCM. Avec FFmpeg et Rubber Band, le traitement du pitch échoue avant la lecture simulée. [Reproduction](../operations/handoffs/2026-11-20-codex-validation-develop.md#validation-locale) | Stabiliser le test micro de bout en bout avec Rubber Band installé | Utiliser un signal assez long pour le DSP ou isoler le DSP dans ce test de chaîne. Vérifier la simulation avec et sans le filtre installé. | OPS-006, REC-004 |

## Usage pour les agents

**Clôture :** suivre la [Definition of Done officielle](DEFINITION_OF_DONE.md). **Done** n'est autorisé qu'après une passe de vérification explicite et une validation positive par **Codex OU le propriétaire**, les deux autres garanties étant les preuves pertinentes et la traçabilité/intégration requises. La décision indique dans la passation/PR liée : ID(s), validateur, date, version/SHA ou asset, tests observés, limites et livraison. Aucune carte n'a été automatiquement clôturée lors de l'adoption de cette règle.



- Ne jamais confondre **fonction déjà codée mais non recettée** et **travail logiciel à développer**.
- Tout nouveau bug exige une observation reproductible : source, environnement/branche SHA, résultat réel vs attendu, impact, dépendance de recette et preuve sans contenu privé.
- La décision de prise en charge, la branche de travail et le responsable sont confirmés à l'ouverture ; ce document n'autorise aucune dépense, modification d'un poste local ou écriture dans main.
- Pour le r21 : préserver checkpoints natifs, sources et licences ; le dessin, le rig et les assets vont dans la [production 2D](04-PRODUCTION-2D.md), le câblage du runtime dans le [développement](01-DEVELOPPEMENT.md).

## Sources de référence

- [Code actuel et limites](../handbook/BRANCH_STATE.md)
- [PCM et mémoire](../operations/handoffs/2026-11-16-chatgpt-pcm-memoire-mobile.md)
- [Animation r21](../history/gpt6-jade/LIVE2D-INTENT-ANIMATION-HANDOFF-20261115.md)
- [Idées futures non engagées](../ameliorations/README.md)

Retour au [backlog opérationnel](README.md).

### Revue du lot du 19 novembre

La [PR #26](https://github.com/goldaj/jade-vtuber/pull/26) a livré le lot sur `develop`. La [validation Codex du 20 novembre](../operations/handoffs/2026-11-20-codex-validation-develop.md) clôt DEV-003/005/007/008 et consigne les travaux OBS/VTS différés sur DEV-004/006. Les recettes physiques REC-005/007/010 restent ouvertes.
