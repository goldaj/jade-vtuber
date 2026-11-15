# Guide technique : architecture, infrastructure et algorithmes de Jade sur develop

**Références visuelles :** voir les [deux schémas d'architecture](../architecture/README.md), l'un sur les appels et leur chronologie, l'autre sur les postes, services et responsabilités. Ces vues sont datées ; le code exécuté et les réglages de cette branche ont priorité sur les illustrations.

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

`memory_store.py` utilise SQLite **local**, avec tables de profils, liens d'identifiants, souvenirs ordinaires et Core, dates et provenance. Les Core Memories n'ont pas de purge automatique mais restent supprimables selon les droits ; les faits ordinaires peuvent expirer. `memory_service.py` relie la mémoire aux tours après activation explicite, propose des commandes de consentement et une curation asynchrone facultative (`JADE_MEMORY_CURATOR_ENABLED`) pouvant appeler un modèle. Les écritures LLM invalides doivent être rejetées, les secrets non automatiquement inscrits. `memory_transfer.py` fournit export/import vérifiés sans écrasement.

Les comptes Discord/Twitch sont identifiés par ID fiables du transport, **pas par pseudonyme visible**. Le micro local et l'application Android authentifiée représentent le même propriétaire Goldaj ; ils peuvent partager un profil mémoire. Les conversations Discord vocal/texte utilisent `discord_conversation.py` pour dériver une clé opaque de session vérifiée, évitant les fausses reprises d'ancienne session. Les mémoires autobiographiques de Jade demandent une discipline de séparation entre expériences du personnage et confidences des autres utilisateurs. L'absence d'opt-in doit empêcher la collecte durable.

## 5. Voix, intentions, sous-titres et animation

Le STT et TTS reposent sur **OpenAI**, non sur une synthèse locale alternative ; `openai_services.py`, `realtime_tts.py`, `voice_pipeline.py`, `microphone.py` et `discord_voice.py` convertissent audio, contrôlent le format et transmettent les réponses. `sentence_stream.py` et `early_speech.py` peuvent produire des phrases audio anticipées, sous contrôle des sessions/deadlines. `AudioCoordinator` réduit les boucles d'écho. Sur PC, `ffplay` lit le WAV ; le pont Discord peut diffuser à un salon autorisé. Les réponses locales privées (micro, HTTP) ne doivent **pas** être routées automatiquement vers un canal Discord public ou OBS.

`intent_engine.py` interprète le préfixe strict `[INTENT:...]` proposé par le LLM, le supprime des sorties visibles et des mémoires et fournit une direction vocale limitée. Le pitch Étincelle +2 demi-tons est un traitement PCM dans `pitch_shift.py` si FFmpeg/rubberband est disponible, **pas** une option `pitch` universelle du TTS OpenAI. `output.py` gère WAV, observation d'animation et fichiers de sous-titres temporaires ; `avatar.py` démarre l'avatar autonome r20 via son processus local. `vtube_studio.py` fournit un renderer optionnel distinct à URL WebSocket loopback.

Le modèle r20 est suivi via **Git LFS**. Les paquets graphiques Web propriétaire et les formats `.moc3` Cubism exigent des licences et une compatibilité testée ; leur présence dans le dépôt Python n'assure pas le rendu Android.

## 6. Connecteurs texte, HTTP et PWA

- **Discord** : `discord_text.py` et `discord_voice.py` reçoivent/émittent sur les destinations associées, contrôle des IDs, permissions, sessions vocales et reconnexions ; `discord_dave.py` et `discord_pcm.py` gèrent la pile audio/codec.
- **Twitch** : `twitch_irc.py` lit les messages IRC via TLS, gère PING/PONG et limitation d'envoi ; `twitch_rotation.py` et `twitch_token.py` valident/renouvellent les secrets si configurés.
- **HTTP PC** : `local_http.py` écoute seulement `127.0.0.1:8765` par défaut, Bearer indépendant et `POST /message` ; `phone_ui.py` est une petite interface Web locale texte, pas la PWA moderne.
- **Android** : `mobile_gateway.py` écoute seulement `127.0.0.1:8766`, sert `GET /`, `/assets/*`, `/vendor/*`, `/model/*` avec chemins autorisés ; les appels `POST /api/chat` et `/api/voice` nécessitent un token Bearer distinct. Toutes les routes vérifient `Tailscale-User-Login` fourni par le proxy Serve, et les POST un contrôle d'origine HTTPS. Les WAV sont traités en RAM. L'API renvoie texte/intention et éventuellement WAV encodé.
- **Client Web** : `mobile_web/index.html`, `app.js`, `avatar.js`, `styles.css`, `manifest.webmanifest` et `sw.js`. Le jeton n'est stocké ni en cookie, ni en localStorage ; le service worker ne met pas en cache des conversations privées. Micro appuyer-pour-parler max 20 s ; capture abandonnée lors de passage en arrière-plan ; TTS joué localement dans le navigateur ; animation de bouche basée sur amplitude audio approximative.

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

**Maintenance :** tout changement d'interface, configuration, source, test, asset ou infra doit mettre à jour **les six guides principaux, la note de nettoyage, le README, AGENTS et les passations spécialisées impactées dans la même branche**. Voir [AI_HANDOFF.md](AI_HANDOFF.md). Ne pas merger `develop` dans `main` simplement pour lui donner ces documents.

## 8. Contrat émotionnel avatar Live2D (ajout du 15/11/2026)

Flux : LLM → préfixe `[INTENT:...]` filtré par `intent_engine.py` → `Reply.intent` validé → `main.py:on_reply` → `Avatar.set_intent` pour l'avatar autonome r20 sur PC, ou JSON `{reply,intent,audio_wav_b64}` vers `mobile_web/app.js` → `JadeAvatar.setIntent` pour la PWA. L'intention envoyée à `SpeechOutput` reste inchangée. Aucun classifieur LLM ou TTS supplémentaire.

**Contrat unique v1 :** `src/jade_runtime/mobile_web/intent-visuals.json` (7 clés, exactement deux variantes chacune pour le catalogue actuel, champ `expression` limité aux expressions r20 et `text` uniquement décoratif). `intent_visuals.py` valide le catalogue, le fallback inconnu → `neutral`, puis sélectionne les variations en rotation par label pour PC ; la PWA lit le même catalogue via `GET /assets/intent-visuals.json` sur la passerelle privée. Le booléen `enabled` n'est pas un état du LLM : il provient du seul réglage `Settings.avatar_intent_enabled` / `JADE_AVATAR_INTENT_ENABLED` (défaut `1`). Il est évalué au lancement ; redémarrage et rechargement PWA nécessaires.

**PC et concurrence :** `avatar.py` possède un unique writer JSON sur stdin du processus `demo/reelle/avatar.py`, alimenté par deux derniers états coalescés indépendants : `expression` (rare) et `mouth` (25 Hz ou niveaux PCM consommés). `_offer` bascule les callbacks audio provenant d'autres threads sur la boucle asyncio. L'avatar revient à `Neutral` après `end/pcm_end` ou après 12 s sans audio actif. Le renderer enfant savait déjà recevoir `{type:expression,value:...}` et vérifier la palette r20 ; aucun nouveau binaire graphique n'est ajouté.

**Mobile et dégradation :** `mobile_gateway.py` sert le JSON de palette en lecture sous identité Tailscale ; `avatar.js` lit le catalogue avant d'essayer le SDK Web, sélectionne A/B par intention, affiche un libellé `textContent` et déclenche les `.exp3` connues. Si le SDK/asset ou le catalogue manque, la discussion et la voix continuent. `app.js` évite de doubler les commandes d'émotion et ne remplace plus les libellés par un état vocal générique ; l'Idle est rétabli en fin de voix. La remise à zéro des expressions Web utilise `resetExpression()` seulement si la version du SDK l'expose ; validation matérielle obligatoire.

**Limite métier :** aucun des deux rendus ne dispose encore de **deux nouvelles motions corporelles distinctes par intention**. Les variantes sont des expressions faciales du r20, certaines réutilisées. L'animation de base Idle et la bouche sont conservées. L'extension v2 avec 14 ressources propres doit être conçue, riggée, validée et seulement ensuite activée. Ne pas basculer automatiquement sur le r21 en pied non finalisé. Contrat/risques/tests : [passation Codex Live2D](../gpt6-jade/LIVE2D-INTENT-ANIMATION-HANDOFF-20261115.md).

## Mise à jour technique : dialogue Low/320 et histoire exacte (2026-11-15)

Le backend `OpenAIServices` envoie maintenant explicitement `reasoning_effort=settings.reasoning_effort` et `max_completion_tokens=settings.max_completion_tokens` sur les deux voies Chat Completions. `Settings` fixe les valeurs par défaut `low` et `320`, avec variantes privées ; le niveau de raisonnement et le plafond doivent être vérifiés auprès de l'API réellement déployée, et les coûts comprennent les tokens cachés du raisonnement.

`Dialogue` réhydrate son deque à l'ouverture de session si `Runtime` a retrouvé l'historique SQLite. Taille par défaut du deque : 48 messages. `MemoryStore` passe au schéma v3 et fournit `conversation_turns`, `append_conversation_turn` et `recent_conversation_turns`; `MemoryService` fournit `history_for` et `remember_turn`. Seuls les profils activés et identifiés conservent leurs échanges complets après remise réussie. Les histoires ne sont pas résumées ; 24 derniers tours maximum sont chargés dans le modèle, le reste restant en SQL. La portée de confidentialité est déterminée par `_scope` ; les données du propriétaire privé ne sont pas injectées dans un canal public. La commande d'effacement du profil supprime aussi la table liée par clé étrangère. Les anciens identifiants micro redémarraient à 1 ; ils comprennent maintenant un préfixe aléatoire de session pour éviter la déduplication accidentelle.

La politique de présence exploite les auteurs humains actifs sur Discord écrit et Twitch sur 10 min, et la liste des membres du salon vocal Discord quand accessible. Le tête-à-tête provoque une réponse pour chaque tour admissible, le groupe échantillonne 30 % des tours spontanés ; les messages expressément adressés restent prioritaires. Les limitations d'audience, de cooldown et d'anti-écho restent applicables. Ne pas considérer le taux de 30 % comme une garantie empirique sur le trafic reçu.

Les intentions existantes et la réponse textuelle vocale restent inchangées ; deux variantes de réaction par intention sont seulement prévues, sans modification des assets 2D. Voir [décision, tests et risques](../gpt6-jade/DIALOGUE-LOW320-HISTORIQUE-PARTICIPATION-20261115.md).

## Audit de fiabilité DevOps du 15/11/2026

**Audit de référence** : [revue DevOps develop du 15 novembre 2026](../gpt6-jade/AUDIT-DEVOPS-DEVELOP-20261115.md). Les workflows de rebuild/scan secrets/hygiène publication limitent désormais les exécutions parallèles obsolètes par ref/PR ; le workflow principal conserve le checkout complet **nécessaire** à `scripts/check_docs.py`, désactive la persistance du token de checkout et exécute le préflight avant installation Poetry. Le diagnostic de runner ne se déclenche plus sur une vieille branche. Le format de sauvegarde SQLite accepte les versions 1, 2 et 3 sans modifier le format ZIP et ses contrôles d'intégrité ; il reste non chiffré. La CI du SHA initial audité était rouge ; le correctif ciblé ne vaut pas certification globale. Vérifier le SHA et les résultats réels avant de déployer.
