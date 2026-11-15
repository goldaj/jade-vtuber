# Pour Codex uniquement : conversation Discord unifiée, voix + écrit simultanés

**15 novembre 2026. Idée fonctionnelle demandée par le propriétaire : DOCUMENTATION UNIQUEMENT dans la présente PR. Ne pas implémenter dans le lot SQLite.**

## Demande utilisateur

Jade doit pouvoir se rendre compte, à partir de l'identité et de l'horodatage/contexte, qu'elle entretient **une seule conversation avec la même personne sur Discord**, même si cette personne parle dans un salon vocal **et écrit simultanément** dans un salon texte. Le changement de canal d'entrée ne doit pas créer artificiellement deux discussions indépendantes.

### Scénario précis

À 14 h 00, Alice parle à Jade dans un vocal Discord et demande de l'aide pour un roman. À 14 h 01, Alice écrit dans le salon texte associé « Je t'envoie le titre dans ce message ». À 14 h 02, elle poursuit oralement. Jade doit pouvoir comprendre que l'écrit précise **la même conversation**, garder le fil, et répondre par le média pertinent, sans agir comme si l'écrit venait d'une inconnue.

**Attention :** même `discord_user_id` ne signifie pas automatiquement même conversation. Une même personne peut être en vocal public et écrire un DM privé, ou discuter de sujets indépendants ; les périmètres et permissions doivent primer.

## État actuellement disponible

- `Incoming.account_id` dans le texte Discord et `Incoming.speaker_id` dans le vocal désignent le même compte Discord lorsqu'ils sont identiques ; la nouvelle mémoire SQLite sait résoudre cette identité.
- `Incoming.session` reste indexée par `(platform, channel)`, et l'audio ajoute son `voice_session_id` éphémère. Donc `Dialogue.history` **ne partage pas encore les tours** entre Discord écrit et vocal.
- Le nouveau `MemoryStore` persiste les souvenirs par **scope du salon** pour limiter les fuites ; cette persistance n'est pas une timeline temps réel fusionnée.
- `jade.conversation` produit déjà des logs d'entrée/sortie corrélés par tour ; ce journal n'est ni une base de mémoire ni une source d'autorisation.

## Proposition Codex (à développer dans un futur lot)

1. Introduire un **ConversationManager** séparé des connecteurs, recevant des événements déjà identifiés, après les autorisations. Chaque événement contient : `event_id`, `person_id` issu de l'identité de transport, `discord_account_id`, `server_id`, `channel_id`, `message_id`, `modality=text|voice`, `event_at_utc`, `received_at_monotonic`, `voice_session_id` (contrôle d'autorisation uniquement), `conversation_id` si déjà connu, `message_text` et `turn_status`. Ne pas conserver de son PCM.
2. Donner à chaque **conversation logique** un `conversation_id` propre, indépendant de Discord texte et vocal. Fusionner dans une même timeline si **même compte, même périmètre autorisé, continuité temporelle et sémantique de l'échange**, ou association explicite texte-vocal (par ex. salon texte lié au vocal). Lier les salons à une conversation active seulement si le contexte est réellement partagé.
3. Le timestamp UTC permet l'ordre intercanal et la reprise ; l'horloge monotone permet les calculs de durée sur un processus. Les événements simultanés doivent garder leur ordre d'arrivée et leur identifiant, avec tolérance au délai STT : un texte envoyé pendant qu'une phrase audio attend sa transcription peut être affiché avant la phrase prononcée. Ne pas réordonner silencieusement une réponse déjà diffusée.
4. Mettre en place une **fenêtre de conversation active** courte (durée à mesurer avec l'utilisateur) ; clôturer ou scinder si le sujet, l'environnement ou la confidentialité changent. Une nouvelle session vocale peut reprendre une conversation logique **seulement** si l'identité et le contexte sont autorisés ; une session révoquée ne redevient jamais autorisée par la mémoire.
5. Aligner `Dialogue.history` et les résumés de session sur `conversation_id` plutôt que directement `platform/channel`, mais **ne pas changer brutalement `Incoming.session`** : elle est aussi utilisée pour la sécurité, la déduplication et le cycle de vie du vocal. Prévoir des identifiants distincts `transport_session_id`, `conversation_id`, `person_id`, `source_message_id`.
6. Conserver la capacité de répondre **oralement ou par écrit ou les deux**, indépendamment du média de la dernière entrée. Empêcher les doubles réponses lorsque le même propos est répété de la voix au texte, lors du streaming, et en présence de messages simultanés.
7. Retirer toute mémoire de session concernée quand le contexte vocal est révoqué si elle contient une transcription qui ne devait pas être réutilisée. Ne jamais exporter un DM privé vers un vocal public sous prétexte que le propriétaire du compte est identique.
8. La **mémoire durable** conserve l'origine, la date, la personne et le contexte ; une conversation active unifiée n'implique pas que tous ses messages doivent devenir des souvenirs durables. Les Core Memories restent choisies par Jade selon le mécanisme de curation défini ailleurs.

## Tests de recette nécessaires

- Même compte Alice, même serveur/sujet, **vocal A → texte A → vocal A** : Jade relie les trois tours et sait citer le titre envoyé par écrit sans répéter les questions.
- Même compte mais **DM privé + salon vocal public** : aucun détail du DM ne fuit dans le vocal.
- Alice parle tandis que Bob écrit dans le même salon : aucun mélange d'identités.
- Alice change de pseudo en pleine conversation : l'identifiant stable permet la continuité.
- Deux messages avec délais STT inversés et micro-interruption : l'ordre réel est conservé ou correctement signalé, aucune double réponse.
- Reconnexion Discord/DAVE, changement de salon vocal, nouvelle `voice_session_id`, déconnexion : pas de réactivation d'écoute et pas d'historique d'un salon non autorisé.
- Conversation intercanal de plusieurs heures et redémarrage : séparation de session active et de souvenirs durables, sans injection incontrôlée de centaines de messages.
- Vérifier latence du premier son, consommation de tokens,  absence de fusion intempestive de sujets.

## Ordre de reprise par Codex

**Ne pas commencer cette fonctionnalité avant d'avoir validé le moteur SQLite et le routage d'identité.** Lire d'abord [HANDOFF-CODEX-MEMORY-20261115.md](HANDOFF-CODEX-MEMORY-20261115.md), puis les contrats `messages.py`, `dialogue.py`, `discord_text.py`, `discord_voice.py`, `orchestrator.py`, `memory_service.py` et `memory_store.py`. Préserver les branches de Terra/Codex et choisir une branche dédiée pour ce lot. L'horodatage seul ne suffit pas : l'identité, le contexte et la confidentialité décident de la corrélation.

**Statut : à concevoir et développer par Codex ; aucune unification Discord écrit/vocal implémentée ici.**
