# Architecture et fonctionnement interne de Jade : branche docs/jade-persistent-memory-identity-20261115

**Périmètre de branche historique : `docs/jade-persistent-memory-identity-20261115`.** Branche de **cadrage mémoire persistante et identités** : ses 5 commits encore uniques face à develop portent principalement sur les documents PLAN-MEMOIRE-PERSISTANTE-IDENTITES-CORE-20261115.md, le journal et les instructions. **Aucune implémentation SQLite/Core Memories dans cette branche.** Le code vocal/intention/log est présent via les travaux antérieurs. Le plan n'est pas le produit. Avant suppression, comparer son contenu de cadrage avec les plans de develop et préserver toute décision non reprise.


## 1. Vue d'ensemble

Jade est un runtime Python 3.11 asynchrone, chargé depuis `main.py`, avec une interface de dialogue remplaçable. Son modèle d'entrée est `Incoming` (`messages.py`), de sortie `Reply` ; le traitement central est `Runtime` (`orchestrator.py`). La configuration est dans `config.py` et les fichiers de prompt dans `assets.py`. Aucune infrastructure serveur distante obligatoire ne sert la démo hors ligne. Les fournisseurs payants et les connecteurs sont explicitement activés par drapeaux sur `main`.

~~~text
Terminal / Discord écrit / Twitch IRC / HTTP local / micro / Discord vocal
     | parse, validation, anti-doublon, routage session, politiques
     v
Incoming -> Runtime.queue [asyncio.Queue FIFO bornée] -> Runtime._process
     -> Dialogue.respond [filtrage, prompt, historique, modèle OpenAI ou DemoChat]
     -> Reply -> routage console / chat d'origine / TTS / sous-titres / VTS
                  ^                                      |
          STT OpenAI (micro ou vocal Discord)       ffplay et avatar r20
~~~

Les responsabilités sont délimitées : le moteur ne connaît pas les secrets du dépôt ; les transporteurs ne doivent pas manipuler directement les prompts ; les callbacks de sortie préservent la destination d'origine.

## 2. Processus et supervision

`main.py` parse les drapeaux, charge `Settings.load()`, valide la configuration, ouvre un `AsyncExitStack`, crée le backend `OpenAIServices` ou `DemoChat`, la classe `Dialogue`, l'avatar, l'audio, puis `Runtime`. Les connecteurs Twitch/Discord/micro/HTTP tournent comme tâches `asyncio`. La console est le mode de repli si aucun connecteur continu n'est activé. `AsyncExitStack` et le bloc `finally` ferment ressources, lecteurs et tâches après Ctrl+C ou une erreur. Le code de `main` **ne propose pas** `--all-channels`, contrairement à `develop`.

Les erreurs d'un connecteur peuvent remonter au superviseur, qui ferme les autres tâches, plutôt que de laisser un faux fonctionnement « complet ». Le préflight `diagnostics.py` contrôle la présence des SDK, formats et dossiers, sans connexion réseau. L'utilisateur doit distinguer résultat des vérifications statiques et succès réel.

## 3. Algorithmes du runtime

### File et concurrence

`Runtime.queue` est une `asyncio.Queue` de capacité `JADE_QUEUE_LIMIT` (défaut **64**, borne 1 à 1024). `submit()` ajoute un `Work` et retourne immédiatement ; une file pleine déclenche `QueueFull`. Un seul worker `_process()` extrait les tâches **dans l'ordre FIFO**. L'exécution d'un tour est protégée par une tâche interne ; une échéance éventuelle invalide le travail et annule les appels en cours. Les tâches ont des compteurs `task_done()` ; `idle()` attend `queue.join()`. L'arrêt gracieux est borné et peut basculer en annulation. La réponse n'est émise que si le travail reste valide.

**Absence importante :** aucun arbitrage de tours par IA dans `docs/jade-persistent-memory-identity-20261115`. L'algorithme `TurnArbiter` a été introduit plus tard dans `develop`.

### Historique et choix de répondre

`Dialogue` conserve des `deque` bornées par clé de session, généralement le salon ou la session locale ; historique par défaut **24 messages**, cap 100. Les caches sont bornés à **256 sessions** avec TTL **1800 secondes** pour les sessions inactives ; la mémoire est en **RAM** et disparaît à l'arrêt. Un `asyncio.Lock` protège chaque session. Les identifiants de transport sont conservés dans une petite file `seen` afin d'éviter de traiter deux fois un même événement ; le texte répété intentionnellement n'est pas dédupliqué.

`should_reply()` traite d'abord les demandes `force_reply`, les préfixes explicites, la mention du nom, puis un tirage aléatoire configuré (par défaut 0). Les politiques des connecteurs peuvent influencer les messages proposés. Le dialogue construit un rôle `system` depuis le prompt, un contexte de salon **non fiable** et le message courant. Les sorties invalides/vides et les appels LLM ratés ne doivent pas polluer l'historique ; les flux oraux interrompus ont une logique de commit distincte.

### Streaming et latence

`Dialogue.respond` peut appeler `complete_stream`. `sentence_stream.py` assemble les fragments en phrases ; `early_speech.py` et `voice_turns.py` préparent une sortie TTS anticipée lorsque `JADE_EARLY_VOICE` est activé et que le backend le supporte. La lecture anticipée et les sous-titres nécessitent un suivi strict de la session pour éviter les réponses après expiration. Ce n'est pas une garantie de latence inférieure à une valeur donnée.

## 4. Interfaces, données et sécurité

| Module | Responsabilité | Contraintes |
| --- | --- | --- |
| `twitch_irc.py`, `twitch_token.py`, `twitch_rotation.py` | Lire les PRIVMSG IRC/TLS, gérer validation/renouvellement de tokens, sortie chat | OAuth réel, limitation des envois, stockage privé |
| `discord_text.py`, `discord_text_policy.py` | Entrées textuelles, filtre, politique de participation, réponse dans le salon | Permissions/intents Discord ; ignorer sa propre identité |
| `discord_voice.py`, `discord_dave.py`, `discord_pcm.py` | Transport/PCM vocal, état session, transcription STT, émission audio Discord | dépendances DAVE/FFmpeg, sessions révocables et politiques de consentement |
| `microphone.py`, `voice_pipeline.py` | Capture PCM, détection parole, STT OpenAI, conversion en message | périphérique et permission micro, prévention d'écho |
| `openai_services.py`, `openai_client.py`, `realtime_tts.py` | Dialogue, STT/TTS et transport streaming OpenAI | clé privée, crédit, erreurs réseau, coûts |
| `output.py` | Audio WAV, ffplay, sous-titres temporaires | effacer les sous-titres après lecture, ne pas exposer des échanges privés |
| `avatar.py`, `vtube_studio.py` | Processus Live2D r20 et API VTS optionnelle | GPU, Git LFS, SDK/logiciel local |
| `local_http.py`, `phone_ui.py` | Serveur loopback texte et page Web locale | Bearer 32+ caractères, pas de CORS ouvert, pas d'accès public |
| `private_config.py`, `config.py` | Charger le fichier `JADE_SECRETS_FILE` et valider les paramètres | ne jamais committer des secrets ; environnement prioritaire |

### Frontières de confiance

Les plateformes externes fournissent du contenu **non fiable**. Les champs utilisateur et extraits Discord restent des données, pas des instructions système. Le service HTTP a un jeton Bearer, du contrôle de longueur, un endpoint fixe et un bind loopback, pas une API publique. Les tokens Twitch, Discord, VTS et OpenAI ne doivent pas apparaître dans les journaux. Le dossier `src/utility/private_config.py` gère les priorités de configuration. Les sous-titres OBS et les sorties vocales publiques sont des surfaces de fuite potentielles, à tester avant la diffusion.

La démo Express n'accède pas à ces services. Le processus de mémoire de Jade sur `main` est volatile : ne pas inventer de base de données ni de politiques Core Memories à cette version.

## 5. Infrastructure, déploiement, CI et ressources

- **Windows local** pour la démo Express (PowerShell WinForms) et la démo réelle ; le moteur Python peut exécuter des composants hors ligne sous Linux/Windows, mais Live2D et l'audio restent dépendants de pilotes.
- **GitHub** héberge le dépôt public et les Git LFS de modèles/sources graphiques. Aucun token dans les artefacts publics. Les binaires propriétaires sont soumis à licence.
- **GitHub Actions** : `.github/workflows/jade-rebuild.yml` exécute les tests de compilation et unittest sur Windows et Ubuntu ; `jade-secret-scan.yml` recherche des secrets ; les autres workflows ont des objets spécifiques. Une CI verte ne valide pas l'audio matériel, Discord/Twitch réels ou des facturations.
- **Données** : historique conversationnel volatile par session ; logs runtime/latence et fichier texte de sous-titres éventuellement sur disque ; aucune base SQLite de mémoire persistante dans cette branche.
- **Réseau** : démo offline isolée ; connexions OpenAI/Twitch/Discord uniquement sur opt-in ; API texte liée à `127.0.0.1`. Les services de démonstration et le VPS personnel du propriétaire sont extérieurs au déploiement de main.
- **Coûts** : aucun pour la démo Express ou la démo console ; modèles OpenAI facturés selon le compte et la charge réels. STT, réponse et TTS peuvent correspondre à plusieurs requêtes.

## 6. Tester, investiguer et étendre

1. `poetry run python -m compileall -q src main.py`.
2. `poetry run python -m unittest discover -s tests -v` ; sous Windows tester aussi `demo/express/Jade-Demo-Express.ps1 -SelfTest`.
3. `poetry run python main.py --preflight` et préflight par drapeau opt-in.
4. Tester séparément les permissions, périphériques audio, codecs et routes réseaux sur les vraies machines, avec accord du propriétaire.
5. Avant de changer le contrat `Incoming/Reply`, revoir tests et adaptateurs ; ne pas injecter de secret dans un nouveau log. Quand un module évolue, actualiser **tous les guides de ce dossier**, `AGENTS.md` et les tests selon le [contrat documentaire](AI_HANDOFF.md).

## 7. Modules spécifiques de cette branche

Les modules supplémentaires `src/jade_runtime/intent_engine.py` (parse/suppression du préfixe `[INTENT:...]`), `src/jade_runtime/pitch_shift.py` (transformation audio DSP sous condition de compatibilité FFmpeg) et `src/jade_runtime/turn_logging.py` (provenance et sorties de tours) sont présents sur ce tronc. En revanche, `src/jade_runtime/mobile_gateway.py`, `src/jade_runtime/memory_store.py`, `src/jade_runtime/turn_arbitration.py` et le launcher unifié **sont absents**. Le runtime traite les travaux selon une file FIFO, sans prise de priorité par support. Les guides de develop ne peuvent être copiés ici sans fausse information.

**Écart propre au code et documentation :** Branche de **cadrage mémoire persistante et identités** : ses 5 commits encore uniques face à develop portent principalement sur les documents PLAN-MEMOIRE-PERSISTANTE-IDENTITES-CORE-20261115.md, le journal et les instructions. **Aucune implémentation SQLite/Core Memories dans cette branche.** Le code vocal/intention/log est présent via les travaux antérieurs. Le plan n'est pas le produit. Avant suppression, comparer son contenu de cadrage avec les plans de develop et préserver toute décision non reprise.
