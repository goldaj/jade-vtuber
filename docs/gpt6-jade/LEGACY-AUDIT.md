# Inventaire des modules hérités supprimés

Refonte isolée `codex/chat-gpt6-jade-rebuild` (24 octobre 2026).
Sources d'origine conservées dans l'historique Git, **non nettoyé pour publication**.

## Modules abandonnés (aucun effacement d'assets)
- `src/queue_consumer.py`, `src/bot.py` : architecture à threads et ancienne
  gestion de conversation ; remplaçants `jade_runtime/orchestrator.py` et
  `jade_runtime/dialogue.py`.
- `src/text_completion_openai.py` : client synchrone héritage, arrêt forcé ;
  remplacé par `jade_runtime/openai_services.py`.
- `src/texttospeech_elevenlabs.py` : **ElevenLabs supprimé**.
  Nouveau TTS **OpenAI uniquement**.
- `src/speechtotext_openai.py`, `src/audio_recorders.py` :
  parcours obsolètes, SpeechRecognition/audioop/hypothèses Discord incompatibles ;
  nouveau STT **OpenAI uniquement**, capture PCM via `microphone.py` et
  `discord_voice.py`.
- `src/generate_subtitle.py`, `src/play_audio.py` :
  anciennes sorties audio/OBS racy ; nouveau `jade_runtime/output.py`.
- `src/discord/discord_connection.py`, `discord_recorder.py` :
  recorder Opus/ffmpeg et class mix obsolètes ; nouveau client discord.py
  texte + transport PCM opt-in séparé.
- `src/filter_message.py` : nltk.download au runtime, non intégré.
- `src/utility/chattypes.py`, `enums.py`, `json_handler.py`,
  `logger.py`, `utils.py` : abstractions uniquement utilisées par
  le vieux runtime ; remplacées par dataclasses/logging standard.

## Conservés volontairement
- `src/utility/private_config.py`, `credentials.py`,
  `src/twitch/twitch_auth.py` : stockage privé et outil OAuth historique
  encore testé ; pas d'API payante pour OAuth. Revue d'auth avant usage live.
- `jade-modeling/**`, Git LFS, scripts Cubism, manifestes et rapports :
  **aucun changement**, importance supérieure à un nettoyage cosmétique.
- `prompt_chat.txt` : réécrit sans fausse référence à ElevenLabs et sans
  prétendre que les vieilles fonctionnalités sont actives.

## Limites
La réussite des tests ne certifie pas les comptes/permissions de Twitch,
Discord, OpenAI ou VTube Studio, ni la génération phonétique ou la latence.
La disparition d'ElevenLabs du code courant ne supprime pas les anciens secrets
de l'historique Git.
