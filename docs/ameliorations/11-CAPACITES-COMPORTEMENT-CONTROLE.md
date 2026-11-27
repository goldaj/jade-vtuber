# Nouvelles capacités : contrôle, comportement, autonomie et interactions

**Historique :** 36 propositions NEW-01 à NEW-36 classées le 18/11/2026 ; extensions NEW-37 et NEW-38 ajoutées ensuite. **État du catalogue actif au 23/11 après transfert NEW-29/38 : 27 idées** : 3 P1 (NEW-04/18/24), 21 P2 et 3 P3 (NEW-34/35/37). Les idées NEW-20 (DEV-031), NEW-12 (déjà réalisée via REC-038), NEW-19 (écartée : une seule personnalité pour Jade) et NEW-25 (multilinguisme écarté) ont été retirées du catalogue. NEW-16 a été transférée à [DEV-036](../backlog/01-DEVELOPPEMENT.md) (rappels/notifications, À qualifier), NEW-30 reste limitée aux sondages Twitch. **NEW-29 → DEV-037 (P2)** et **NEW-38 → DEV-038 (P1)** sont maintenant suivies dans la [backlog DEV](../backlog/01-DEVELOPPEMENT.md) et ne figurent plus parmi les propositions actives.

**Statut : idées restantes à étudier, pas de nouveau code autorisé par ce catalogue.** Les mécanismes existants (files bornées, arrêt de session vocal, opt-in mémoire, contrôles de transport, expressions r20, sous-titres locaux, participation Discord 20 % / Twitch 30 %, etc.) doivent être conservés : les entrées ci-dessous couvrent seulement des extensions **non identifiées comme fonctionnalités complètes dans le code**. Vérifier l'état réel de `develop` lors de chaque prise en charge. Pour respecter l'identité de Jade, les contrôles de sortie publique doivent permettre la personnalité espiègle prévue, pas neutraliser systématiquement sa voix.

## A. Maîtrise opérationnelle, sécurité et gouvernance

| ID | Priorité / nature | Proposition et critères de réussite |
| --- | --- | --- |
| NEW-01 | P2 / P | **Plafonnement global des dépenses API** : budgets configurables par heure/jour/mois, plateforme, fournisseur et fonctionnalité ; comptabilisation de consommation estimée puis réelle, blocage de nouveaux appels facturables, réserves autorisées et notifications. Les quotas techniques existants ne suffisent pas à fixer un plafond monétaire ferme côté application ; les montants facturés peuvent être retardés ou différer de l'estimation. |
| NEW-02 | P2 / P | **Arrêt d'urgence global administrateur** : désactiver immédiatement nouvelles entrées, générations, sorties publiques et processus concernés, même quand le modèle IA est défaillant ; reprise explicite et diagnostics. Compléter les commandes vocales d'arrêt, l'annulation de tours et le shutdown existants sans court-circuiter leur sécurité. |
| NEW-03 | P2 / P | **Protection anti-abus multicanal** : quotas et temporisations par identité vérifiée, salon, serveur, source et période, détection de rafales/robots/sollicitations répétées ; dégradation contrôlée sans bloquer les échanges légitimes. Complète les files bornées et les cooldowns existants. |
| NEW-04 | **P1 / P** | **Contrôle des réponses publiques avant diffusion** : contrôler les phrases/segments avant texte publié ou audio prononcé afin d'éviter les fuites d'informations privées, accusations infondées, dérives graves ou provocations inadaptées. Règles configurables par contexte et canal, audit des refus, latence mesurée, compatibilité streaming, personnalité et humour préservés. Ne pas déclencher nécessairement un second appel LLM pour chaque réponse. |
| NEW-05 | P2 / P | **Défense transversale contre les injections de prompt et la manipulation de mémoire** : distinguer directives du propriétaire, messages publics, observations, résultats externes et souvenirs ; marquer la confiance/provenance et tester les scénarios adversariaux. Prolonge les protections déjà en place dans le dialogue et la curation. |
| NEW-06 | P2 / P | **Permissions centralisées et rôles** : propriétaire, modérateur/administrateur explicitement autorisé, utilisateur, invité ; actions et scopes déclarés, refus systématique hors droits, identité transport vérifiée. Réunir à terme les gardes aujourd'hui spécifiques à la mémoire/PWA/Discord. |
| NEW-07 | P2 / P | **Tests adversariaux reproductibles** : scénarios simulés de spam, usurpation, attaques par contenu, tentatives de fuite, épuisement d'API, manipulations de souvenirs et dérives publiques ; contrôles automatiques des garde-fous sans exposer de secrets ni effectuer d'appels payants. Distinct de la recette E2E générale. |
| NEW-08 | P2 / P | **Approbation humaine des actions sensibles** : cadre générique de confirmation à portée limitée, expiration et journalisation avant suppression de fichiers, envoi privé ou action externe à conséquences. **Condition bloquante avant l'activation de telles actions**, sans exiger de développer immédiatement ces fonctionnalités. |
| NEW-09 | P2 / P | **Cockpit de pilotage live** : interface privée montrant sessions, connexions, consommation, réponses en cours, modules activés et contrôles propriétaire pour suspendre/relancer. Distinct du tableau de mesures passif QUA-11 ; accès strictement authentifié. |

## B. Comportement social, apprentissage et continuité conversationnelle

| ID | Priorité / nature | Proposition et critères de réussite |
| --- | --- | --- |
| NEW-18 | **P1 / P** | **Apprentissage supervisé par retours humains** : accepter notes/retours du propriétaire ou participants autorisés sur réponses utiles, erronées, mal placées ou inadaptées ; rattacher chaque retour à son contexte, analyser les motifs récurrents, proposer des ajustements de comportement/prompts. Pas de mise à jour automatique irréversible du modèle, des permissions ou de la personnalité ; évaluer avant/après et respecter le droit à l'effacement. |
| NEW-32 | P2 / P | **Direction vocale expressive affinée** : rythme, pauses, emphase, nuances émotionnelles et prosodie au-delà des neuf intentions, compatibles avec les capacités réelles des différents fournisseurs TTS. |
| NEW-37 | **P3 / D** | **Évolution expérientielle et auto-évaluation ponctuelle de la personnalité** : étudier, en complément des repères dérivés des souvenirs de [DEV-026](../backlog/01-DEVELOPPEMENT.md), la capacité de Jade à réviser elle-même et graduellement goûts, habitudes et comportement après plusieurs expériences pertinentes **sur des événements autorisés**, plutôt qu'une simple reformulation de souvenirs. Prévoir provenance, observations longitudinales, contradiction/correction, historique réversible et comparaison de comportements avant/après. **Jade seule décide de ses Core Memories ; aucun utilisateur n'impose un trait**. Jamais de boucle LLM permanente en inactivité, d'auto-réécriture incontrôlée du prompt, ni d'apprentissage opaque ; envisager une analyse différée *seulement si* coût, stabilité, pertinence et gains sont démontrés. À distinguer de NEW-18 (retours humains) et de NEW-35 (banc d'expérimentation). |

## C. Connaissances, autonomie et tâches

| ID | Priorité / nature | Proposition et critères de réussite |
| --- | --- | --- |
| NEW-13 | P2 / P | **Bibliothèque documentaire choisie** : consultation/recherche sur fichiers Markdown, PDF, dépôts ou documents explicitement accessibles, indexation, provenance, contrôle d'accès, données temporaires séparées de la mémoire personnelle. |
| NEW-21 | P2 / P | **Gestion de tâches longues** : objectifs, étapes, états d'attente, reprise après interruption, rapports d'avancement exacts, journal des actions réalisées et autorisations par étape. Aucun travail autonome persistant implicite sans exécuteur/ordonnanceur explicite. |
| NEW-35 | P3 / D | **Laboratoire d'expérimentation conversationnelle** : scénarios reproductibles et jeux d'évaluation pour comparer prompts, modèles, routage et taux d'intervention, avec mesures de coût, latence, qualité et stabilité. Distinct du banc d'attaques NEW-07. |

## D. Twitch, Discord, stream et interaction collective

| ID | Priorité / nature | Proposition et critères de réussite |
| --- | --- | --- |
| NEW-14 | P2 / P | **Événements Twitch structurés** : ajout facultatif de sources EventSub/API adaptées pour raids, follows, abonnements, points de chaîne ou autres événements effectivement exposés ; événements normalisés, déduplication, authentification et contrôle de participation, en conservant l'IRC existant. |
| NEW-15 | P2 / P | **Prise en compte de la modération Discord/Twitch** : traiter des signaux de suppression, timeout et modération lorsqu'ils sont accessibles et autorisés ; éviter de répondre à des contenus modérés, respecter les décisions humaines. Pas de sanctions automatiques par défaut. |
| NEW-30 | P2 / P | **Sondages Twitch uniquement :** permettre à Jade, à terme, de proposer ou déclencher des sondages sur une chaîne Twitch explicitement autorisée, selon les capacités et permissions de l'API Twitch, puis d'annoncer un résultat réel sans l'inventer. Définir qui peut démarrer/terminer un sondage, limites de fréquence, règles de participation et comportement en cas d'indisponibilité. **Exclure les quiz, devinettes, mini-jeux et sondages Discord** : ces fonctionnalités ne sont pas souhaitées. Aucun développement engagé et Twitch reste soumis à sa suspension actuelle. |
| NEW-33 | P2 / P | **Pilotage optionnel des scènes OBS** : déclencher changements de scène, cadrages, overlays ou présentations selon événements autorisés, avec permissions, confirmations si nécessaires et retour au mode manuel. Différent de l'observation de visibilité VIS-02. |
| NEW-34 | P3 / D | **Réalisation autonome d'émissions** : préparer et enchaîner des segments de live, transitions et interventions ; reprendre la main en un geste, planifier sans frais non bornés, conserver validation humaine des actions sensibles. |

## E. Perception, audio, vidéo et expressivité

| ID | Priorité / nature | Proposition et critères de réussite |
| --- | --- | --- |
| NEW-23 | P2 / P | **Diarisation sur une source audio partagée** : distinguer plusieurs locuteurs sur un seul microphone ou flux, de manière prudente, sans confondre une identité vocale inférée avec un compte authentifié. Le vocal Discord dispose déjà d'identités de transport distinctes. |
| NEW-24 | **P1 / P** | **Compréhension des sons non verbaux** : rire, applaudissements, surprise ou événements acoustiques pertinents, avec niveau de confiance et réaction proportionnée ; ne pas déduire une identité ou un état émotionnel certain de simples sons. |
| NEW-26 | P2 / P | **Télémétrie de jeux structurée** : fournisseurs d'événements de jeu (scores, manches, victoires, etc.) lorsqu'une API ou source locale autorisée existe ; corréler avec le visuel sans supposer l'existence d'une API universelle. |
| NEW-27 | P2 / P | **Gestion de l'attention multimodale** : arbitrer entre événements vocaux, textuels, visuels et API en temps réel selon importance, coût, latence, consentement et priorité des conversations directes. Complète le TurnArbiter textuel existant et PER-09. |
| NEW-28 | P2 / P | **Gestuelle contextuelle non émotionnelle** : gestes de présentation, désignation d'éléments, orientation du regard, posture et synchronisation ; extension distincte des dix-huit mouvements associés aux intentions du r21. |
| NEW-31 | P2 / P | **Auto-calibration contrôlée** : comparer paramètres de VAD, durée des réponses, fréquence d'analyse et autres réglages sur mesures, proposer des ajustements ; validation humaine et retour arrière avant application. |

## F. Reproductibilité et qualité produit

| ID | Priorité / nature | Proposition et critères de réussite |
| --- | --- | --- |
| NEW-22 | P2 / P | **Rejeu déterministe des conversations** : rejouer hors ligne des événements et des décisions avec fournisseurs simulés, horloges et sources maîtrisées, afin de reproduire les régressions sociales, la concurrence et le routage ; pas de réutilisation de conversations privées sans autorisation. |

## Liens et conditions de lancement

- [Catalogue central](README.md) ; [architecture modulaire](05-ARCHITECTURE-IA.md) ; [routage](03-CANAUX-ROUTAGE.md) ; [qualité/exploitation](07-QUALITE-EXPLOITATION.md).
- [Mémoire et présence](02-MEMOIRE-PRESENCE.md) ; [perception multimodale](09-PERCEPTION-MULTIMODALE.md) ; [normalisation](10-NORMALISATION-DONNEES-MEMOIRE.md) ; [avatar](04-AVATAR-VISIBILITE.md).
- **Priorité est une décision du propriétaire, pas une permission d'implémentation**. Pour NEW-08, les validations préalables à des actions sensibles restent un prérequis de sécurité lorsque ces actions seront développées, même si l'idée est classée P2.
- **Ne pas dupliquer les fondations déjà codées** : vérifier le code de `develop` avant la conception. Compléter plutôt que recréer.
- Aucune action externe, surveillance, connexion, nouvelle dépense API, modification de permissions ou déploiement n'est autorisé par cette seule liste.

**Contrôle de cohérence au 23/11/2026 : 27 idées actives (3 P1 : NEW-04/18/24 ; 21 P2 ; 3 P3 : NEW-34/35/37).** NEW-12, NEW-19, NEW-20 et NEW-25 sont absentes du tableau actif. Les décisions et correspondances sont consignées dans la [passation de tri](../operations/handoffs/2026-11-22-chatgpt-ux19-perceptions-catalogue.md).
