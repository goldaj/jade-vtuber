# Guide utilisateur complet : branche feat/turn-conversation-logs-20261115

**Branche divergente : feat/turn-conversation-logs-20261115.** Journalisation des tours de conversation (messages, intentions et modalités de réponse), avec module turn_logging.py, adaptation de l'orchestrateur et tests de journalisation. Les dix commits propres recensés face à develop demandent une revue de contenu avant suppression. Pas de PWA mobile, de mémoire SQLite ou de launcher unifié. Les guides sont spécifiques à cette branche et ne doivent pas être confondus avec ceux de develop.

**Important :** seules les possibilités présentes dans le code de **feat/turn-conversation-logs-20261115** sont décrites ici. Les commandes de `develop`, sa PWA et sa mémoire persistante ne s'appliquent pas. Avant le premier usage, suivre [INSTALLATION.md](INSTALLATION.md). Une fonction externe est opt-in : elle n'est ni ouverte ni connectée par défaut.

## 1. Découvrir Jade sans connexion ni installation lourde

- Sous Windows, double-cliquer `Installer-Demo-Express.cmd`, puis ouvrir « Jade Demo Express » dans le menu Démarrer : portrait stylisé et répliques pré-écrites, totalement hors ligne. Voir [DEMO.md](DEMO.md).
- Pour essayer le *vrai moteur* avec dialogue simulé : `poetry run python main.py`, écrire un message et sortir par `/exit`. Les réponses portent « Mode démo » et sont générées localement, sans IA.

## 2. Discuter avec Jade en console via l'API OpenAI

**Prérequis :** `OPENAI_API_KEY` dans un fichier privé, `JADE_SECRETS_FILE` pointant vers ce fichier, internet et compte API avec crédit. `poetry run python main.py --preflight --live`, puis `poetry run python main.py --live`. Saisir un texte puis Entrée ; `/exit` ou `/quit` pour quitter. Un abonnement ChatGPT ne remplace pas un budget d'API.

**Comportement :** contexte tenu par session en mémoire du processus ; la console ne conserve pas une mémoire durable entre démarrages sur main. Les modèles sont paramétrés par `JADE_LLM_MODEL`, `JADE_STT_MODEL`, `JADE_TTS_MODEL`. Leur disponibilité réelle et leur tarification peuvent changer : le préflight ne valide pas l'accès distant à ces modèles.

## 3. Personnalité, réponses et sessions

La personnalité est chargée par `src/jade_runtime/assets.py`, depuis les fichiers de prompt autorisés. Les profils publics sont sous `config/profiles/` ; les paramètres privés peuvent prendre le dessus. Jade filtre les messages qu'elle doit traiter : demande forcée, préfixes `!response` / `!rsp`, mention du nom du bot ou réponse aléatoire si `JADE_RANDOM_REPLY_RATE` est supérieur à zéro. Par défaut, le taux aléatoire global du moteur est nul ; les politiques propres aux plateformes peuvent ajouter un comportement spécifique. Les conversations sont isolées selon leur session/salon et stockées **temporairement en RAM**, pas dans une base persistante.

## 4. Lire et répondre sur Discord écrit

**Prérequis :** bot Discord créé, token `DISCORD_TOKEN`, permissions suffisantes et extras `-E discord` ; démarrage `poetry run python main.py --live --discord`. Les événements de salons accessibles et les messages privés pris en charge sont transformés en `Incoming` ; le moteur décide si Jade répond. La participation automatique texte est réglable par `JADE_DISCORD_TEXT_AUTO_RATE` (base 30 %) et `JADE_DISCORD_TEXT_COOLDOWN_SECONDS` (base 180 s). La réponse est adressée au canal de la demande. Ne pas publier de jeton bot, ni faire entrer le bot dans un serveur sans autorisation. Contrôler intents/permissions réels dans Discord avant de conclure que cela fonctionne.

## 5. Recevoir la voix sur Discord et répondre oralement

**Prérequis :** Discord configuré, salon vocal numérique `DISCORD_VOICE_CHANNEL`, permissions de rejoindre/parler, dépendances `-E discord-voice`, FFmpeg, compte OpenAI actif. Contrôle : `poetry run python main.py --preflight --live --discord --voice --discord-voice`. Exécution : mêmes drapeaux sans `--preflight`. L'application utilise le codec/transport Discord et la transcription OpenAI. La politique de session, les membres présents et la déconnexion sont à vérifier sur le serveur réel. Une mauvaise configuration, DAVE incompatible ou un changement de salon peut interrompre la réception. Les échanges audibles et transcriptions de tiers nécessitent leur information/consentement adapté.

## 6. Lire et répondre dans un chat Twitch

Configurer `JADE_TWITCH_ENABLED=1`, `TWITCH_TOKEN` et `TWITCH_CHANNEL`; `TWITCH_BOT_LOGIN` peut être indiqué explicitement. L'envoi des réponses nécessite en plus `JADE_TWITCH_SEND=1`. Exécuter `poetry run python main.py --preflight --live --twitch`, puis retirer `--preflight`. Le transport est IRC/TLS, les événements textuels sont filtrés, le rythme de sortie est limité par le code. Pour rotation OAuth, consulter `docs/gpt6-jade/TWITCH-AUTH.md`. Ne pas traiter un jeton expiré comme un problème du dialogue.

## 7. Parler depuis le microphone Windows

Installer `-E mic`, autoriser l'accès au micro du système, fournir une clé OpenAI et un périphérique de capture. `poetry run python main.py --live --mic` démarre l'écoute ; l'audio qualifié est transmis au STT puis au dialogue. La démo Express n'ouvre jamais le micro. Les caractéristiques de capture (détection de voix, durée et seuils) sont dans `microphone.py` et `voice_pipeline.py` ; contrôler les retours d'écho et les appels API réels avant usage prolongé. Avec le paramètre `--voice`, configurer également `JADE_AUDIO_OUTPUT=ffplay` et le lecteur adéquat.

## 8. Entendre la synthèse vocale et afficher les sous-titres OBS

`--voice` active la synthèse OpenAI ; `JADE_AUDIO_OUTPUT=ffplay` dirige la lecture locale (ou le système Discord vocal utilise son pont). La voix, la vitesse, le modèle se règlent par `JADE_TTS_VOICE`, `JADE_TTS_SPEED` et `JADE_TTS_MODEL` (valeurs de cette branche vérifiables dans `config.py`). La piste sonore est envoyée au lecteur configuré, non à tous les canaux de manière garantie. `JADE_SUBTITLE_PATH` définit un fichier de sous-titres utilisé par OBS (lecture d'un fichier texte) ; il doit être inscriptible et peut contenir temporairement des paroles. Vérifier la confidentialité avant une diffusion publique. Les erreurs STT/TTS peuvent coûter des requêtes déjà commencées.

## 9. Avatar Live2D local autonome

`--avatar` démarre le processus d'avatar via `src/jade_runtime/avatar.py` et le modèle r20. Installer les extras `-E avatar`, effectuer `git lfs pull`, vérifier `poetry run python jade-modeling/verify_assets.py` et le pilote OpenGL. Le composant reçoit des observations de lecture audio pour les mouvements. Il est séparé de la **Démo Express**, qui n'utilise pas Live2D, et du modèle r21 encore en travail. La présence des fichiers et l'import Python ne prouvent pas le rendu réel à l'écran.

## 10. Relier VTube Studio

`--vts` parle à l'API WebSocket **locale** de VTube Studio. Le logiciel doit être installé et démarré séparément avec son API activée. Configurer `JADE_VTS_ENABLED=1`, `JADE_VTS_TOKEN`, facultativement `JADE_VTS_URL` (par défaut loopback) et `JADE_VTS_SPEAK_HOTKEY`. L'extra `-E vts` apporte WebSocket. On peut utiliser l'avatar r20 autonome sans VTube Studio. Ne pas publier le token VTS ni changer le bind vers internet.

## 11. Interface Web/API locale texte

`--http` active un serveur **loopback seulement** sur `127.0.0.1:8765` par défaut. Configurer `JADE_HTTP_ENABLED=1`, un `JADE_HTTP_TOKEN` indépendant de **32 caractères minimum**, et éventuellement `JADE_HTTP_PORT`. Démarrer avec `poetry run python main.py --live --http`. Ouvrir la page locale sur le **PC** : elle possède un champ jeton privé en mémoire de session du navigateur, et envoie `POST /message` avec un JSON `text` / `session` et un en-tête `Authorization: Bearer`. Aucun token n'est placé en cookie ni dans localStorage. Pour accéder depuis un téléphone, un accès sécurisé supplémentaire est indispensable, mais ce n'est **pas** la PWA moderne de `develop`.

## 12. Diagnostic, changement de paramètres et reprise

- Toujours commencer par `poetry run python main.py --preflight` suivi, si nécessaire, des drapeaux activés. Aucun appel de fournisseur n'est effectué par le préflight.
- Contrôler `JADE_SECRETS_FILE` et les variables de l'environnement du processus qui prennent priorité sur le fichier privé.
- Installer un extra Poetry manquant ; ne pas désactiver silencieusement la sécurité d'un connecteur pour masquer une erreur.
- À l'arrêt, vérifier que les tâches Discord/Twitch/audio se terminent ; le runtime impose une borne temporelle. Les messages encore en file peuvent être annulés.
- Les tests automatiques ne valident pas le réseau et les périphériques physiques. En cas de problème, relever l'étape, l'heure, le message d'erreur **sans token** et consulter [TECHNICAL.md](TECHNICAL.md).

## Moteur d'intentions vocales et logs structurés dans cette branche

Ce tronc contient aussi `intent_engine.py` et `pitch_shift.py` : le préfixe `[INTENT:label]` est interprété puis supprimé du texte présenté, et le pitch audio DSP exige des dépendances compatibles. `turn_logging.py` journalise les informations techniques de provenance/traitement ; ces journaux ne sont **pas** une base de mémoire personnelle, et les données privées doivent rester privées. Voir `docs/gpt6-jade/CONVERSATION-LOGS-20261115.md`. Cette branche utilise les flags CLI séparés, une file FIFO et **n'a pas `--all-channels`**.
