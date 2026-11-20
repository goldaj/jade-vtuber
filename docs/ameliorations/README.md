# Catalogue centralisé des améliorations de Jade

**Branche de référence : develop. Date de création : 16 novembre 2026.**
**Statut : propositions et actions futures, PAS un ordre de développement ni de déploiement.** Le [backlog opérationnel distinct](../backlog/README.md) recense les développements nécessaires déjà identifiés, les recettes, les opérations et le r21 en cours de production. Ne pas ouvrir automatiquement une tâche opérationnelle pour chaque idée de ce catalogue.

Ce dossier rassemble les idées des conversations des 16, 18 et 20 novembre 2026 (latence, mémoire, routage, visibilité, modularité, perception multimodale et normalisation), ainsi que les pistes encore pertinentes repérées dans les audits, plans, passations et documents de modélisation. Les propositions sont confrontées au code réel de `develop` ; les doublons clairement identifiés et les prémisses obsolètes sont retirés ou réécrits.

**Décision du propriétaire : effectuer d'abord les tests sur son PC, sauf les cinq quick wins expressément autorisés le 19 novembre (DEV-003/005–008) ; les autres idées restent prospectives.** Toute fonction déjà codée dans `develop` est considérée implémentée, indépendamment du programme de recette. **Révision de cohérence du 18 novembre : 149 entrées d'origine dans 10 thèmes** (LAT-12 retirée, intégrée à RTE-07 ; IDs conservés pour traçabilité). **Ajout validé par le propriétaire : 36 nouvelles propositions NEW-01 à NEW-36**, soit **185 entrées dans 11 thèmes** (état du 18 novembre). **Le 20 novembre, trois demandes produit UX-15 à UX-17** ajoutent le modèle Live2D visible sur Android, un vrai décor animé produit avec des outils artistiques adaptés et une connexion mobile via Authenticator : **188 entrées au total, dans 11 thèmes**. **Nouvelle idée UX-18 (20 novembre 2026)** : affichage sécurisé du crédit API OpenAI et des dépenses sur mobile, portant le catalogue à **189 entrées dans 11 thèmes** ; NEW-04, NEW-10, NEW-18, NEW-24 et NEW-36 en **P1** ; 29 autres en **P2** ; NEW-34 et NEW-35 en **P3** (classement initial conservé). **Ajout du 20 novembre 2026 : RTE-15 (P1 / P), conscience opérationnelle unique et commandes intercanaux autorisées sans mélange ni divulgation des conversations : 190 entrées dans 11 thèmes.**

## Où trouver les idées

| Thème | Document | Périmètre |
| --- | --- | --- |
| Latence, STT, TTS et streaming | [01-LATENCE-VOIX.md](01-LATENCE-VOIX.md) | Mesures, micro/VAD, audio progressif, optimisations immédiates |
| Mémoire et présence des personnes | [02-MEMOIRE-PRESENCE.md](02-MEMOIRE-PRESENCE.md) | Préchargement Goldaj/Discord, mémoire en couches, confidentialité |
| Canaux, sorties et concurrence | [03-CANAUX-ROUTAGE.md](03-CANAUX-ROUTAGE.md) | Routage, confidentialité des audiences, conscience commune et actions autorisées entre canaux, files, arrêt |
| Avatar et intention | [04-AVATAR-VISIBILITE.md](04-AVATAR-VISIBILITE.md) | Affichage conditionnel, rendu suspendu, expression et voix |
| Moteur IA et architecture | [05-ARCHITECTURE-IA.md](05-ARCHITECTURE-IA.md) | Jade Realtime légère, interfaces extensibles, Luna différée |
| Expérience, mobile, installation | [06-PRODUIT-MOBILE.md](06-PRODUIT-MOBILE.md) | PWA Android, rendu Live2D, décor animé, connexion Authenticator, crédit API OpenAI, UX et installation |
| Recette, sécurité et exploitation | [07-QUALITE-EXPLOITATION.md](07-QUALITE-EXPLOITATION.md) | Tests PC réels, métriques, sauvegardes, CI, secrets et déploiement |
| Modèle artistique r21 | [08-MODELE-2D.md](08-MODELE-2D.md) | Rig final, export, 14 motions, tests Windows et Android |
| Perception visuelle et multimodale | [09-PERCEPTION-MULTIMODALE.md](09-PERCEPTION-MULTIMODALE.md) | Images statiques, lecture de textes/photos/dessins, flux vidéo/jeux/films et réactions en direct |
| Normalisation des données et mémoire | [10-NORMALISATION-DONNEES-MEMOIRE.md](10-NORMALISATION-DONNEES-MEMOIRE.md) | Formats canoniques, événements inter-modules, structure SQLite, indexation et récupération de souvenirs |
| Contrôle, comportement, autonomie et capacités complémentaires | [11-CAPACITES-COMPORTEMENT-CONTROLE.md](11-CAPACITES-COMPORTEMENT-CONTROLE.md) | 36 propositions NEW : contrôle des réponses publiques, participation sociale, retours humains, administration, recherche, tâches, intégrations et expressivité |

## Lecture du catalogue

- **Identifiant** : stable par idée et thème (LAT, MEM, RTE, VIS, ARC, UX, QUA, ART, PER, NRM, NEW) ; les futures PR peuvent le citer.
- **Priorité** : P0 = recette / risque ou prérequis incontournable ; P1 = gain rapide ou besoin produit explicite ; P2 = chantier structurant ; P3 = amélioration ultérieure. Ce n'est **pas** l'ordre automatique d'exécution.
- **Nature** : **P** = fonction nouvelle à concevoir ; **E** = amélioration d'une fonction déjà codée (donc considérée implémentée) ; **C** = contrôle, décision ou action d'exploitation sans affirmer une absence de fonction ; **D** = proposition différée.
- **Référence de statut** : si une fonctionnalité est raccordée au code de `develop`, elle est **implémentée**. Ne pas introduire une seconde distinction « fonctionnelle seulement si testée ». La configuration privée et les rapports QA sont des sujets distincts ; vérifier le code avant d'ajouter une idée.

Les critères mentionnés dans chaque thème sont des critères cibles ; les chiffres de latence évoqués en conversation sont **hypothétiques**, pas mesurés sur Jade. Les durées et économies ne doivent jamais être déclarées acquises sans mesure.

## Décisions produit à retenir en priorité

1. Une seule instance Jade conserve tous les connecteurs actifs simultanément : **aucun retour à un sélecteur de mode par plateforme**. **Cible RTE-15 (P1)** : état global de Jade cohérent et instructions entre canaux autorisées, sans fusionner les conversations ni divulguer les informations d'autres utilisateurs.
2. **Chaque réponse sort uniquement sur le canal et la modalité ayant reçu la question**, sauf demande explicite et autorisée. Cela remplace, comme cible future, l'ancien comportement de diffusion audio globale des messages écrits.
3. **Pas de Luna dans le MVP rapide** : privilégier un moteur conversationnel temps réel pour les échanges ordinaires ; prévoir une interface facultative pour un moteur de raisonnement avancé, à brancher plus tard.
4. **Précharger les souvenirs avant la parole** : Goldaj en session privée PC/mobile ; personnes annoncées pour une rencontre ; utilisateurs Discord présents/actifs selon leur identité et leur consentement.
5. **Ne rendre le modèle 2D que lorsqu'il a un affichage utile**, en distinguant disponibilité d'une fenêtre, diffusion OBS, salon Discord, application visible et vraie audience ; n'animer que les sorties concernées.
6. **Conserver l'intention vocale même sans avatar**, et ne jamais prononcer ses métadonnées.
7. **Mesurer avant de refondre** : première parole audible pertinente, réponse complète, médiane, p95, coût, CPU/GPU et fonctionnement multicanal.

## Chemin recommandé après la recette du PC

| Étape | Objectif | Conditions |
| --- | --- | --- |
| **0 — Maintenant** | Installer, connecter et recetter le runtime actuel sans modification de code | Périphériques réels, budget API borné, matrice sécurité/routage, latences p50/p95 |
| **1 — Corrections ciblées** | Routage par origine ; TTS uniquement si voix attendue ; corrections VAD/connexion TTS/observabilité | Tests de non-fuite et comparaison avant/après |
| **2 — Mémoire anticipée** | Gestionnaire unique d'identité, présence et cache L1/L2/L3 avec invalidation | Consentement, scopes, TTL, retour arrière et tests multi-personnes |
| **3 — Refondre le temps réel** | Moteur vocal et sortie en flux, orchestration concurrente et interruptions | Spike A/B mesuré contre le pipeline existant, coût par conversation |
| **4 — Rendu conditionnel** | Détection de visibilité, économie CPU/GPU, choix d'animations | Recette Twitch/OBS, Discord, PC et navigateur Android |
| **5 — Plus tard** | Raisonnement approfondi optionnel (Luna), mémoire très profonde et r21 final | Besoin produit réel, budget et conformité des assets |

Les phases peuvent se chevaucher techniquement, mais les preuves de validation ne doivent pas être anticipées.

## Gouvernance des idées

Lorsqu'une proposition est prise en charge, préciser dans sa ligne ou une PR : **responsable, branche, statut réel, critères d'acceptation, tests automatiques, tests physiques, mesure de coût/latence et décision de clôture**. Ne pas déplacer une idée en « fait » parce qu'une documentation, un mock ou un script existe. Réviser les guides obligatoires de develop lors des changements de code conformément à [AGENTS.md](../../AGENTS.md). Ne rien fusionner vers main sans demande explicite.

### Provenance des propositions

- **Conversations des 16 au 20 novembre 2026** : latence profonde, mémoire proactive, sortie exclusive par source, modèle 2D à visibilité conditionnelle, perception d'images/vidéos, architecture ultra modulaire, normalisation des interactions/souvenirs et **36 nouvelles capacités transverses priorisées par Goldaj** (5 en P1, 29 en P2, 2 en P3). **Ajouts du 20 novembre : UX-15/16/17/18 en P1 et RTE-15 en P1 ; UX-18 concerne le solde et les dépenses API OpenAI dans la PWA ; le PC reste hébergeur allumé en attendant un serveur 24/7 ultérieur.**
- **Code develop étudié** : main.py, output.py, realtime_tts.py, openai_services.py, orchestrator.py, dialogue.py, voice_turns.py, discord_text.py, discord_voice.py, memory_service.py, memory_store.py, mobile_gateway.py et avatar.py.
- **Plans et audits** : [plan de latence](../history/gpt6-jade/PLAN-LATENCE-20261110.md), [audit transverse](../history/gpt6-jade/AUDIT-TRANSVERSE-20261115.md), [audit DevOps](../history/gpt6-jade/AUDIT-DEVOPS-DEVELOP-20261115.md), [audit mobile/mémoire](../history/gpt6-jade/AUDIT-REVUE-MOBILE-MEMOIRE-20261115.md), [réconciliation du 16 novembre](../history/gpt6-jade/RECONCILIATION-CODE-CONFIG-DOCS-20261116.md), [plan produit](../history/gpt6-jade/ROADMAP-MVP-DISCORD-PRODUIT-MOBILE.md).
- **Passations et spécifications** : [mémoire](../history/gpt6-jade/HANDOFF-CODEX-MEMORY-20261115.md), [streaming](../history/gpt6-jade/HANDOFF-STREAMING-TTS-20261113.md), [intention Live2D](../history/gpt6-jade/LIVE2D-INTENT-ANIMATION-HANDOFF-20261115.md), [PC et Android](../history/gpt6-jade/HANDOFF-CODEX-MOBILE-20261115.md), [guide agents](../handbook/AI_HANDOFF.md).
- **Artistique et visibilité publique réelle** : [plan r21](../../jade-modeling/PLAN_MODELE_JADE.md), [qualité r21](../../jade-modeling/PLAN_QUALITE_PRO_20261113.md), [statut actuel du dépôt public](../publication/CURRENT_PUBLIC_STATUS.md). Les anciens plans de migration sont historiques.

### Contrôle de cohérence

Les notes des 10–15 novembre décrivent parfois une fonction alors en PR ou absente. Plusieurs ont depuis été intégrées dans develop (SQLite v3, PWA, Discord unifié, expressions r20 A/B, contrôles CI). **Ne pas rouvrir ces travaux sans vérifier le HEAD réel**. Un ancien incident CI, un écart historique main/develop ou une consigne de merge déjà satisfaite est un point de recontrôle, pas nécessairement une anomalie encore ouverte. Le dépôt est **déjà public et doit le rester** ; la **Démo Express est la seule démo distribuée**. Un fonctionnement réel de Jade n'est pas une deuxième démo.
