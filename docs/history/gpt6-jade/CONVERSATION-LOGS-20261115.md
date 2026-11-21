# Logs de conversation Jade (15 novembre 2026)

## Fonctionnement

Le nouveau module src/jade_runtime/turn_logging.py enregistre des événements JSON dans le journal local jade.conversation (niveau INFO, stderr). Un entier turn commun corrèle chaque tentative.

**input_selected** enregistre le texte reçu ou sa transcription STT, la plateforme source (twitch, discord, discord_voice, microphone, local_http, console), la modalité text/voice, le salon, l'auteur et l'identifiant du message.

**reply_planned** enregistre la réponse préparée en réintroduisant **uniquement dans le log** son intention canonique sous la forme [INTENT:curious] Bonjour !, le label intent, les modalités prévues text/voice et les destinations prévues (discord_text, twitch_text, local_http_text, local_audio, discord_voice, console_text).

**turn_outcome** avec no_reply, failed ou cancelled rend visibles les tentatives non abouties.

Le journal de sortie porte delivery_status=planned_not_confirmed. Il ne garantit PAS que Discord, Twitch ou le haut-parleur ait effectivement reçu la réponse. Une réponse peut échouer après sa génération.

## Périmètre et règles

- Le log entrant concerne les messages sélectionnés pour la file Runtime. Les messages Discord simplement observés sans sélection préalable ne sont pas enregistrés. Runtime peut encore décider de ne pas répondre.
- La balise d'intention est reconstruite à partir de Reply.intent après le parsing du modèle : ce n'est pas une copie exacte du payload brut. Le texte envoyé sur les réseaux, à OBS ou au TTS reste dépourvu de cette balise.
- Les logs sont locaux, leur destination de stockage dépend de la redirection stderr du processus. Ils contiennent des textes potentiellement privés et des transcriptions, mais jamais le son PCM/WAV. Ne pas pousser de logs réels dans GitHub, des artefacts CI ou un canal public.
- Aucun redémarrage du processus Jade sur le PC n'a lieu simplement en fusionnant le code.

## Exemple fictif

~~~json
{"event":"input_selected","turn":9,"source_platform":"discord_voice","source_modality":"voice","source_channel":"123","source_author":"Invité","source_message_id":"abc","input_text":"Jade, tu en penses quoi ?"}
{"event":"reply_planned","turn":9,"reply_with_intent":"[INTENT:curious] Ça dépend de ton objectif.","intent":"curious","output_modalities":["voice"],"output_destinations":["discord_voice"],"delivery_status":"planned_not_confirmed"}
~~~

## Validation

Tests ciblés : python -m unittest tests.test_jade_turn_logging -v. Contrôles globaux : python -m unittest discover -s tests -v et python -m compileall -q src main.py. Aucun appel payant ni test réel du microphone, de Discord ou de Twitch n'est requis pour la CI.

## Contrat d'intention commun à toutes les plateformes

Le modèle reçoit le même `INTENT_PROMPT` dans `Dialogue.respond`, quelle que soit l'origine : Twitch, Discord texte, Discord vocal, microphone, HTTP local ou console. Chaque réponse passe par le parseur commun et expose `Reply.intent` ainsi qu'un `Reply.text` débarrassé des balises. Le logger `jade.conversation` reconstruit la balise canonique pour **toutes** les réponses préparées, pas uniquement celles provenant de Discord. Lorsqu'un fournisseur omet malgré tout le préfixe exigé, l'intention devient `neutral` plutôt que de laisser fuiter une balise dans la sortie.

Les tests `test_intent_contract_and_logs_apply_to_every_entry_platform` et `test_missing_intent_tag_gets_neutral_metadata_even_for_twitch` protègent explicitement ce comportement multicanal. La présence de l'intention dans les logs n'implique pas une voix audible : un message Twitch peut rester uniquement écrit si le TTS n'est pas activé.

## Risque opérationnel à traiter (15/11/2026)

L'audit [DevOps develop](AUDIT-DEVOPS-DEVELOP-20261115.md) confirme que stderr contient les textes, auteurs, IDs et transcriptions sélectionnés lorsque la journalisation INFO est active. Les logs sont demandés pour diagnostiquer l'activité de Jade : ne pas les supprimer sans décision produit. Codex devra définir rotation, emplacement local hors dépôt, ACL Windows, durée de conservation, effacement et version expurgée avant partage de diagnostics. La CI utilise des valeurs de tests ; **ne jamais** télécharger/upload des journaux de conversations réelles comme artefacts publics.
