# Journalisation de diagnostic par session de Jade

## Emplacement et cycle de vie

Au lancement de Jade depuis PyCharm ou le terminal, elle crée automatiquement un fichier unique dans :

    <racine-du-projet>/logs/sessions/jade_YYYY-MM-DD_HH-MM-SS_microsecondes+fuseau_pid-XXXX.log

Chaque redémarrage du processus Python crée un nouveau fichier, sans modifier les précédents. Le chemin exact s'affiche au démarrage dans la console de PyCharm (événement session_started). Le répertoire est ignoré par Git via la règle existante logs/*.

Les anciens fichiers restent disponibles pour diagnostic. Ils ne sont ni supprimés ni tronqués au redémarrage. Les traces complètes pouvant être volumineuses, surveiller occasionnellement la taille du dossier.

## Deux niveaux de visibilité

**Console IDE (synthétique, en direct)** :
- démarrage du processus et configuration non secrète ;
- input_selected : numéro de tour, plateforme (discord, discord_voice, twitch, mobile, microphone, local_http, console) et médium (text/voice) ;
- reply_planned : destinations et médias prévus, intention sans contenu privé ;
- delivery_outcome : transfert réussi vers le connecteur ou échec ; ce n'est pas la confirmation qu'un destinataire a entendu ou lu ;
- turn_outcome, avertissements, erreurs et tracebacks Python complets ;
- rec006_pcm_progress : à chaque tentative de lecture PCM Discord, `first_pcm_ms` (première trame non silencieuse consommée par le lecteur), `tts_completed_ms` (réponse TTS validée), `pcm_before_tts_complete` (booléen ou null), `playback_completed` et `verdict`.

**Fichier de session (détaillé, local)** :
- toutes les traces précédentes, horodatées ;
- contenu des messages entrants, dont les transcriptions vocales autorisées ;
- discord_transport_input et discord_policy_decision : messages Discord reçus, y compris ceux non retenus pour une réponse ;
- requêtes OpenAI avec modèle et activation des outils, réponses brutes et intentions avant/après parsing ;
- llm_raw et llm_parsed ; fragments partiels disponibles lors d'une erreur de streaming, appels et résultats d'outils de mémoire ;
- destinations textuelles ou vocales prévues, résultats de transfert ;
- transactions sqlite_commit et sqlite_rollback : table, opération et nombre total de lignes modifiées, sans SQL développé ni paramètres ;
- opérations de mémorisation (memory_write, memory_batch_write, conversation_saved) ;
- WARNING, ERROR, exceptions et avertissements des bibliothèques.

Les événements structurés sont des objets JSON sur une ligne, précédés de l'horodatage et du niveau de log. Filtrer par turn permet de reconstituer un échange.

## Dépannage d'un échec conversationnel

1. Relancer Jade après git pull origin develop.
2. Lire session_started pour identifier le nouveau fichier.
3. Reproduire un seul échec depuis le canal concerné.
4. Repérer input_selected dans la console et noter le numéro de tour.
5. Chercher ce tour dans le fichier, puis inspecter memory_start, memory_end, llm_request, openai_request, openai_response ou l'exception complète.
6. Différencier reply_planned (réponse prévue), handoff_completed (connecteur appelé sans erreur) et confirmation de réception réelle, que seul le service distant peut garantir.

Si !jade-memoire etat fonctionne mais qu'un message normal échoue, regarder en priorité l'appel chat.complete_with_tools ou chat.stream_with_tools.

## Confidentialité

Les logs détaillés contiennent intentionnellement des paroles et échanges privés. **Ils doivent rester sur une machine privée et ne pas être publiés tels quels.** Les clés OpenAI au format sk-..., les jetons GitHub connus, les en-têtes Bearer et quelques secrets courants sont masqués par une protection best effort, qui n'est pas un anonymiseur exhaustif.

Les opérations SQLite sont tracées **sans la requête SQL avec ses paramètres** pour éviter de dupliquer les secrets de la base. Les textes de conversation et résumés de souvenirs présents dans le journal détaillé restent potentiellement sensibles. Vérifier les extraits avant tout partage.

Aucune capture audio WAV/PCM brute n'est écrite dans ces journaux ; seules les transcriptions textuelles disponibles le sont.

## Limites

- Les logs naissent au démarrage de la nouvelle version du code. Ils ne peuvent expliquer les sessions précédentes.
- Une interruption brutale du système peut empêcher l'écriture des dernières lignes.
- handoff_completed ne vaut pas accusé de lecture ni lecture audio confirmée.
- `rec006_pcm_progress` utilise le temps monotone depuis le lancement du lecteur PCM Discord, **pas** depuis le début de la question. `progressive_confirmed` signifie que le lecteur a consommé une première trame sonore avant la fin du TTS validé, et que la lecture s'est terminée normalement ; ce n'est pas une preuve que le destinataire Discord l'a entendue. `no_overlap_observed` ne prouve pas à lui seul une panne du streaming, et `inconclusive` signale une mesure manquante (erreur, interruption, autre adaptateur TTS). Les durées sont en millisecondes. Ce diagnostic n'ajoute aucun appel API.
- Les écritures couvertes sont celles de MemoryStore et des réservations de CostGuard. Les autres connexions SQLite ajoutées ultérieurement devront être instrumentées à leur tour.
- Les exceptions TTS/STT/réseau remontées sont journalisées, mais les requêtes réseau complètes et flux audio ne sont pas enregistrés.
