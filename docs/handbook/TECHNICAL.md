# Guide technique : architecture, infrastructure et algorithmes de Jade sur develop

## Live mobile — intégration develop du 26 novembre 2026

**Code présent sur `develop`, lot `90ec0c7` intégré le 26/11 à la demande du propriétaire ; base `6dc8d1b` conservée.** [Architecture et états](../architecture/LIVE_MOBILE.md) · [preuves et reprise](../operations/handoffs/2026-11-26-chatgpt-live-mobile-implementation.md) · [REC-044 à REC-050](../backlog/02-RECETTE.md).

Le gateway mobile raccorde `create_mobile_live` au Runtime existant. **Live est sélectionné par défaut, sans plafond financier mobile.** La case **Mode Live** de **Config → Paramètres** conserve le choix (`live` par défaut, `classic` explicite conservé). L’appui sur le micro d’Accueil ou du plein écran arme le bail et fournit le geste requis par le navigateur. Un second appui coupe la capture. La scène indique la veille en bleu et la connexion ou session active en rouge tant que la capture reste ouverte. La signalisation et le contrôle restent sur l’origine privée Jade. L’audio négocié utilise WebRTC vers OpenAI. Les clés du fournisseur restent sur le serveur.

### Configuration privée Live

Les valeurs sont lues par `Settings.live` depuis la configuration privée habituelle. L'ancien argument CLI `--live` conserve son sens de runtime connecté ; il ne sélectionne pas le nouveau moteur vocal.

| Variable | Défaut | Effet |
| --- | --- | --- |
| `JADE_LIVE_ENABLED` | `1` | Live mobile disponible par défaut ; un OFF explicite verrouille le mobile, sans piloter Discord |
| `JADE_MOBILE_LIVE_ENABLED` | `1` | Canal mobile autorisé lorsque les autres conditions sont remplies |
| `DISCORD_ENABLED` dans `src/jade_runtime/discord_config.py` | `True` | Unique interrupteur code de tout Discord et de sa sélection vocale automatique ; anciennes variables privées Discord ignorées |
| `JADE_LIVE_MODEL` | `gpt-live-1.1` | Modèle distinct du dialogue et du TTS classique |
| `JADE_LIVE_VOICE` | `brise` | Voix API explicite ; Aube non confirmée, aucune équivalence supposée |
| `JADE_LIVE_VOICE_ID` | vide | ID autorisé d’une voix personnalisée, prioritaire sur le nom |
| `JADE_LIVE_VOICE_STYLE` | vide | `petillante` joint la consigne vocale choisie aux sessions mobiles et Discord Live et exige un `JADE_LIVE_VOICE_ID` privé |
| `JADE_LIVE_HEARTBEAT_SECONDS` / `JADE_LIVE_LEASE_SECONDS` | `2` / `5` | Cadence de contrôle et expiration du bail |
| `JADE_LIVE_IDLE_STANDBY_SECONDS` / `JADE_LIVE_IDLE_CLOSE_SECONDS` | `8` / `30` | Veille fournisseur puis fermeture idle avec bail conservé |
| `JADE_LIVE_OPENING_TIMEOUT_SECONDS` / `JADE_LIVE_CLOSE_TIMEOUT_SECONDS` | `8` / `5` | Deadlines de création et de demande de clôture |
| `JADE_LIVE_MUTED_DRAIN_SECONDS` | `15` | Fin maximale d'une réponse après mute, non renouvelable |
| `JADE_LIVE_MAX_SESSION_SECONDS` | `600` | Durée maximale avant arrêt nécessitant un geste |
| `JADE_LIVE_MAX_STARTS_PER_MINUTE` | `3` | Protection contre les faux réveils et les boucles de création |
| `JADE_LIVE_MAX_DELEGATIONS_PER_SESSION` | `12` | Borne du nombre de travaux backend, curation comprise |
| `JADE_LIVE_USAGE_DB_PATH` | chemin privé par plateforme | Suivi d'usage passif hors dépôt ; vide conserve le défaut |
| `JADE_LIVE_SESSION_DB_PATH` | voisin de l'usage | Registre de préférence, sessions et fermetures à réconcilier |

Le suivi d'usage réutilise le fichier historique `D:/Jade/private/jade-live-budget.sqlite3` sous Windows si D: existe, sinon `~/.jade/jade-live-budget.sqlite3`, pour conserver les données existantes. L'ancien nom de variable de chemin `JADE_LIVE_BUDGET_DB_PATH` reste accepté pour cette migration uniquement ; il ne configure aucun plafond. Les anciennes variables de montant `JADE_LIVE_DAILY_USD`, `JADE_LIVE_MONTHLY_USD` et `JADE_LIVE_BACKEND_RESERVATION_USD` sont ignorées, y compris à zéro. Le registre `jade-live-sessions.sqlite3` et le journal `jade-live-journal.sqlite3` sont voisins, sauf surcharge explicite du registre. Audio brut, SDP et clés ne sont pas conservés dans ces bases. Le journal de texte est privé, lié au consentement et purgé après 7 jours ; le registre conserve seulement des métadonnées techniques. Ne pas versionner ces fichiers ni les supprimer pour faire disparaître une fermeture inconnue.

Les diagnostics Live sont ajoutés à `--preflight --live --mobile`, sans réseau ni capture, sans exigence de budget. Une panne du suivi d'usage reste informative et n'empêche ni conversation ni outils. Un registre de sessions ou journal métier indisponible désactive le module optionnel sans empêcher le classique de démarrer ; les identifiants de sessions connues et lisibles restent proposés à la fermeture. Une configuration syntaxiquement invalide reste signalée par le validateur habituel. Après mise à jour, redémarrer Jade et recharger la PWA ; un ancien `JADE_LIVE_ENABLED=0` explicitement présent dans la configuration privée doit être retiré ou passé à `1`.

### Routes et cycle de vie

| Méthode/route | Contrat |
| --- | --- |
| `GET /api/live/capabilities` | Disponibilité mobile, raisons, voix, usage passif et diagnostic Discord isolé ; aucune admission |
| `GET/POST /api/voice/preferences` | Mode serveur et révision ; ON ne crée rien, OFF révoque |
| `POST /api/live/arm` | Bail exclusif lié au client et au fil, avant permission micro |
| `GET /api/live/control` | WebSocket `jade-live-v1`, Bearer dans première trame ; uniquement heartbeat/playback |
| `POST /api/live/sessions` | Offre SDP, bail et requête idempotente ; modèle/voix/permissions imposés serveur |
| `POST /api/live/sessions/close` | Arrêt ou mute borné ; reste disponible après retrait de flag |
| `POST /api/metrics` | Métriques classiques, jalons Live et snapshot passif `live_usage` |

Les routes conservent identité Tailscale, origine privée et Bearer. L'enveloppe JSON de signalisation est bornée à 128 Kio et le SDP décodé à 64 Kio ; les petits POST restent à 4 Kio. Le sideband est le seul canal métier fiable ; le data channel fournisseur interdit les commandes de la PWA. Le contrôle n'accepte pas d'audio.

La clôture fournisseur confirme `session.closed`, pas une déconnexion. `opening_unknown` et `close_unconfirmed` restent visibles et bloquent une nouvelle session. Le serveur invalide les travaux avant les attentes, tente les fermetures bornées et reprend la réconciliation au démarrage. Un heartbeat ne prolonge ni le délai de mute ni l'activité conversationnelle. La curation en attente ne démarre qu'à la prochaine session active, avec contrôle du bail et de l'idempotence, sans condition financière.

Les compteurs d'usage mobile restent passifs. La politique Discord distincte ci-dessous agrège les dépenses globales ; aucun seuil quotidien ni plafond mobile. Le script `python scripts/live_voice_preview.py` prépare hors ligne les variantes et le corpus. Voir [REC-052](../backlog/02-RECETTE.md#rec-052--voix-pétillante-avec-lavatar-de-jade-ancienne-dev-041) pour le profil Pétillante et l’essai avec l’avatar.

## Discord Live automatique — 27 novembre 2026

Le propriétaire demande désormais l’implémentation de DEV-052, transférée en [REC-051](../backlog/02-RECETTE.md#rec-051--live-discord-automatique-et-interrupteur-global-ancienne-dev-052). Dans `src/jade_runtime/discord_config.py`, `DISCORD_ENABLED=True` autorise les transports Discord du lancement habituel et le choix vocal automatique. `False` masque Discord écrit et vocal avant le contrôle du token et la création des connecteurs, y compris avec `--all-channels`. Redémarrer Jade après modification de cette constante. **Config → Suivi Discord** règle séparément l’autorisation du moteur vocal Live à chaud, via `/api/discord/live` sur la passerelle privée. Le choix vocal du mobile est indépendant.

`global_spend.py` collecte toutes les lignes OpenAI de l'organisation via la clé existante `JADE_OPENAI_ADMIN_KEY`, sans filtre de projet/produit/canal, ainsi que les crédits consommés du compte Tavily lorsque ce fournisseur est configuré. Le mois est civil en Europe/Paris et les devises sont converties avec le taux ECB daté et mis en cache. Rafraîchissement cible : 300 secondes ; une décision ne bloque pas sur le réseau. Le fichier privé `jade-global-spend.sqlite3`, voisin de `JADE_LIVE_USAGE_DB_PATH`, conserve relevés, provenance, estimations et verrou mensuel. Aucun audio, texte de conversation ou secret n'y est enregistré.

`discord_live_policy.py` sélectionne Live sous **50 EUR** seulement avec une couverture monétaire complète et explicitement à jour ; une collecte estimée utilise **40 EUR**. Les sources standard n'exposant pas de borne certaine de fraîcheur, **40 EUR est le régime normal**. Une donnée essentielle absente/inexploitable ou un relevé trop ancien impose le classique avec un motif. Un dépassement conserve le classique pour le reste du mois, même après redémarrage ou correction baissière. Les usages Live observés avant facturation ne sont pas effacés par une simple lecture réussie ; les quotas inutilisés ne sont jamais comptés comme dépenses. Il s'agit d'un choix de moteur : les autres appels, le mobile et le classique continuent, donc ce seuil n'est pas un plafond garanti de facture.

`discord_live_provider.py` transporte le PCM via la WebSocket primaire Live ; `discord_live.py` raccorde la voix et le pont de conversation/mémoire/outils. Solo : streaming natif après détection locale de parole. Groupe : admission par les règles existantes, puis envoi cadencé du tour admis ; l'étape STT ajoute de la latence. Changement de présence, seuil, déconnexion et arrêt invalident le tour avant fermeture ; un tour ambigu n'est pas rejoué en classique. [Architecture, limites et protocole](../architecture/DISCORD_LIVE.md).

**Références fonctionnelles prioritaires :** [atlas du 16 novembre 2026](../architecture/atlas-fonctionnel-2026-11-16/README.md) (cinq vues compactes) et [contrat exhaustif des parcours](../architecture/atlas-fonctionnel-2026-11-16/CONTRAT_FLUX_COMPLET.md), couvrant règles propres à Twitch/Discord/micro/Android/HTTP, arbitrage, appels IA distincts, parallélisme, mémoire et incidents. Les [deux anciens schémas](../architecture/README.md) sont conservés pour l'infrastructure. L'atlas est basé sur `develop` au SHA `a841628b`, non sur une recette PC en conditions réelles ; le code et les réglages de la branche ont priorité.

## 1. Portée et architecture globale

Jade est un **runtime Python 3.11 asynchrone** à plusieurs transports entrants, une file de travail partagée, un moteur de dialogue configurable, des capacités de mémoire et des sorties adaptées à chaque demande. La branche `develop` est plus avancée que `main`. Les appels OpenAI existent uniquement en mode réel autorisé ; la démo console et la Démo Express restent hors ligne.

~~~text
Discord écrit ─────────────┐
Discord vocal -> STT ──────┤
Twitch IRC ────────────────┤
Micro Windows -> STT ──────┤ -> Incoming -> Runtime/ArbitratingQueue
HTTP local 127.0.0.1:8765 ┤             -> TurnArbiter (LLM seulement si concurrence)
PWA Android via Tailscale  ┘             -> Dialogue + MemoryService
   Serve HTTPS privé -> loopback 8766          -> OpenAI LLM/STT/TTS
                                            -> Reply / intention / destinataire
                       ┌──────────────────────────────────────────────┐
                       v                      v                      v
                  Discord/Twitch       ffplay / avatar r20       Web Android
                  texte/vocal          + sous-titres OBS       JSON + audio WAV
~~~

**Aucun transport n'a de priorité fixe.** Le propriétaire utilise un launcher Windows qui choisit la branche Git et lance tous les supports en une fois. Le VPS Hyperliquid n'est pas une dépendance de Jade ; les serveurs HTTPS Tailscale sont **sur le PC Jade**, pas sur le VPS.

## 2. Couche plateforme et configuration

- `main.py` : entrée CLI, `--all-channels`, `--preflight`, initialisation `OpenAIServices` / `DemoChat`, `AsyncExitStack`, création des connecteurs, `Runtime`, audio et mémoire. `--all-channels` active live, voice, mic, Twitch, Discord, Discord vocal, API HTTP, avatar et mobile ; VTS seulement si son connecteur est configuré.
- `src/jade_runtime/config.py` : dataclass `Settings`, parsing typé, validations de sécurité ; `src/utility/private_config.py` : `JADE_SECRETS_FILE`, anciennes localisations privées de compatibilité, priorité des variables d'environnement du processus.
- `src/jade_runtime/diagnostics.py` : préflight local **sans appels réseau ou micro**. Les exigences des services sont vérifiées mais les SDK JS du Web et certaines capacités matérielles peuvent rester des diagnostics informatifs. Ne pas confondre présence de paquet et succès Android.
- `scripts/jade-launcher.ps1`, `jade-runner.ps1` et `install-jade-launcher.ps1` : interface WinForms, Git fast-forward si répertoire propre, Git LFS, Poetry extras all, préflight, démarrage console, installation dans `D:\Jade\launcher`. Aucune clé stockée dans la configuration du launcher (chemin du fichier privé uniquement).

## 3. Flux conversationnel et ordonnanceur

`messages.py` définit `Incoming` et `Reply` avec plateforme, auteur, identifiants, canal/session, mode d'entrée et métadonnées fiables des transporteurs. `orchestrator.py` possède une file limitée par `JADE_QUEUE_LIMIT` (défaut **64**), des objets `Work` (tour, deadline, validation, future de fin) et un worker séquentiel. L'API `submit` échoue sur saturation, sans écraser une autre demande. `task_done` / `queue.join` assurent le suivi des tâches. Les annulations, délais et arrêts empêchent de délivrer une réponse après invalidation d'une demande.

**Arbitrage (nouveau dans develop)** : `turn_arbitration.py` expose `ArbitratingQueue` et `TurnArbiter`. En cas de plusieurs travaux en attente, il considère jusqu'à **6 têtes de conversations distinctes** afin de **ne pas réordonner** les tours internes d'un même fil. Le backend LLM commun reçoit des extraits plafonnés des messages et retourne strictement l'identifiant numérique du prochain tour. L'arbitre ne transforme pas la réponse, ne choisit pas de destinataire différent et ne suit pas d'instructions contenues dans les extraits non fiables. Son délai par défaut est **2 s** ; réponse invalide/timeout/absence de backend = **FIFO**. Un tour en attente depuis **15 s** ou proche de sa deadline est traité via équité, sans priorité de plateforme. L'arbitrage ajoute potentiellement un appel LLM payant, **mais jamais si un seul travail est en attente**. La génération est séquentielle, l'arbitre ne préempte pas un tour en cours.

**Choix de répondre** : `dialogue.py` applique le prompt système, les contrôles de mention/commande/force_reply et les politiques de canal ; les sessions en RAM sont bornées et isolées. `discord_text_policy.py` gouverne notamment la participation spontanée Discord sans imposer de priorité globale. Les échecs d'API, délais et doublons d'IDs ne doivent pas polluer l'historique. Les logs de provenance sont fournis par `turn_logging.py`, avec une attention particulière aux données personnelles.

## 4. Mémoire persistante, identité et autobiographie

**DEV-011 révisée, demandes ordinaires uniquement :** `explicit_memory_intent.py` reconnaît les demandes naturelles de mémorisation en texte/STT, même lorsqu'elles mentionnent les Core Memories. `MemoryService.command` intercepte la demande avant le dialogue, vérifie l'identité de transport et son opt-in, filtre les secrets courants et appelle **exclusivement** `MemoryStore.put_requested_ordinary`. La transaction SQLite (`BEGIN IMMEDIATE`) revérifie le `person_id` initial, l'inscription et les doublons, puis écrit avec `kind='ordinary'`, TTL 365 jours et la portée de `_scope` ; la réponse ne confirme qu'après retour de cette transaction. Une demande explicite n'alimente pas le curateur et **ne peut pas créer de Core Memory**, y compris depuis Goldaj. L'ancienne méthode d'écriture Core forcée par propriétaire a été retirée. Le curateur autonome est le seul parcours du runtime qui sélectionne `core_self`/`core_relationship` à partir d'échanges ordinaires réellement admissibles, en ignorant les injonctions des utilisateurs ; `put_self_core` et `put(kind=core_*)` demeurent internes à la curation. Les anciennes commandes privées de consultation/suppression Core restent disponibles pour la correction ou l'effacement des données, jamais pour leur création forcée. Isolation par personne et salon inchangée.

`memory_store.py` utilise SQLite **local**, avec tables de profils, liens d'identifiants, souvenirs ordinaires et Core, dates et provenance. Les Core Memories n'ont pas de purge automatique mais restent supprimables selon les droits ; les faits ordinaires peuvent expirer. `memory_service.py` relie la mémoire aux tours : en mode réel, SQLite et la curation (`JADE_MEMORY_CURATOR_ENABLED=1` par défaut) sont activées, et le chemin de base est privé hors Git. Les comptes Discord vérifiés (serveur, vocal ou MP) sont inscrits automatiquement à leur première interaction traitée ; Twitch garde une activation explicite. L'ancienne commande `!jade-memoire oublier` et la liste de refus Discord sont supprimées ; les suppressions individuelles (`supprimer-self`, `supprimer-core`) et la déliaison restent opérationnelles. La curation peut appeler un modèle. Les écritures LLM invalides doivent être rejetées, les secrets non automatiquement inscrits. `memory_transfer.py` fournit export/import vérifiés sans écrasement.

**Souvenirs transversaux MVP (21/11) :** `MemoryStore.recall_linked` retrouve au maximum quatre souvenirs condensés des autres portées du même `person_id`, seulement si plusieurs identités vérifiées sont liées. `MemoryService.context_for` les utilise en conversation privée (PWA propriétaire, micro PC, MP Discord) et conserve huit souvenirs au maximum dans le prompt. Les salons publics Discord, vocaux et Twitch restent sur `recall` strictement limité à leur portée. Aucun historique brut de niveau 1 ne traverse les salons : `recent_conversation_turns` reste inchangé. Pas de migration SQLite, de copie des souvenirs ni de coût IA supplémentaire ; déliaison, suppression ciblée, TTL et curation autonome préservés. Cette version n'autorise pas à divulguer automatiquement les souvenirs privés dans les salons publics.

Les comptes Discord/Twitch sont identifiés par ID fiables du transport, **pas par pseudonyme visible**. Le micro local et l'application Android authentifiée représentent le même propriétaire Goldaj ; ils peuvent partager un profil mémoire. Les conversations Discord vocal/texte utilisent `discord_conversation.py` pour dériver une clé opaque de session vérifiée, évitant les fausses reprises d'ancienne session. Les mémoires autobiographiques de Jade demandent une discipline de séparation entre expériences du personnage et confidences des autres utilisateurs. L'absence d'activation sur les parcours manuels doit empêcher la collecte durable ; Discord conserve l'inscription automatique des comptes vérifiés ; l'information préalable des membres de serveur Discord est une condition d'exploitation.

## 5. Voix, intentions, sous-titres et animation

Le STT et TTS reposent sur **OpenAI**, non sur une synthèse locale alternative ; `openai_services.py`, `realtime_tts.py`, `voice_pipeline.py`, `microphone.py` et `discord_voice.py` convertissent audio, contrôlent le format et transmettent les réponses. `sentence_stream.py` et `early_speech.py` peuvent produire des phrases audio anticipées, sous contrôle des sessions/deadlines. `AudioCoordinator` réduit les boucles d'écho. Sur PC, `ffplay` lit le WAV ; le pont Discord peut diffuser à un salon autorisé. Les réponses locales privées (micro, HTTP) ne doivent **pas** être routées automatiquement vers un canal Discord public ou OBS.

`intent_engine.py` interprète le préfixe strict `[INTENT:...]` proposé par le LLM, le supprime des sorties visibles et des mémoires et fournit une direction vocale limitée. Le pitch Étincelle +2 demi-tons est un traitement PCM dans `pitch_shift.py` si FFmpeg/rubberband est disponible, **pas** une option `pitch` universelle du TTS OpenAI. `output.py` gère WAV, observation d'animation et fichiers de sous-titres temporaires ; `avatar.py` démarre l'avatar autonome r20 via son processus local. `vtube_studio.py` fournit un renderer optionnel distinct à URL WebSocket loopback.

Le modèle r20 est suivi via **Git LFS**. Les paquets graphiques Web propriétaire et les formats `.moc3` Cubism exigent des licences et une compatibilité testée ; leur présence dans le dépôt Python n'assure pas le rendu Android.

## 6. Connecteurs texte, HTTP et PWA

- **Discord** : `discord_text.py` et `discord_voice.py` reçoivent/émittent sur les destinations associées, contrôle des IDs, permissions, sessions vocales et reconnexions ; `discord_dave.py` et `discord_pcm.py` gèrent la pile audio/codec.
- **Twitch** : `twitch_irc.py` lit les messages IRC via TLS, gère PING/PONG et limitation d'envoi ; `twitch_rotation.py` et `twitch_token.py` valident/renouvellent les secrets si configurés.
- **HTTP PC** : `local_http.py` écoute seulement `127.0.0.1:8765` par défaut, Bearer indépendant et `POST /message` ; `phone_ui.py` est une petite interface Web locale texte, pas la PWA moderne.
- **Android** : `mobile_gateway.py` écoute seulement `127.0.0.1:8766`, sert `GET /`, `/assets/*`, `/vendor/*`, `/model/*` et, uniquement si configuré, `/models/next/*` avec chemins autorisés ; les appels `POST /api/chat` et `/api/voice` nécessitent un token Bearer distinct. Toutes les routes vérifient `Tailscale-User-Login` fourni par le proxy Serve, et les POST un contrôle d'origine HTTPS. Les WAV sont traités en RAM. L'API renvoie texte/intention et éventuellement WAV encodé.
- **Client Web** : `mobile_web/index.html`, `app.js`, `avatar.js`, `styles.css`, `manifest.webmanifest` et `sw.js`. Le jeton n'est stocké ni en cookie, ni en localStorage ; le service worker ne met pas en cache des conversations privées. Micro appuyer-pour-parler max 20 s ; capture abandonnée lors de passage en arrière-plan ; TTS joué localement dans le navigateur ; animation de bouche basée sur amplitude audio approximative.
- **Scène partagée entre onglets** : `.scene-panel` contient un bandeau `.scene-toolbar` au-dessus de `.room`, sans superposition au décor : Décor et Recentrer sont disponibles uniquement à l’Accueil fenêtré. `jade-theme.css` recadre les mini-scènes sur la tête. Le corps assis et le rendu Live2D gardent un repère commun. Le portrait et son canvas partagent un plan de décor distinct qui conserve le cadrage de la vue même pendant un changement d’avatar. `avatar.js` recadre aussi la cuisine et le repli debout. `app.js` relie le bouton plein écran, le double clic et le double appui à une bascule unique, avec exclusion des contrôles et gestes de défilement/pincement. Les tests Node `mobile_scene_framing_test.js` et `mobile_scene_gestures_test.js` sont exécutés en CI.

### Préférences mobiles et Config (27/11/2026)

`login-guard.js` charge `preferences.js` avant `app.js` et les modules visuels. Le seul enregistrement local `jade.mobile.preferences.v1` contient une version et des valeurs validées : voix, notifications, animations de la chambre, secousses, décor, modèle et niveau de filtrage des logs. Les champs inconnus et valeurs invalides sont rejetés ; aucun jeton, identifiant de compte, dialogue, audio ou état de session Live n’est enregistré. Le stockage refusé ou corrompu ne bloque pas le salon. La préférence Live conserve son registre serveur révisionné, sans duplication locale.

**Config → Paramètres** regroupe le modèle et les cases Mode Live, Voix activée, Animations de la chambre, Réagir aux secousses et Recevoir les rappels sur ce téléphone. Le son est ON au premier lancement ; un OFF enregistré est restauré avant toute requête de conversation. Les notifications reflètent la souscription et la permission réelles du navigateur ; une erreur d’inscription ne devient pas une activation confirmée. La restauration des réglages ne demande aucune permission et ne relance ni capture ni lecture. Les paragraphes permanents ont été retirés ; les échecs utiles restent affichés.

Le décor explicitement indiqué par `?room=bedroom|kitchen` prime sur le choix enregistré. Le choix de décor est sauvegardé après chargement réussi ; celui du modèle après confirmation du renderer. Les logs se rafraîchissent et défilent automatiquement. Le suivi OpenAI affiche les deux montants, la date du dernier relevé et le lien de facturation. [Passation du lot](../operations/handoffs/2026-11-27-chatgpt-mobile-config.md).

### Sélection du modèle mobile (26/11/2026)

Le sélecteur **Modèle** appartient à **Config**. Au lancement, `avatar.js` attend le catalogue et charge le choix enregistré s’il est disponible, sinon le défaut du catalogue. Le repli temporaire ne remplace pas la préférence enregistrée. `login-guard.js` charge d’abord les préférences et l’application de conversation, puis le catalogue, la scène, le SDK et le chargeur d’avatar. L’ouverture de Config ne provoque aucun chargement supplémentaire.

`GET /assets/avatar-models.json` fournit le catalogue v1 suivant :

| Profil | URL du manifeste | Présentation | Intentions du classique | Mouvement initial | Disponibilité livrée |
| --- | --- | --- | --- | --- | --- |
| `classic` | `/model/Jade.model3.json` | `seated` | Oui | `Idle` | Disponible |
| `next` | `/models/next/Jade.model3.json` si le paquet est disponible | `full` | Motions r21 | `Idle` déclaré dans le paquet | r21 v45.1 livré par Git LFS |

`defaultId` vaut `next` quand le paquet est disponible, autrement `classic`. Le serveur lit la livraison v45.1 versionnée et expose son manifeste sous le nom attendu. Il ajoute quatre expressions Web au manifeste virtuel. Le répertoire optionnel `JADE_MOBILE_SECOND_MODEL_DIR` fournit son propre `Jade.model3.json` et ses expressions. Le serveur valide les références locales et refuse les liens symboliques, chemins sortants et pointeurs Git LFS non matérialisés.

Le catalogue côté client est immuable et n’accepte que les deux profils et les URL locales attendus. Une erreur de lecture ou un délai dépassé conserve un catalogue classique sûr. `JadeAvatar.state` expose `status`, `modelId`, `requestedId` et `message` ; `jade-avatar-state` notifie les changements. Le contrôle est désactivé avant disponibilité du renderer et pendant le chargement. `selectModel(id)` ne vaut réussite que lorsque le modèle demandé est réellement prêt ; les refus et replis restent visibles.

Le chargeur détient les ressources d’un seul modèle à la fois, y compris celles acquises avant un échec partiel. Le remplacement retire d’abord le corps DOM via `JadeSeatedScene.deactivate()`, arrête le modèle et libère ses ressources avant toute nouvelle allocation. Si la libération ne peut pas être confirmée, le rendu demande un rechargement au lieu de superposer deux modèles. `usesSeatedBody` réserve la composition hybride au profil classique prêt. Les images de corps en retard sont invalidées par génération ; un retour au classique relance leur préparation. Le portrait vertical est déclaré dans `salon.html`. `portrait-bedroom-motion.js` suit le chargement de cette image et la visibilité du salon. `seated-scene.js` charge le corps du classique et le cadrage du r21 répond à la pièce sélectionnée.

Le sélecteur appelle `JadeConversation.stopForModelChange()` avant le remplacement. La PWA arrête la capture, les sources audio et la pose, annule la requête ou le duplex, et ignore les événements tardifs. La conversation peut être relancée manuellement quand la bascule se termine. [Cycle des modèles](../operations/handoffs/2026-11-26-codex-mobile-r21.md)

Pour le r21, `JadeAvatar.setIntent` tire A ou B à parts égales une fois par réponse. La pose profite de la préparation du son et le geste est déclenché au premier tampon planifié. Une file PCM vide ferme les lèvres jusqu’au tampon suivant. Une fois le flux terminé et toutes les sources jouées, la pose reste 600 ms puis s’efface en 220 ms. Le PCM et le WAV partagent l’enveloppe d’ouverture. Les sourcils et la forme de la bouche répondent à l’intention. [Recette des intentions](../operations/handoffs/2026-11-26-codex-mobile-intentions.md)

Pour chaque intention, une petite variation du buste précède le calcul de la physique. L’ouverture expressive des paupières multiplie leur ouverture après le clignement, ce qui préserve la fermeture complète. La forme des lèvres interpole entre le dessin au repos et la forme choisie pendant la parole. Les quatorze clips se chargent en arrière-plan au montage du r21. Le lecteur vérifie la réplique active avant de confier au SDK un clip téléchargé tardivement.

Le manifeste mobile référence le MOC3 v49.1, les atlas retouchés et les quatorze clips d’intention. Il réutilise la physique du v45.1. Les poses de rotation de la peau suivent deux contours dessinés de joue et de menton. Les yeux et les sourcils partagent un déformeur distinct. La frange et l’arrière de la tête disposent chacun de leur propre déformeur. La peau masque les deux longues mèches à leur passage sur la joue et le haut du cou se prolonge derrière la mandibule. Ces formes natives se combinent avec la parole, le clignement et les mouvements de tête. Les courbes de regard se terminent en douceur vers la pose tenue. Au fil du mouvement, le moteur remet les axes du regard à leur valeur de base avant de lire les courbes. Un paquet fourni par `JADE_MOBILE_SECOND_MODEL_DIR` conserve ses propres références.

L’ouverture r21 est modulée en trois-quarts par la valeur absolue de `ParamAngleX`, la forme de bouche effectivement rendue et l’enveloppe de voix. La réponse continue préserve la fermeture à zéro, l’amplitude de face et l’ordre des ouvertures. Elle atténue surtout les voyelles les plus ouvertes des sourires à fort angle.

Le r21 échantillonne `ParamBreath` après le calcul du souffle et de la physique dans Cubism. Deux réponses légèrement retardées sont ajoutées à `ParamJadeEarFollowL/R` avec une marge qui dépend de la valeur physique courante. À la préparation d’une réponse, l’intention ajoute sa propre courbe de mouvement avec une transition vers une pose tenue. Les profils asymétriques d’Enjouée et de Curieuse suivent la variante A/B. La pose suit le fondu du visage et les valeurs d’oreille sont restaurées par le SDK après chaque image.

Sur l’Accueil et en plein écran, `avatar-gestures.js` écoute les pointeurs tactiles dans la zone du r21 et distingue les gestes consommés des appuis courts du plein écran. Le rendu applique le zoom et le déplacement par-dessus le cadrage de scène. Une limite conserve une partie saisissable dans la zone visible. Les gestes sont annulés au départ du modèle ou de la vue et le bouton **Recentrer** rétablit le cadrage de référence.

Le push-to-talk classique transmet le PCM au WebSocket authentifié pendant l’appui. Le relâchement ferme la capture et termine le tour. Le mode classique peut transmettre le WAV au relâchement en secours si le WebSocket a échoué avant son état prêt. `avatar-shake.js` demande l’accès aux capteurs au besoin à l’activation du réglage dans Config. Le r21 traduit la secousse en angles amortis dans la boucle Live2D qui calcule la physique. Le zoom et le déplacement restent les coordonnées du cadrage.

**Modèle de sécurité :** aucune ouverture publique du port mobile, aucune CORS générale, aucun Funnel, pas de transit par le VPS trading. Le fait de posséder l'URL privée ne dispense pas du bon compte Tailscale et du token. Un code local sur le PC capable d'usurper l'en-tête sur loopback reste hors du modèle de confiance, ce qui rend l'isolation du PC importante.

## 7. Infra, opérations, limites et tests

~~~text
GitHub public (branches main/develop, PR, Actions, Git LFS)
     |
Windows PC Jade (clone + Poetry + modeles LFS sur D:)
     |-- process Python Jade :443? NON (boucle locale uniquement)
     |-- Discord/Twitch/OpenAI : connexions sortantes autorisees
     |-- Tailscale Serve prive HTTPS (.ts.net) -> 127.0.0.1:8766
     |-- API HTTP texte : 127.0.0.1:8765
     |-- SQLite memoire privee et fichiers de configuration hors Git
     |-- FFmpeg / ffplay / r20 Live2D / eventuel VTube Studio
     |
Android Chrome PWA + Tailscale -> URL privee Serve PC Jade
~~~

`D:\Jade\launcher` est volontairement **hors du clone**, ce qui impose une réinstallation après changement de scripts. Les données SQLite et secrets sont hors Git et ne se réinitialisent pas lors d'un `git switch` normal. Le PC doit rester allumé ; pas de reprise par le VPS. Les appels OpenAI (dialogue, STT, TTS, arbitre, curation) peuvent être facturables séparément. Les logs et l'overlay OBS exigent une politique de confidentialité concrète ; ne jamais les committer.

**Validation automatisée :** `python -m compileall`, `python -m unittest discover -s tests -v`, tests du module mobile, mémoire, intentions, arbitrage et routage privé ; `scripts/check_docs.py` contrôle les guides par branche. GitHub Actions exécute Windows et Ubuntu en mode hors ligne, avec scan secrets. **Ce n'est pas une validation du PC réel** : prévoir recette Discord/Twitch/micro/audio, animation r20 Windows/Web, Tailscale et Android Wi-Fi/4G, charge simultanée, pertes de réseau, coûts réels, arrêt/reprise et fuite inter-canaux.

**Maintenance :** pour les changements techniques, mettre à jour le journal [`docs/operations/CHANGELOG.md`](../operations/CHANGELOG.md), puis **uniquement les guides, atlas, README, consignes AGENTS et passations réellement impactés**, conformément à [AGENTS.md](../../AGENTS.md) et [AGENT_COORDINATION.md](../operations/AGENT_COORDINATION.md). Aucune réécriture automatique de tous les guides ; une correction purement documentaire ne requiert pas d'entrée technique au changelog. Ne pas merger `develop` dans `main` simplement pour lui donner ces documents.

## 8. Contrat émotionnel avatar Live2D (ajout du 15/11/2026)

Flux : LLM → préfixe `[INTENT:...]` filtré par `intent_engine.py` → `Reply.intent` validé → `main.py:on_reply` → `Avatar.set_intent` pour l'avatar autonome r20 sur PC, ou JSON `{reply,intent,audio_wav_b64}` vers `mobile_web/app.js` → `JadeAvatar.setIntent` pour la PWA. L'intention envoyée à `SpeechOutput` reste inchangée. Aucun classifieur LLM ou TTS supplémentaire.

**Contrat unique v1 :** `src/jade_runtime/mobile_web/intent-visuals.json` (7 clés, exactement deux variantes chacune pour le catalogue actuel, champ `expression` limité aux expressions r20 et `text` uniquement décoratif). `intent_visuals.py` valide le catalogue, le fallback inconnu → `neutral`, puis sélectionne les variations en rotation par label pour PC ; la PWA lit le même catalogue via `GET /assets/intent-visuals.json` sur la passerelle privée. Le booléen `enabled` n'est pas un état du LLM : il provient du seul réglage `Settings.avatar_intent_enabled` / `JADE_AVATAR_INTENT_ENABLED` (défaut `1`). Il est évalué au lancement ; redémarrage et rechargement PWA nécessaires.

**PC et concurrence :** `avatar.py` possède un unique writer JSON sur stdin du processus `src/jade_runtime/avatar_renderer.py`, alimenté par deux derniers états coalescés indépendants : `expression` (rare) et `mouth` (25 Hz ou niveaux PCM consommés). `_offer` bascule les callbacks audio provenant d'autres threads sur la boucle asyncio. L'avatar revient à `Neutral` après `end/pcm_end` ou après 12 s sans audio actif. Le renderer enfant savait déjà recevoir `{type:expression,value:...}` et vérifier la palette r20 ; aucun nouveau binaire graphique n'est ajouté.

**Modèle classique et repli mobile.** `mobile_gateway.py` sert la palette sous identité Tailscale. Pour le r20, `avatar.js` applique l’expression de la palette via les `.exp3` disponibles. Le chat et la voix restent utilisables si le SDK, les ressources ou la palette sont indisponibles. Le r21 suit la chronologie décrite dans la [sélection du modèle mobile](#sélection-du-modèle-mobile-26112026).

**Runtime Windows.** Les variantes sont les expressions faciales du r20. Le raccordement des quatorze motions du r21 au bot Windows reste suivi dans DEV-001. [Passation Live2D d’origine](../history/gpt6-jade/LIVE2D-INTENT-ANIMATION-HANDOFF-20261115.md)

## 9. Dialogue, historique et participation

Le backend `OpenAIServices` transmet `reasoning_effort=low` et `max_completion_tokens=320` par défaut, en appel normal et en streaming. `MemoryStore` SQLite v4 conserve les tours complets des personnes consentantes **7 jours** et `MemoryService` restaure **tous les tours des dernières 24 h** d'une identité et d'un salon, sans `LIMIT` SQL ni troncature `deque` des sessions SQLite. Le contexte du modèle peut néanmoins atteindre les plafonds de tokens du fournisseur ; aucun quota en nombre d'échanges n'est appliqué par Jade. Les souvenirs ordinaires (`kind='ordinary'`) expirent après **365 jours**, les Core n'ont aucun TTL. La migration v3→v4 recalcule les échéances ordinaires existantes depuis `created_at`, sans déplacer les Core. Purge au lancement et toutes les heures en mode réel ; la curation reste asynchrone.

`DiscordTextPolicy` et le vocal utilisent 100 % de réponse en tête-à-tête observé et un tirage à 20 % des tours spontanés admissibles en groupe. `TwitchIRC` ignore les nouveaux messages pendant un tour Twitch en cours, force une réponse si un seul auteur est observé et passe par le dialogue pour les 30 % en groupe ; les spectateurs silencieux ne sont pas comptés.

Les sept intentions disposent de variantes faciales et textuelles sur le r20 et de deux motions dédiées par intention sur le r21 mobile. [Dialogue et participation](../history/gpt6-jade/DIALOGUE-LOW320-HISTORIQUE-PARTICIPATION-20261115.md) · [Inventaire actuel](BRANCH_STATE.md)

La roadmap technique non implémentée est centralisée dans le [catalogue](../ameliorations/README.md). Les anciennes anomalies et comptes rendus CI restent dans les audits datés et ne sont pas répétés dans cette documentation d'architecture.


## Correctif de streaming PCM et liaison d'identités (PR #23)

`SpeechOutput.start_early` et `_speak_progressive` acceptent maintenant `discord_voice` même avec `AudioOutput('ffplay')`, lequel reste réservé aux réponses du micro local dans le parcours PCM. Le streaming exige un modèle TTS Realtime, une session Discord autorisée et la capacité `play_pcm_stream_for_reply` ; à la date de cette PR, le repli WAV conservait des effets locaux ; **DEV-003 du 19/11 retire ensuite la lecture locale du fallback Discord vocal**. `MobileGateway` expose `POST /api/link` uniquement après double authentification PWA Tailscale + Bearer ; la source est le profil privé Goldaj, la cible un ID numérique `discord` ou `twitch`. Le secret temporaire encodant la cible est à usage unique, confirmé par `!jade-memoire confirmer` depuis l'identité authentifiée par son connecteur ; les profils SQLite et historiques sont rapprochés sans effacer les échanges lors du merge. La commande globale `!jade-memoire oublier` n'existe plus ; `!jade-memoire delier` sépare les comptes en conservant les souvenirs. Le texte du code de liaison est masqué avant l'arbitrage LLM, dans les logs et le contexte Discord. Voir [la fiche de mission](../operations/handoffs/2026-11-16-chatgpt-pcm-memoire-mobile.md) ; SDK Live2D Web toujours à installer sur D:, aucune animation r21 livrée.

## Instrumentation de latence multi-canaux (DEV-008, 19 novembre 2026)

Activer `JADE_LATENCY_LOG=1` dans la **configuration privée** (défaut `0`) pour émettre sur stderr les jalons `jade.latency` des tours de chaque plateforme. Chaque ligne ne comporte que l'identifiant technique du tour, la plateforme/modalité, un nom de jalon et la durée monotone `since_queue_ms` ; aucun texte, auteur, canal, ID transport ni audio. Les jalons comprennent la prise en file, la mémoire facultative, le LLM, le début/fin d'appel aux sorties et la complétion/échec. `delivery_end` atteste seulement le retour du callback, **pas** la diffusion audio complète si un flux vocal asynchrone continue. Ces métriques sont destinées aux expériences p50/p95 ; le STT et le premier son réellement audible demandent encore les mesures REC-010 sur le PC.
