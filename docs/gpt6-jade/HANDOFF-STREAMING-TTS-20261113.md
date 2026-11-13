# Passation Terra : streaming audio Discord (13 novembre 2026)

## Périmètre et coordination

Base de départ : branche develop, SHA f1750f4da77fc8bdc0f7f85bd5bf5d7a55275b08.
Branche isolée : feat/tts-streaming-discord-parallel-20261113. Aucune écriture sur develop ou main.

Ce lot commence la diffusion audio Discord avant la fin du TTS Realtime, avec un tampon borné et un arrêt possible à tout moment. Le parcours normal utilise une seule synthèse pour la réponse complète ; le mode optionnel par phrases utilise une synthèse par phrase, avec un canal de lecture unique. Il ne modifie pas les travaux locaux de Terra et doit être intégré par lui. Les lots A/A bis (mesure, vitesse x1,5, voix Aube) restent sous sa responsabilité.

## Livré

1. src/jade_runtime/realtime_tts.py : RealtimeTTS.stream_pcm fournit un itérateur asynchrone PCM 24 kHz mono sur les événements response.output_audio.delta. Queue bornée, limites de taille, contrôle final du fournisseur et annulation sans relance. Les méthodes WAV restent compatibles.
2. src/jade_runtime/openai_services.py : stream_speech_pcm expose le flux uniquement pour les modèles Realtime ; les autres gardent l'ancien contrat.
3. src/jade_runtime/discord_pcm.py : conversion continue 24 kHz mono vers 48 kHz stéréo 16 bits, trames de 3 840 octets / 20 ms, source Discord synchrone alimentée par une queue thread-safe de 50 trames au maximum. Fin de flux et trou temporaire distincts ; aucune écriture de WAV sur disque ou nouveau service.
4. src/jade_runtime/discord_voice.py : consommation progressive, vérification de génération, session, canal et mute pendant l'attente de PCM, arrêt du lecteur en cas d'annulation, déconnexion ou erreur tardive. Chemins distincts réponse vocale / autre source.
5. src/jade_runtime/output.py : active ce flux quand le Discord vocal est présent, que le modèle est Realtime et que la sortie locale est none. Sinon, la synthèse et la lecture WAV originales restent actives. Les sous-titres sont toujours nettoyés.
6. src/jade_runtime/avatar.py : nouveaux événements pcm_start, pcm_level et pcm_end provenant des trames réellement consommées, sans anticiper l'audio non encore émis.
7. realtime_tts.py : RealtimeConnectionPool garde la connexion WebSocket après un tour réussi et la ferme après une erreur, annulation ou shutdown. OpenAIServices.close et main.py prennent en charge la fermeture dans l'ordre.
8. src/jade_runtime/sentence_stream.py, dialogue.py, early_speech.py, orchestrator.py et main.py : pipeline LLM par phrases facultatif, tampon de deux phrases, audio de la première avant la fin du texte complet, historique final écrit une fois, réponse texte publiée une seule fois. L'activer uniquement avec JADE_EARLY_VOICE=1 après essais réels ; valeur par défaut 0.
9. tests/test_jade_streaming_pcm.py et tests/test_jade_early_speech.py : tests synthétiques du transport, de la connexion conservée et de la première phrase avant la fin LLM.

## Contraintes inchangées

- STT et TTS OpenAI exclusivement ; aucun secret, identifiant, transcription ou enregistrement conservé.
- Pas de nouveau filtre Discord sur participants ou salons ; Jade ignore sa propre voix.
- Pour le téléphone, conserver JADE_AUDIO_OUTPUT=none. Le chemin progressif n'ajoute pas une seconde synthèse.
- La démo Windows, la sortie locale et la diffusion double restent en mode WAV.
- Aucune preuve d'écoute, de gain réel de latence, de mouvement réel ni d'appel API effectué dans cette branche. Les tests CI peuvent vérifier des contrats synthétiques uniquement.

## Preuves de CI déjà observées (code applicatif)

Sur le commit applicatif `8343b64dda09ffc46f68efdcbdc776172a80bf77` :
- GitHub Actions « Jade rebuild offline tests » : Windows **success** et Ubuntu **success** ;
- 347 tests de la suite Linux, 2 ignorés ; tests du streaming et du mode phrases réussis ;
- scan de secrets (history) **success** ;
- contrôle d'hygiène de publication (hygiene) **success**.

Ces résultats prouvent la compilation et les scénarios logiciels hors ligne, **pas** la qualité audio, la latence perçue, l'écoute sur téléphone ni le coût réel. Après ce commit documentaire et, surtout, après le merge avec les travaux locaux de Terra, lire la CI de **la nouvelle tête**, et ne pas réutiliser cette preuve comme résultat du merge.

## Validation à effectuer sur la branche et après merge

    python -m unittest tests.test_jade_streaming_pcm -v
    python -m unittest tests.test_jade_early_speech -v
    python -m unittest discover -s tests -v
    python -m compileall -q src main.py

Consulter les contrôles CI associés au SHA final, et non les anciens résultats de develop.

## À reprendre par Terra, par priorité

1. Résoudre les éventuels conflits entre le paramétrage x1,5 / voix du lot A bis et les modifications dans realtime_tts.py et openai_services.py, sans ouvrir deux connexions ni doubler les frais.
2. Vérifier la compatibilité du merge sur son Windows/Python 3.11 et exécuter les tests réels convenus avec le propriétaire : première syllabe, fin de réponse, silence, reprends, changement de canal, reconnexion et synchronisation bouche.
3. Comparer la latence fin de parole → premier PCM Discord avant/après avec quelques mêmes phrases, distinguer sortie vers Discord de l'audition réelle sur téléphone et mesurer les trous de lecture ; ajuster si nécessaire le prébuffer de 5 trames (100 ms) et file maximale de 50 trames et les délais.
4. Lot D implémenté sous drapeau expérimental JADE_EARLY_VOICE=1, désactivé par défaut : recetter le début audio avant texte final, la cohérence des sous-titres, les voix entre phrases, le surcoût de plusieurs synthèses et les paroles interrompues. Ne l'activer en pratique qu'après validation réelle. Les autres sources et HTTP gardent l'ancien parcours.
5. Lot E après mesures : éventuel seuil de silence plus court et réponses orales plus brèves. La connexion Realtime est déjà réutilisée entre tours ; contrôler sa tenue en cas de coupure réseau.

## Préparation du merge (qualité du diff)

Les fins de ligne CRLF des fichiers existants ont été restaurées dans un commit de finition pour limiter les conflits et les changements purement cosmétiques. Comparaison directe de cette branche avec develop : aucun commit à récupérer depuis develop au contrôle, PR fusionnable dans son état GitHub du 13 novembre. Cette information peut changer si Terra pousse de nouveaux commits sur develop. Les sources Jade, les modèles et les assets LFS restent intacts.

## Limites et risques

- Les queues bornées appliquent une backpressure au fournisseur. Le timeout de réception fournisseur est distinct du budget global qui autorise la backpressure normale ; confirmer les limites en conditions réelles.
- La conversion PCM est une interpolation linéaire pure Python : qualité audio à comparer en conditions réelles (notamment x1,5).
- Une erreur après les premières trames ne peut retirer les mots déjà entendus : aucune relance automatique ne doit les répéter.
- Les checks synthétiques ne certifient ni le transport DAVE réel ni la performance perçue sur téléphone.
- Aucun merge et aucun déploiement automatiques. Terra décide de l'intégration.
