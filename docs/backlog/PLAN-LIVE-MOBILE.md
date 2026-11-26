# GPT-Live mobile — plan d'architecture et feuille de route

**Cadrage du 26 novembre 2026**, demandé par Goldaj. Code audité : `develop`, `990dfbe043f16619359d86405f5c128b435d0bb8`. Ce document décrit le **travail à réaliser**, pas une fonctionnalité déjà disponible. Les statuts et critères de chaque US restent canoniques dans [la vue DEV](01-DEVELOPPEMENT.md) ; ce plan n'ajoute aucun suivi concurrent. La présente livraison est documentaire, sans activation du micro, création de voix ni appel API facturé.

**Accord propriétaire du 26/11 après revue :** Goldaj valide le reste du cadrage, avec ajustements possibles des US au fil du développement, et demande **Aube comme voix de prototype souhaitée** en attendant la voix originale. La disponibilité d'Aube dans l'API reste à confirmer selon la section 3.4 ; cet accord produit ne clôt aucune US de développement.

## 1. Résultat produit à construire

Depuis **Profil**, Goldaj pourra activer ou désactiver **Mode Live**. Activé, ce choix sélectionne le moteur vocal du mobile ; il ne déclenche ni microphone ni session OpenAI. Le micro reste une action distincte : un toucher pour parler librement, un second pour le couper. Le mode classique conserve son appui maintenu. Le choix du moteur survit à une réouverture ; l'autorisation de capturer et une session distante n'y survivent jamais.

La V1 vise la **PWA Android privée existante, en priorité le Redmi Note 13**. Discord continue sur sa chaîne actuelle. Un paramètre serveur réservé et une interface par canal préparent son futur branchement ; le paramètre ne prétend pas livrer un adaptateur Discord absent. VPS (`DEV-043`), APK (`DEV-044`), sous-titres synchronisés (`DEV-037`) et registre général des capacités (`DEV-038`) ne sont pas des prérequis du Live mobile.

Les décisions du 25/11 sont conservées : deux modes disponibles, conversation sans mot d'activation, voix originale à concevoir, mémoire et outils de Jade partagés, aucune session vocale payante maintenue en arrière-plan, arrêt lors du kill. Le cadrage du 26/11 précise le **Profil comme emplacement de la bascule**, le verrouillage initial de Discord et le découpage du chantier.

## 2. Existant vérifié et réutilisation

| Source dans le code audité | Constat et conséquence |
| --- | --- |
| `mobile_web/app.js`, `duplex-client.js`, `mobile_duplex.py` | Le vrai PTT émet du PCM pendant l'appui puis utilise STT → dialogue → TTS. `DEV-039` est déjà transférée dans **REC-042**. Conserver ce parcours et ses tests ; ne pas refaire ce développement. |
| `realtime_tts.py`, `openai_services.py` | Le TTS utilise `client.realtime.connect`, avec pool, contrôle du texte et sortie PCM/WAV. Il ne constitue pas une session GPT-Live conversationnelle. Conserver les transports et modèles classiques. |
| `Runtime._execute`, `Dialogue.respond`, `MemoryService` | Préparation de contexte, outils, historique et mémoire sont aujourd'hui liés à un tour classique. Extraire une façade réutilisable avant de brancher les délégations Live. |
| `Runtime._process`, `TurnArbiter` | Le worker traite les demandes classiques séquentiellement. Le dialogue vocal natif Live nécessite la décision explicite de concurrence décrite plus bas. |
| `mobile_gateway.py` | Serveur privé, identité propriétaire et Bearer, contrôle d'origine, routes et tailles bornées ; CSP `connect-src 'self'`. Ajouter des routes précises et une limite SDP dédiée. |
| `app.js` et tests du gateway | Le jeton n'est pas stocké dans cookies, localStorage ou sessionStorage. Préférence Live enregistrée côté serveur, sans changer ce contrat d'authentification. |
| `CostGuard`, `BillingCosts` | Réservations limitées aux initiatives/analyses sociales ; affichage des coûts agrégés organisation avec délai. Aucun de ces composants n'est déjà un compteur continu ni un coupe-circuit Live. |
| `cancelConversation`, `newChat`, `stopForModelChange` | L'annulation, le nouveau fil et la bascule de modèle doivent être reliés à la fermeture Live. Une annulation locale ne prouve pas l'arrêt du fournisseur. |
| `JadeAvatar`, gestes r21, `sw.js`, rappels | Réutiliser les commandes de bouche/intention et préserver les gestes. Les notifications restent indépendantes de la connexion vocale. |

Les réserves des REC déjà acceptées ne sont pas rouvertes artificiellement. **REC-042** fournit la recette du classique et la non-régression de la bascule, sans bloquer le démarrage du socle Live.

## 3. Décisions d'architecture

### 3.1 API et transport

**Cible : `gpt-live-1.1`, API Live, WebRTC entre mobile et OpenAI, signalisation par le serveur Jade.** Le serveur échange l'offre SDP, impose la configuration, garde les secrets et ouvre un **sideband** de contrôle. Le client ne choisit ni modèle facturé, ni identité, ni canal, ni budget. Aucune clé OpenAI durable ou autorisation de création libre ne lui est remise. [S1, S2, S3]

Le mode de délégation est **`client`** : Jade conserve son workflow et ses modèles configurés. Les demandes nécessitant réflexion, souvenirs explicites ou outils reviennent au backend existant. Il n'y a pas de seconde chaîne STT/LLM/TTS systématique derrière chaque phrase Live. [S4]

**Signalisation même origine** : le mobile appelle Jade sur Tailscale, Jade appelle OpenAI ; conserver la CSP actuelle lorsque cette topologie le permet. Vérifier les flux WebRTC/ICE/TURN réellement requis sur Wi-Fi et réseau mobile. Si une permission réseau navigateur supplémentaire s'avère indispensable, autoriser les seules destinations documentées, jamais un joker. Aucun Funnel public, nouvel accès LAN ou hôte Hyperliquid.

### 3.2 Une Jade commune, concurrence explicitement différente

Le fournisseur Live écoute et parle de manière autonome ; il ne propose pas le même pilotage vocal manuel par tour que le TTS Realtime actuel. **Ne pas inventer un `response.create` vocal ou un `response.cancel` Live.** Une pause de lecture locale n'est pas une pause d'inférence. [S3, S4, S9]

**Choix de conception retenu pour ce chantier :** conserver un seul profil/personnage, un seul système mémoire et un seul registre d'actions ; laisser le moteur Live gérer les échanges oraux simples. Le worker et `TurnArbiter` continuent d'arbitrer les demandes classiques et les **délégations backend Live**, sans priorité fixe mobile ni réservation pendant toute la session. Les opérations qui modifient un état commun restent sérialisées et idempotentes.

Cela signifie que la parole native mobile peut coexister avec un échange sur un autre canal. **Ce n'est pas la sérialité absolue de toutes les générations vocales.** Cette évolution est un contrat d'implémentation à documenter dans les guides lorsque le code sera livré ; elle n'est pas prétendue présente dans le runtime actuel. Une fermeture/réouverture à chaque tour global dégraderait la fluidité et multiplierait les créations facturables. Aucun second personnage, profil mémoire ou worker métier autonome n'est créé.

Pour le **même dialogue mobile**, une demande écrite explicite arrête le Live puis emprunte le moteur écrit existant. Le même message ne part jamais dans les deux moteurs. Les autres canaux restent actifs, avec leurs destinations propres. Une réponse privée mobile ne pilote ni audio public, ni sous-titres OBS, ni avatar public.

### 3.3 Identité, contexte et outils

- Conserver `Incoming.platform = "mobile"`, l'identité vérifiée, `history_key`, `thread_id` et les protections de destination. Le mode/provider est une métadonnée, pas une nouvelle identité `mobile_live`.
- Partager la préparation et la conclusion du contexte avec le runtime. Borner le contexte injecté, en conservant l’historique durable et sa rétention actuelle ; réutiliser souvenirs sélectionnés, personnalité durable et prompt approuvé. À la création, vérifier séparément les limites fournisseur : 128 messages et 8 192 tokens combinés pour `input`, 16 384 tokens pour `instructions` dans la documentation consultée. Ne jamais tronquer la mémoire durable pour faire entrer un prompt. [S5, S11] Réinjecter des textes de contexte utiles à la reprise, sans redemander tout l'historique au modèle ni créer un résumé LLM à chaque reconnect.
- Après journalisation Live, actualiser ou invalider sous verrou et révision commune le cache `Dialogue.history` du même `history_key` : le runtime ne recharge SQLite que si ce cache est absent. Relire la révision courante avant toute reconstruction de contexte. Tester Live → texte classique → Live avec les derniers échanges visibles dans les trois parcours.
- Conserver la lecture/divulgation globale de L1/L2/L3 avec provenance, les droits existants d'écriture/suppression, le L2 imposable uniquement par Goldaj et le L3 choisi par Jade. Ne pas rétablir de cloisonnement mémoriel sous couvert d'isolation des transports.
- Brancher mémoire, Tavily, rappels, documents et actions intercanaux déjà autorisées. Les fonctionnalités non disponibles ne sont pas annoncées comme exécutables. `DEV-038` demeure le chantier plus large du registre et de l'initiative.
- Une délégation doit préparer les outils et droits du contexte réel avant exécution. Ne pas réutiliser sans adaptation `Runtime.submit` si cela produit une deuxième réponse dans le chat, un TTS classique ou une deuxième écriture de l'échange.
- Utiliser des identifiants distincts pour session fournisseur, génération de bail, segment de conversation, délégation et opération métier. Dédupliquer le transport et les effets persistants. Une demande réellement nouvelle et identique de l’utilisateur ne doit pas être supprimée par une simple comparaison de texte. Tracer chaque action `started`, `committed` ou `unknown` avec sa clé stable, l’empreinte de ses paramètres et son résultat métier ; réutiliser une même clé avec d’autres paramètres est refusé ; après crash entre effet et acquittement, réconcilier via l’identifiant métier ou garder l’issue indéterminée, sans réexécuter automatiquement l’effet.
- À l'interruption, empêcher les nouvelles actions devenues invalides et les résultats tardifs dans un autre fil. Un rappel ou fichier déjà créé ne disparaît pas à l'arrêt du micro ; son résultat reste traçable. Une tâche en cours encore annulable est annulée selon son contrat ; une action confirmée n'est pas rejouée.
- Préserver le contrat actuel des écritures mémoire différées, y compris la politique verbale choisie par le propriétaire. Le journal technique distingue acceptation en file et écriture effective ; la migration Live n'impose pas une nouvelle attente de confirmation SQLite à la parole de Jade.

### 3.4 Personnalité, voix et intentions

Le contenu de personnalité approuvé reste commun. **Adapter seulement le contrat de sortie du transport** : ne pas envoyer au moteur vocal natif l'obligation textuelle de prononcer un préfixe `[INTENT:...]`. Filtrer après réception du transcript serait trop tard pour l'audio déjà émis.

Le flux distant pilote la bouche sur le **son effectivement lu**. Une intention fournie par une délégation peut déclencher les animations existantes ; en son absence, utiliser le comportement neutre de parole. Pas d'appel LLM ajouté à chaque phrase pour classifier une animation, pas de prétention à une intention structurée que Live n'émet pas. La prosodie Live reste orientée par les instructions vocales. Le sous-titrage synchronisé complet reste `DEV-037`.

`DEV-041` conserve la création d'une voix par description, féminine de jeune adulte, française, vive et espiègle. **Aube est la préférence de prototype de Goldaj**, en attendant la voix originale. Aube est bien documentée dans ChatGPT ; au 26/11, le catalogue API Live et la référence de création consultés listent `brise`, mais pas `aube`, et aucune correspondance officielle Aube → Brise n'a été trouvée. La disponibilité d'Aube pour Jade n'est donc pas confirmée. [S5, S11, S12]

Dans DEV-046, vérifier la disponibilité API et l'identifiant exact avant le premier essai vocal : retenir Aube si son accès est confirmé, sans inventer d'alias. À défaut, **Brise (`brise`) reste le recours technique documenté pour les essais**, annoncé comme tel et jamais présenté comme Aube ; cela ne change pas la préférence du propriétaire. Le choix reste configurable sans refonte. Un changement de voix nécessite une nouvelle session. Les voix issues d'un prompt sont compatibles Live, leur création et leur consommation ont des règles de coût différentes. [S5, S6]

## 4. Parcours et machine d'états

Trois axes d’interface séparés : **préférence** (`classic` / `live`), **capture locale** (`closed` / `armed`), **session distante** (`absent`, `opening`, `active`, `standby`, `closing`, `close_unconfirmed`). L'UI dérive ses libellés de ces états, jamais d'un seul booléen.

| Action ou événement | Comportement à construire |
| --- | --- |
| Profil : Live ON | Persister la préférence propriétaire ; aucune capture, permission micro ou création fournisseur. Si classique en cours, l'annuler proprement avant de changer de propriétaire audio. |
| Profil : Live OFF | Révoquer côté serveur l’armement et fermer toute session Live de ce propriétaire, même sur un autre client ; notifier une nouvelle révision de préférence. Capture/lecture arrêtées ; classique sélectionné, aucun replay. |
| Micro Live, premier toucher | Vérifier son disponible, foreground, authentification, disponibilité et budget ; obtenir le bail exclusif d’armement **avant getUserMedia**, puis ouvrir la détection locale. Première parole : création distante et réinjection du début capturé. Aucun appel LLM pour surveiller le silence. |
| Micro Live, second toucher | Fermer toutes les pistes et la détection locale, vider le pré-roll ; aucune réouverture sur bruit. Une réponse déjà demandée peut finir seulement si la page reste visible, jusqu'à une borne de 15 s initiale, puis clôture. Après audio utilisateur envoyé, une réponse peut encore être attendue même sans son/transcript : appliquer la borne si son achèvement est incertain ; clôture immédiate seulement lorsque aucune réponse ni tâche n’est attendue. |
| Parole pendant la réponse | Barge-in natif ; réception des nouveaux mots et arrêt de l'ancien son observable. Une courte pause du transcript ne devient pas artificiellement un tour terminé. |
| Pause courte | Standby fournisseur si configuré ; état encore facturable. Heartbeat de contrôle distinct de l'activité de conversation. |
| Pause longue | Fermer uniquement la session fournisseur et sa génération ; conserver le bail d’armement, la VAD locale et le tampon en RAM tant que le client reste visible et vivant. Reprise à la parole, sans mot d'activation. |
| Message écrit / Nouveau fil | Stopper Live avant traitement écrit ou changement du fil. Le texte écrit garde le parcours existant. Un terminal fournisseur manquant reste signalé, sans rejouer le tour oral. |
| Bouton « Voix coupée » | En Live, ferme aussi capture et session ; préférence Live conservée, affichée suspendue. Réactiver le son ne réarme pas le micro. Le classique conserve sa sémantique existante. |
| Accueil ↔ Chat ↔ Profil, plein écran | Même session et même contrôle micro ; navigation interne n'est pas un background Android. Les labels accessibles indiquent maintien classique ou toucher Live. |
| Décor, zoom, secousse, coiffure | Aucun effet sur la session ni le micro du seul fait d'un changement visuel. Le micro reste accessible en plein écran. |
| Changement r20/r21 | Respecter l'annulation audio existante : arrêter le Live et libérer ses ressources ; ne pas le rouvrir après chargement. |
| Background, verrouillage, perte d'auth, appel/interruptions audio système | Arrêt immédiat local et clôture serveur, sans laisser finir une réponse. Le retour demande un nouveau geste micro. |
| Kill/crash ou disparition réseau | Le serveur invalide le bail et ferme la session même sans callback client. Reconnexion et notification ne réarment rien. |
| Perte du backend/sideband pendant média encore actif | Le mobile ferme également capture, audio et PeerConnection ; le backend tente la clôture de son côté. |
| Quota, budget, modèle/voix indisponible | Incident déterministe, aucune boucle de retry ni bascule audio cachée ; texte disponible et retour classique explicite, sans rejouer une demande ambiguë. |
| Second client pour Goldaj | Refuser le deuxième armement **avant capture**, même si le premier client est en silence sans session fournisseur. Une reprise explicite ferme d'abord la première et attend sa confirmation ; aucune capture silencieuse sur deux appareils. |

La préférence est stockée **côté serveur par identité propriétaire**, chargée après authentification. Elle est commune aux clients du même propriétaire, mais ne leur accorde pas le droit de capter. Aucun token persistant nouveau dans le navigateur. Un seul bail d’armement et une seule session Live distante au maximum par propriétaire pour la V1. La révision de préférence est monotone : OFF depuis un second client révoque l’armement du premier ; ON et les notifications d’état ne réarment aucun client. Un ancien acquittement ON ne peut pas annuler un OFF plus récent. Le droit propriétaire d’arrêter globalement ne donne pas au second client le droit de lire ou de reprendre le handle, les médias et le fil de l’autre instance ; une reprise nécessite son propre geste et l’acquisition d’un nouveau bail.

## 5. Capture froide, qualité audio et limites

Le PTT courant transporte du PCM vers Jade. **Son buffer ne peut pas être envoyé tel quel sur le sideband Live WebRTC.** La voie candidate pour le Live est une capture locale traitée par navigateur, un `AudioWorklet`, un buffer circulaire borné et une piste Web Audio réinjectant les trames en ordre avant le direct. Cette piste doit être la seule entrée WebRTC ; pas de double envoi direct + buffer. [S2, S9, S10]

Valeurs initiales d'ingénierie : pré-roll de **500 ms**, tampon total de connexion de **8 s**, timeout d'ouverture de **8 s**. La capacité totale de 8 s inclut les 500 ms de pré-roll ; l’échec survient au premier seuil atteint (capacité ou timeout), sans promettre 8 s pleines de handshake. Les nouvelles trames ne doivent pas écraser le début de l’énoncé en attente. Si la connexion ou le buffer dépasse la borne, abandonner et demander explicitement de recommencer ; aucun mot perdu masqué, aucun replay automatique vers le classique. Effacer les données au mute/stop/fermeture et ne pas stocker l'audio brut.

Avec `wake_policy=speech`, la piste doit émettre la parole qui provoquera le premier `session.resumed` ; ne pas attendre ce signal pour autoriser toute entrée audio, sous peine d’attente circulaire. Les commandes applicatives attendent `session.started`, les pistes suivent leur négociation. [S2, S5]

**Porte de validation de DEV-047 :** démontrer sur Redmi la réinjection de première syllabe, l'ordre, l'absence de doublon et un retard qui ne s'accumule pas au fil de la conversation. La latence inclut le tampon, le handshake et sa vidange. Le passage au direct peut rattraper une pause détectée ; ne pas accélérer arbitrairement la voix. Si ce chemin échoue, le réveil vocal automatique reste non livré : le prototype peut proposer « connecter puis parler », mais ce repli ne satisfait pas à lui seul l'acceptation finale.

Demander suppression d'écho, réduction de bruit et gain automatique, puis les **observer** sur haut-parleur/écouteurs/Bluetooth. Le son de Jade ne doit pas réveiller une nouvelle session. Ne pas raccorder simultanément deux destinations audibles au flux distant. AudioContext suspendu, piste terminée, permission tardive et changement de périphérique passent par le même contrôleur d'arrêt. Une intention ou une animation ne retarde pas le premier son utile.

## 6. Contrats techniques à implémenter

### 6.1 Configuration proposée

Ces paramètres sont **à coder**, ils n'existent pas encore dans la configuration livrée. Ne pas détourner `--live`, qui signifie déjà l'exécution réelle de Jade.

| Paramètre / réglage | Valeur initiale proposée | Règle |
| --- | --- | --- |
| `JADE_LIVE_ENABLED` | `false` | Verrou serveur global de déploiement ; doit pouvoir couper toutes les sessions Live. |
| `JADE_MOBILE_LIVE_ENABLED` | `true` | Autorise seulement le canal mobile lorsque le verrou global est ouvert et les contrôles passent. |
| `JADE_DISCORD_LIVE_ENABLED` | `false` | Réservé au futur adaptateur ; actuellement `true` doit produire « adaptateur non disponible » au préflight, jamais activer un autre chemin. |
| `JADE_LIVE_MODEL` | `gpt-live-1.1` | Indépendant de `JADE_TTS_MODEL` et des modèles backend. |
| `JADE_LIVE_VOICE` | Identifiant API validé ; `brise` comme recours technique documenté | Aube est prioritaire si son accès API est confirmé ; aucun identifiant `aube` ni équivalence avec Brise supposés. Remplacer ensuite par la voix originale validée dans DEV-041. |
| Préférence `voice_mode` | `classic` | Persistante côté serveur ; la capture ne l'est jamais. |
| `JADE_LIVE_HEARTBEAT_SECONDS` / `JADE_LIVE_LEASE_SECONDS` | `2` / `5` | Temps monotone serveur ; contraintes de validation et tests de races. |
| `JADE_LIVE_IDLE_STANDBY_SECONDS` / `JADE_LIVE_IDLE_CLOSE_SECONDS` | `8` / `30` | Cibles à comparer ; l'activité audio/lecture/tâches conditionne la fermeture d'inactivité. |
| `JADE_LIVE_CLOSE_TIMEOUT_SECONDS` | `5` | Borne d'attente nominale du terminal ; dépassement = fermeture non confirmée, pas succès. |
| `JADE_LIVE_MUTED_DRAIN_SECONDS` | `15` | Maximum de fin d'une réponse déjà demandée après mute volontaire visible. |
| `JADE_LIVE_MAX_SESSION_SECONDS` | `600` | Borne locale dure d'une connexion ; arrêt puis geste requis, pas reconnexion automatique. Aucun équivalent fournisseur court présumé. |
| `JADE_LIVE_MAX_STARTS_PER_MINUTE` | `3` | Anti-boucle/faux réveils ; au dépassement suspendre et demander un geste, sans contourner le budget. |
| `JADE_LIVE_DAILY_USD` / `JADE_LIVE_MONTHLY_USD` | `0` / `0` | **0 interdit les dépenses Live**, jamais « illimité ». Des montants privés explicites sont requis pour le pilote réel. |

Les seuils ci-dessus sont des **valeurs de départ modifiables et mesurables**, pas des résultats de performance. Les budgets réels ne sont pas décidés par ce document. L'interface affiche une indisponibilité compréhensible si leur configuration manque ; aucun budget positif implicite.

### 6.2 Routes et objets internes

Prévoir dans le gateway existant : `GET /api/live/capabilities`, `GET/POST /api/voice/preferences`, `POST /api/live/arm`, `POST /api/live/sessions`, un canal authentifié `/api/live/control`, `POST /api/live/sessions/close`. Le nom final peut suivre les conventions locales ; le contrat fonctionnel reste celui-ci :

- Toutes les opérations vérifient Tailscale/propriétaire, Bearer, origine et état serveur. Le contrôle WebSocket utilise le mécanisme d'authentification existant, sans secret dans l'URL ; taille, fréquence, débit et nombre de connexions bornés.
- `/api/live/arm` acquiert atomiquement le bail exclusif, sans session OpenAI ; il doit réussir avant ouverture du micro. Refus d’auth/disponibilité/budget : pas de capture. Le bail est libéré si la permission échoue.
- Les verrous de fonctionnalité, quota et budget contrôlent **l’ouverture**, jamais la possibilité de fermer une session. Les routes exposées gardent leur authentification ; le superviseur serveur reste habilité à clôturer après révocation, bail expiré ou flag OFF, sans dépendre d’un client encore connecté.
- Limiter explicitement le data channel OpenAI : `session.client.data_channel.allowed_client_events=[]`, commandes via Jade/sideband ; `allowed_server_events` limité aux signaux d’état nécessaires au navigateur (dont démarrage/terminal/erreur). Le chat et les résultats métier sont projetés par Jade. Ne pas laisser la valeur fournisseur allow-all par omission. [S11]
- La création contient offre SDP, identifiant d'instance cliente et nonce de demande ; le canal mobile et l'identité sont dérivés du serveur. Limite d'offre dédiée, **64 Kio initialement**, sans relever la limite de tous les POST.
- Réserver budget et place de session avant l'appel externe ; création avec retry automatique désactivé. Le `request_id` local déduplique les demandes concurrentes, sans supposer une idempotence HTTP fournisseur non documentée.
- Retourner SDP et handle applicatif, pas de secret durable ni de contexte métier arbitrairement choisi par le client. Enregistrer l'ID fournisseur dès sa réception, même si le mobile a déjà annulé.
- Le contrôle transporte bail, état, incidents, événements d'affichage et observations de lecture. Un message client ne constitue pas une autorité sur les droits, coûts ou résultats métier ; les événements fournisseurs sont observés côté serveur.
- Interfacer `LiveSessionManager`, `LiveProvider`, `LiveConversationBridge`, `LiveBudgetLedger` et le contrôleur mobile. Noms proposés : rôles séparés, pas six nouveaux services à déployer.

### 6.3 Événements fournisseur à ne pas confondre

| Contrat documenté | Traitement Jade à prévoir |
| --- | --- |
| Création HTTP WebRTC puis `session.started` | Attendre le signal disponible, sans envoyer `session.start` sur data channel/sideband. |
| `session.input_transcript.delta`, `session.output_transcript.delta` | Garder texte et intervalles ; construire des segments locaux sans inventer de fin de tour fournisseur. |
| `session.delegation.created` | Utiliser ID, `offset_ms`, historique et état ; l'événement ne contient pas lui-même la demande textuelle. Attendre de façon bornée le contexte manquant, jamais déléguer le tour précédent. |
| `session.thinking.append` / `session.commentary.append` | Retour discret de contexte / résultat vocal de délégation, avec ID valide ; limiter chaque append selon le contrat courant. |
| Rejeu sideband des 3 dernières secondes | Déduplication `event_id` avant effet ; les trous plus anciens restent des trous, pas un historique supposé complet. |
| `session.paused` / `session.resumed` | Réconcilier état d'inférence et estimation de coût avec l'activité observée. |
| `session.usage.updated` | Valeur cumulée : 12 → 15 → 15 donne 15, pas 42. |
| `session.close` puis `session.closed` | Seul terminal fournisseur vérifié pour cette voie ; conserver réception sideband le temps de finaliser. |

Références des schémas : [S3, S4, S5, S9]. Ne pas réutiliser les événements Realtime de `realtime_tts.py` ni supposer qu'un endpoint de raccrochage décrit pour SIP contrôle WebRTC.

## 7. Fermeture, facturation et panne

### Contrat d'arrêt

**Deux niveaux de durée de vie :** le bail d’armement client est obtenu avant la capture, associé à l’instance visible et conservé pendant la veille locale ; la génération de session fournisseur est créée seulement à la parole. Une fermeture d’inactivité invalide uniquement cette seconde génération. Un arrêt fort révoque les deux. Le mute retire immédiatement le droit de capturer et passe le bail client en état `draining` si une réponse doit finir ou reste attendue : heartbeat de présence toujours requis, échéance fixe de 15 s non prolongeable, puis libération. Il n’autorise aucun réveil. Le watchdog couvre `armed` et `draining` ; le service worker ne renouvelle aucun bail.

**Le kill ne doit laisser aucun Live payé durablement par l'application.** Le client arrête immédiatement capture et lecture lorsqu'il observe la disparition de la page. Le serveur surveille indépendamment le bail client, invalide armement et génération fournisseur avant toute suite lors d’un arrêt fort, annule les tâches Live encore annulables et ferme le fournisseur. Le heartbeat ne crée pas une session et ne réinitialise pas l'inactivité de conversation.

Installer le récepteur de terminal avant la demande de fermeture. Conserver le sideband pour finaliser, même si les appareils audio locaux sont déjà libérés. À réception de `session.closed`, enregistrer le résultat et l'usage final ; sinon conserver **`close_unconfirmed`**, faire des tentatives de clôture bornées et bloquer la création d'une autre session Live pour l'identité. Ne pas déclarer l'arrêt facturable à partir du seul socket client fermé. [S3, S5]

L'objectif de détection est **au plus 5 s après le dernier heartbeat valide**, puis une attente nominale de terminal de **5 s** sous réseau fonctionnel. Mesurer les deux délais. Ce n'est pas une promesse de facture figée exactement au moment du kill : unités déjà engagées, latence réseau et finalisation peuvent laisser un résidu. Une panne simultanée du mobile, du serveur et du chemin vers OpenAI ne permet pas une garantie d'arrêt immédiat par Jade.

### Races et reprise

Le bail client et les générations fournisseur sont rattachés à l’identité, à l’instance cliente et au fil ; une session fournisseur fermée peut être remplacée seulement sous un bail client toujours armé, visible et valide. Un heartbeat ancien ne ressuscite rien. OFF/kill pendant création place la demande en abandon ; une réponse de création tardive est fermée côté serveur, sans être transmise comme une nouvelle session prête.

Le watchdog est une tâche indépendante du worker de dialogue, avec I/O non bloquantes, deadlines et mesure de dérive de boucle. Il ne dépend pas d'un callback `beforeunload`, d'une animation ou du service worker. Le téléphone surveille aussi le canal Jade : sa perte coupe le média direct. L'arrêt normal de Jade ferme toutes les sessions avant de terminer ; un redémarrage réconcilie le petit registre privé des sessions non confirmées, sans les reprendre.

Si la création HTTP devient ambiguë avant obtention d'un ID fournisseur, garder une réservation et l'état `opening_unknown` ; aucune nouvelle création automatique. Utiliser seulement une récupération documentée si disponible, sinon diagnostic et rapprochement d'usage. Ne pas affirmer qu'une session sans identifiant a été raccrochée. Tester ce cas au même titre qu'une fermeture sans terminal.

### Coûts et limites

Au 26/11/2026, les tarifs consultés sont **0,05 USD/min active** et **0,02 USD/min standby WebRTC**, facturés à la seconde ; modèles et outils backend sont séparés. Le silence avant mise en veille et l'attente d'un outil peuvent rester actifs. Une piste muette ne ferme pas l'inférence. [S1, S7, S8]

La documentation décrit, **avec le démarrage WebRTC par défaut**, 15 secondes facturées à l'initialisation puis créditées sur la durée réelle. Ne pas les ajouter une seconde fois à une session active ; ne pas présumer les créations avortées gratuites. Qualifier ce comportement avec la configuration `wake_policy.type=speech` choisie. La réservation initiale couvre conservativement cette exposition tant que sa mesure ne la précise pas. [S7]

Le ledger Live calcule l’exposition comme **consommation déjà comptabilisée + reste réservé non consommé**. Un usage confirmé remplace l’estimation et réduit sa réservation, sans compter deux fois les mêmes unités. Les appels backend distincts s’ajoutent à la voix. Exemple : réserve 0,05 USD, consommation finale 0,03 USD et libération 0,02 USD donnent 0,03 USD consommé, pas 0,08 USD. Il persiste après redémarrage, utilise des montants décimaux, déduplique les snapshots et expose la différence **estimé / confirmé fournisseur / agrégat facturé**. Le rapprochement `BillingCosts` reste informatif et n'exige pas de nouvelle clé admin pour fonctionner.

Vérifier les plafonds avant création, avant délégation et pendant la session. Garder une marge de fermeture ; à l'atteinte de la borne arrêter capture/lecture et clôturer, pas seulement muter. Réserver les coûts maximums de délégation selon les limites des modèles/outils configurés ; lorsqu'un coût ne peut pas être borné, bloquer cette délégation ou la soumettre au budget explicite concerné. Ne pas annoncer de plafond exact garanti face à une panne fournisseur.

Les journées/mois de budget sont en **Europe/Paris**, avec tests de minuit, changement de mois et heure d'hiver/été ; l'agrégat fournisseur UTC reste identifié comme tel. Aucun appel IA pour rafraîchir la jauge, aucun crédit promotionnel présumé durable ni réduction supposée sur le coût brut.

## 8. Fichiers et responsabilités prévues

| Zone | Fichiers existants à examiner/modifier lors du code | Livrable attendu |
| --- | --- | --- |
| Configuration et assemblage | `config.py`, `main.py`, `.env.example`, `pyproject.toml`/lock si nécessaire, `diagnostics.py` | Flags canal, paramètres validés, préflight sans dépense, dépendance SDK Live réelle et arrêt propre. |
| Fournisseur et sessions | `openai_client.py`, `openai_services.py`, nouveaux `live_provider.py`, `live_sessions.py` | Adaptateur distinct, sideband, schémas d'événements, baux, registre privé et clôture. |
| Gateway | `mobile_gateway.py` | Préférences/capacités, SDP, contrôle, origine/auth, limites ciblées, whitelist de nouveaux assets. |
| PWA | `salon.html`, `jade-theme.css`, `app.js`, nouveaux `live-client.js`, `live-audio-worklet.js` | Contrôle Profil, états, propriétaire audio commun, VAD/pré-roll, fermeture, accessibilité. |
| Conversation commune | `orchestrator.py`, `dialogue.py`, `messages.py`, `responses_chat.py`, nouveau `live_bridge.py` | Façade de contexte/conclusion, délégations sans TTS redondant, annulation et arbitrage. |
| Mémoire et outils | `memory_service.py`, `memory_store.py`, `memory_actions.py`, `cross_channel.py`, `web_search.py`, `documents.py`, `reminders.py` | Réutilisation des services, journal et idempotence, résultats tardifs cohérents ; migrations seulement si nécessaires, sur copie. |
| Chat et avatar | `app.js`, `avatar.js`, `turn_logging.py`, `turn_metrics.py` | Transcriptions progressives, états interrompu/inconnu, vraie lecture, lip-sync privé et événements préparant DEV-037. |
| Coûts | `cost_guard.py`, nouveau `live_budget.py`, intégration `billing.py` | Réservations Live persistantes, coût séparé, coupe-circuit serveur et mesures. |
| Régression | tests gateway/stream/duplex/plein écran/avatar/rappels + nouveaux tests Live | Doubles fournisseur, horloge contrôlée, courses et scénarios discriminants ; recette Redmi distincte. |

Les noms de modules nouveaux sont des recommandations d'implantation, pas des fichiers déjà livrés. Ne pas transformer `mobile_gateway.py` ou `app.js` en gestionnaire monolithique de toute la logique Live. Le SDK actuel est épinglé à `openai 3.42.1` : vérifier son support réel des ressources Live avant toute mise à jour ciblée, sans migration globale gratuite du client OpenAI.

## 9. Feuille de route et dépendances

| Étape | Cartes | Résultat concret avant la suite |
| --- | --- | --- |
| 1 — Socle contractuel | **DEV-046** | Schémas/SDK vérifiés, configuration par canal, faux fournisseur, création/sideband/terminal modélisés ; registre et contrats d'erreur disponibles. |
| 2 — Contrôle avant exposition | **DEV-048 + DEV-051** | Baux, stop, fermeture incertaine, reprise serveur, budgets persistants et aucune création sans admission. Travaux parallèles possibles sur interfaces convenues. |
| 3 — Conversation et audio | **DEV-049 + DEV-047** | Pont mémoire/outils/arbitrage et capture WebRTC/pré-roll. Prototypes sur doubles possibles dès étape 1 ; activation réelle seulement après étape 2. |
| 4 — Restitution et interface | **DEV-050 + DEV-040** | Chat, bouche, annulations, Profil ON/OFF et bascule classique/Live intégrés. Maquette logique du Profil possible plus tôt, fonctionnalité réelle verrouillée jusqu'aux dépendances. |
| Voix en parallèle | **DEV-041** | Prompt préparé dès le début ; échantillons et choix lorsque le chemin audio est sûr. Aube est souhaitée pour le prototype si accessible par API ; sinon Brise permet les essais techniques explicites. La voix originale reste à sélectionner. |
| 5 — Pilote et livraison | Critères des huit US, **REC-042** pour le classique | Preuves hors ligne puis Redmi/fournisseur ; passage DEV → REC de chaque fonction livrée encore à accepter, sans doublon actif. |

**Dépendances et acceptation :** une dépendance doit fournir une interface utilisable et les mécanismes testés nécessaires à l’intégration, sans exiger prématurément son statut Done. Par exemple, DEV-051 fournit son ledger et ses tests hors ligne à DEV-047 ; son benchmark final dépend ensuite du client et de la restitution intégrés. Ce retour de validation ne crée ni cycle d’exécution ni faux Done. Les cartes demeurent ouvertes jusqu’à leurs preuves finales.

Ordre conseillé des commits : contrats/configuration → supervision et ledger → pont/backend et client audio → restitution → parcours Profil complet → voix retenue. Garder au plus trois travaux réellement en cours, chaque lot avec vérifications pertinentes et documents de comportement mis à jour. Aucun calendrier fictif ni estimation de jours sans connaissance du poste.

Les premières preuves à collecter sont les risques qui peuvent invalider le choix technique : **terminal de fermeture via sideband**, **pré-roll WebRTC sur Redmi**, **contexte de délégation complet malgré les événements asynchrones**, **comptage des créations et de l'usage**. Un échec ouvre le correctif de la carte concernée ; il ne vaut pas acceptation du mode dégradé.

## 10. Matrice de recette transverse

Les preuves ci-dessous sont **à produire**, pas exécutées pendant ce cadrage. Une recette simulée ne valide ni l'acoustique ni la facturation réelle. Les appels payants et les budgets du pilote seront traités au lancement effectif, sans demander de clé pour écrire cette backlog.

| Scénario | Preuve attendue | US porteuse |
| --- | --- | --- |
| Profil ON/OFF, lancement avec Live mémorisé | Zéro micro et zéro création sans geste micro ; états et labels cohérents | DEV-040 |
| Classique déjà livré | Trames avant relâchement, un seul tour, plafond classique conservé, aucun fournisseur Live | REC-042, DEV-040 |
| Premier mot, silence 5/30 s puis plusieurs minutes | Début intact, aucune duplication, reprise mesurée ; zéro consommation Live pendant période effectivement déconnectée | DEV-047 |
| 30–60 min sans interlocuteur, bruits/écho | Pas de boucle distante ; faux réveils et coût bornés, micro local correctement signalé | DEV-047, DEV-051 |
| Interruption, parole simultanée, mute pendant réponse | Capture stoppée au mute, fin bornée, transcript interrompu, pas de double son | DEV-047, DEV-050 |
| Kill pendant opening/active/standby/outil | Fermeture observée côté fournisseur sans callback client, délais et coût résiduel ; aucune réouverture | DEV-048 |
| Background, lock, permission refusée/révoquée/tardive | Tracks/timers/lecture libérés ; aucun réarmement au retour | DEV-047, DEV-048 |
| Réseau média perdu avec contrôle vivant, et inversement | Arrêt cohérent des deux voies ; aucun Live autonome ni reprise ambiguë | DEV-048 |
| Backend tué/redémarré, absence de terminal | Mobile coupe, registre réconcilié, état non confirmé visible, pas de deuxième session | DEV-048 |
| Deux clients en silence puis parole simultanée | Un seul armement avant capture ; les générations fournisseur restent distinctes du bail client | DEV-046, DEV-047, DEV-048 |
| OFF depuis autre client, vieux ON/heartbeat, ouverture tardive | Révocation propriétaire propagée, révision monotone et aucun réarmement | DEV-040, DEV-048 |
| Flag OFF, budget épuisé ou auth révoquée pendant appel | Ces refus d’ouverture ne bloquent jamais la clôture interne et sa réconciliation | DEV-046, DEV-048 |
| Commande interdite depuis data channel frontend | Rejet sans mutation métier ni appel payant supplémentaire | DEV-046 |
| Live → classique → Live et crash après effet métier | Cache et DB cohérents, résultat d’action réconcilié sans répétition | DEV-049 |
| Rejeu sideband / délégation avant dernier fragment | Une seule action et un contexte correct, jamais une demande vide ou précédente | DEV-049, DEV-050 |
| Mémoire L2/L3, recherche, rappel, document | Droits/règles actuels, vraie action et livraison privée ; action accomplie non répétée après reconnect | DEV-049 |
| Texte, nouveau fil, changement r20/r21, notifications | Aucun résultat tardif dans le mauvais fil ; reprise micro explicite ; rappels conservés | DEV-040, DEV-050 |
| Usage 12 → 15 → 15 ; création avortée ; budget concurrent | Total 15, réservation non perdue, dépassement prévenu, pas d'initialisation comptée deux fois | DEV-051 |
| Coût proche du plafond, minuit/mois/redémarrage | Arrêt serveur avant exposition non réservée ; compteurs durables et dates correctes | DEV-051 |
| Même corpus français classique/Live | p50/p95 première réponse utile réellement entendue, latence froide/chaude, coût voix+backend et qualité notés séparément | DEV-051, DEV-041 |
| Wi-Fi/mobile, haut-parleur/écouteurs/Bluetooth | Écho, bruit, appel entrant, latence et coupures observés sur Redmi | DEV-047 |
| 20–30 bascules, avatar actif, plein écran | Une capture/lecture, retour des ressources à leur base, absence de fuite mémoire et CPU/batterie évalués | DEV-040, DEV-050 |
| Mobile Live avec Discord classique sollicité | Délégations équitables, aucune fuite de transport/animation publique, aucun remplacement global de TTS | DEV-049 |
| Discord Live flag ON sans adaptateur | Préflight explicite, aucune création Live Discord ; classique préservé | DEV-046 |

### Critères de sortie du pilote

- Tous les scénarios bloquants d'arrêt, droits, budget, duplication et capture froide sont prouvés. Le kill réel Android est testé pendant écoute, réponse, standby et création.
- L'écoute française confirme le gain de fluidité et l'absence de régression majeure ; les mesures A/B sont publiées sans audio/transcription privés. Une interjection d'attente n'est pas comptée comme première réponse utile.
- La fermeture fournisseur est confirmée, et les essais distinguent consommation après détection et consommation après terminal. Aucune affirmation « zéro coût instantané » invérifiable.
- Régression classique, rappels, mémoire, documents, canaux existants et modèle mobile couverte selon les fonctions touchées. Les recettes PC micro/Twitch/OBS suspendues ne sont pas réactivées par ce lot ; leurs contrôles hors ligne restent possibles.
- Les fonctions livrées sont transférées une fois en REC si l'acceptation reste à faire ; `Done` suit la [DoD](DEFINITION_OF_DONE.md). La voix personnalisée possède son choix utilisateur distinct.

## 11. Sources techniques vérifiées

Sources officielles consultées le **26/11/2026** ; revérifier schémas, tarifs et limites au début de l'implémentation. Les valeurs de configuration et décisions d'architecture de Jade ci-dessus sont nos choix de conception, pas des garanties OpenAI.

- **S1** — [GPT-Live-1.1 : modèle et tarification](https://developers.openai.com/api/docs/models/gpt-live-1.1).
- **S2** — [Connexion WebRTC Live](https://developers.openai.com/api/docs/guides/voice-webrtc).
- **S3** — [Sideband et contrôles serveur](https://developers.openai.com/api/docs/guides/voice-server-controls).
- **S4** — [Délégation et outils Live](https://developers.openai.com/api/docs/guides/live-delegation).
- **S5** — [Sessions, voix, contexte, veille et finalisation](https://developers.openai.com/api/docs/guides/live-conversations).
- **S6** — [Voix personnalisées par description](https://developers.openai.com/api/docs/guides/custom-voices).
- **S7** — [Coût vocal et initialisation WebRTC](https://developers.openai.com/api/docs/guides/voice-latency-cost).
- **S8** — [Tarifs API](https://developers.openai.com/api/docs/pricing).
- **S9** — [Référence Live et événements du WebSocket primaire](https://developers.openai.com/api/reference/resources/live/primary-websocket) ; [raccrochage décrit pour SIP](https://developers.openai.com/api/reference/resources/live/subresources/sessions/methods/hangup).
- **S10** — [Web Audio API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API), [piste de sortie MediaStream](https://developer.mozilla.org/en-US/docs/Web/API/MediaStreamAudioDestinationNode), [cycle de vie mobile Chrome](https://developer.chrome.com/docs/web-platform/page-lifecycle-api).
- **S11** — [Création de session et permissions frontend](https://developers.openai.com/api/reference/resources/live/methods/create).
- **S12** — [Voix de ChatGPT, dont Aube et Rivage](https://help.openai.com/fr-fr/articles/20001274-chatgpt-voice) ; catalogue produit distinct du catalogue API, aucune équivalence supposée.

**Prochaine action de développement : DEV-046**, avec interfaces convenues pour DEV-048/051. Aucune question produit bloquante n'est laissée ouverte pour commencer le code ; disponibilité du compte, budgets privés du pilote, faisabilité acoustique et choix de voix final restent des contrôles d'exécution explicitement assignés.
