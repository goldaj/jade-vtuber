# Nouvelles capacités : contrôle, comportement, autonomie et interactions

**Décision de priorisation du propriétaire — 18 novembre 2026.** Ajout des **36 propositions NEW-01 à NEW-36** formulées lors de la revue produit et architecture de Jade. **NEW-04, NEW-10, NEW-18, NEW-24 et NEW-36 sont P1** ; **NEW-34 et NEW-35 restent P3** comme dans la recommandation initiale ; **les 29 autres sont P2**, y compris les anciennes recommandations P0. La promotion explicite de NEW-36 en P1 prime sur son classement initial P3. Les priorités ci-dessous sont les décisions du propriétaire.

**Statut : idées à étudier et à concevoir, pas de code autorisé.** Les mécanismes existants (files bornées, arrêt de session vocal, opt-in mémoire, contrôles de transport, expressions r20, sous-titres locaux, participation Discord 20 % / Twitch 30 %, etc.) doivent être conservés : les entrées ci-dessous couvrent seulement des extensions **non identifiées comme fonctionnalités complètes dans le code**. Vérifier l'état réel de `develop` lors de chaque prise en charge. Pour respecter l'identité de Jade, les contrôles de sortie publique doivent permettre la personnalité espiègle prévue, pas neutraliser systématiquement sa voix.

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
| NEW-20 | P2 / P | **Explication compréhensible des incidents** : état d'indisponibilité, déconnexion ou capacité temporairement coupée indiqué seulement sur les canaux autorisés, sans affirmer qu'une action a abouti et sans transformer chaque panne en nouvelle génération payante. |

## B. Comportement social, apprentissage et continuité conversationnelle

| ID | Priorité / nature | Proposition et critères de réussite |
| --- | --- | --- |
| NEW-10 | **P1 / P** | **Participation sociale intelligente** : remplacer progressivement le taux fixe d'intervention spontanée par une décision contextualisée selon pertinence, rythme, participants, valeur ajoutée, conversation active et signaux de gêne. Conserver un réglage simple, un plafond de participation, les sollicitations explicites prioritaires et un mode déterministe de repli. Mesurer interventions utiles, interruptions inopportunes, latence et coût sur Discord/Twitch/vocal. |
| NEW-11 | P2 / P | **Continuité volontaire interplateformes** : reprendre une discussion entre Discord, mobile et PC uniquement si l'identité est liée/vérifiée, si les participants et audiences y consentent et si le transfert de contexte est explicitement autorisé ; ne pas fusionner automatiquement des salons. |
| NEW-17 | P2 / P | **Compréhension des conversations de groupe** : reconnaître les destinataires, sujets concurrents, apartés et occasions pertinentes d'intervenir ; garder l'isolement des sessions et les règles de confidentialité existantes. |
| NEW-18 | **P1 / P** | **Apprentissage supervisé par retours humains** : accepter notes/retours du propriétaire ou participants autorisés sur réponses utiles, erronées, mal placées ou inadaptées ; rattacher chaque retour à son contexte, analyser les motifs récurrents, proposer des ajustements de comportement/prompts. Pas de mise à jour automatique irréversible du modèle, des permissions ou de la personnalité ; évaluer avant/après et respecter le droit à l'effacement. |
| NEW-19 | P2 / P | **Profils comportementaux par contexte** : profils public Twitch, Discord, propriétaire privé, travail, etc., avec degré de spontanéité, style et règles de disponibilité différents ; ne pas multiplier les personas contradictoires ni affaiblir les invariants de sécurité. |
| NEW-32 | P2 / P | **Direction vocale expressive affinée** : rythme, pauses, emphase, nuances émotionnelles et prosodie au-delà des sept intentions, compatibles avec les capacités réelles des différents fournisseurs TTS. |
| NEW-36 | **P1 / P** | **Personnalité évolutive encadrée** : goûts, habitudes et références vécues enrichies progressivement grâce à la mémoire et aux retours, avec cohérence de la personnalité centrale, provenance, correction et consentement. Ne pas supposer qu'une LLM se réentraîne seule. |

## C. Connaissances, autonomie et tâches

| ID | Priorité / nature | Proposition et critères de réussite |
| --- | --- | --- |
| NEW-12 | P2 / P | **Recherche d'informations externes vérifiables** : accès facultatif et contrôlé à une recherche Web/documentaire, récupération des sources et dates, distinction entre faits consultés et suppositions ; limites de coût et résilience en cas d'indisponibilité. |
| NEW-13 | P2 / P | **Bibliothèque documentaire choisie** : consultation/recherche sur fichiers Markdown, PDF, dépôts ou documents explicitement accessibles, indexation, provenance, contrôle d'accès, données temporaires séparées de la mémoire personnelle. |
| NEW-16 | P2 / P | **Initiative conversationnelle autorisée** : Jade peut démarrer une intervention à partir d'événements définis ou d'une planification, selon horaires et audience, avec garde-fous de fréquence et interruption manuelle. Distinct de l'intervention spontanée pendant un échange en cours. |
| NEW-21 | P2 / P | **Gestion de tâches longues** : objectifs, étapes, états d'attente, reprise après interruption, rapports d'avancement exacts, journal des actions réalisées et autorisations par étape. Aucun travail autonome persistant implicite sans exécuteur/ordonnanceur explicite. |
| NEW-35 | P3 / D | **Laboratoire d'expérimentation conversationnelle** : scénarios reproductibles et jeux d'évaluation pour comparer prompts, modèles, routage et taux d'intervention, avec mesures de coût, latence, qualité et stabilité. Distinct du banc d'attaques NEW-07. |

## D. Twitch, Discord, stream et interaction collective

| ID | Priorité / nature | Proposition et critères de réussite |
| --- | --- | --- |
| NEW-14 | P2 / P | **Événements Twitch structurés** : ajout facultatif de sources EventSub/API adaptées pour raids, follows, abonnements, points de chaîne ou autres événements effectivement exposés ; événements normalisés, déduplication, authentification et contrôle de participation, en conservant l'IRC existant. |
| NEW-15 | P2 / P | **Prise en compte de la modération Discord/Twitch** : traiter des signaux de suppression, timeout et modération lorsqu'ils sont accessibles et autorisés ; éviter de répondre à des contenus modérés, respecter les décisions humaines. Pas de sanctions automatiques par défaut. |
| NEW-30 | P2 / P | **Interactions collectives structurées** : votes, sondages, quiz, devinettes et mini-jeux avec états, règles, temps de participation, isolation par salon et contrôle anti-abus. |
| NEW-33 | P2 / P | **Pilotage optionnel des scènes OBS** : déclencher changements de scène, cadrages, overlays ou présentations selon événements autorisés, avec permissions, confirmations si nécessaires et retour au mode manuel. Différent de l'observation de visibilité VIS-02. |
| NEW-34 | P3 / D | **Réalisation autonome d'émissions** : préparer et enchaîner des segments de live, transitions et interventions ; reprendre la main en un geste, planifier sans frais non bornés, conserver validation humaine des actions sensibles. |

## E. Perception, audio, vidéo et expressivité

| ID | Priorité / nature | Proposition et critères de réussite |
| --- | --- | --- |
| NEW-23 | P2 / P | **Diarisation sur une source audio partagée** : distinguer plusieurs locuteurs sur un seul microphone ou flux, de manière prudente, sans confondre une identité vocale inférée avec un compte authentifié. Le vocal Discord dispose déjà d'identités de transport distinctes. |
| NEW-24 | **P1 / P** | **Compréhension des sons non verbaux** : rire, applaudissements, surprise ou événements acoustiques pertinents, avec niveau de confiance et réaction proportionnée ; ne pas déduire une identité ou un état émotionnel certain de simples sons. |
| NEW-25 | P2 / P | **Multilinguisme et traduction contextuelle** : langues et préférences par conversation, traduction en temps réel facultative, maintien de la personnalité française par défaut, coût/latence mesurés. |
| NEW-26 | P2 / P | **Télémétrie de jeux structurée** : fournisseurs d'événements de jeu (scores, manches, victoires, etc.) lorsqu'une API ou source locale autorisée existe ; corréler avec le visuel sans supposer l'existence d'une API universelle. |
| NEW-27 | P2 / P | **Gestion de l'attention multimodale** : arbitrer entre événements vocaux, textuels, visuels et API en temps réel selon importance, coût, latence, consentement et priorité des conversations directes. Complète le TurnArbiter textuel existant et PER-09. |
| NEW-28 | P2 / P | **Gestuelle contextuelle non émotionnelle** : gestes de présentation, désignation d'éléments, orientation du regard, posture et synchronisation ; extension distincte des 14 motions associées aux intentions. |
| NEW-29 | P2 / P | **Sous-titrage en direct accessible** : sous-titres synchronisés et configurables sur les supports compatibles au-delà des sous-titres OBS locaux existants, avec contrôle de l'audience, du délai et des données privées. |
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

**Contrôle de cohérence attendu : 36 IDs distincts (NEW-01 à NEW-36), exactement 5 en P1 (NEW-04, NEW-10, NEW-18, NEW-24, NEW-36), exactement 29 en P2, exactement 2 en P3 (NEW-34 et NEW-35), aucun P0.**
