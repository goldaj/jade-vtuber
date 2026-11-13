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

## Revue de recul PO et technique (13 novembre, seconde passe)

### Décision de livraison

- **Parcours recommandé par défaut :** conserver le PCM progressif pour Discord avec JADE_AUDIO_OUTPUT=none. La réponse LLM complète reste produite en une seule requête, et un seul appel TTS est utilisé.
- **Parcours expérimental :** JADE_EARLY_VOICE=1 reste **désactivé**. Les segments vocaux sont désormais limités à six synthèses maximum par réponse, fin comprise. Plusieurs segments peuvent augmenter les frais et produire des jonctions sonores perceptibles ; le gain de latence doit être comparé au mode PCM simple avant activation.
- **Définition du terminé :** codes et tests hors ligne verts, PR lisible et fusionnable, sans mélange avec les changements locaux de Terra. **Ne signifie pas** audio sur téléphone validé ou déploiement terminé.

### Anomalies trouvées et corrigées

1. **Critique, interruption :** un stream LLM abandonné parce que la voix échoue ou qu'une session expire ne se fermait pas explicitement. Son générateur est maintenant fermé immédiatement pour éviter un flux réseau et des dépenses inutiles.
2. **Critique, nettoyage :** une annulation pendant la fermeture d'un flux pouvait éviter le rétablissement du gate micro, l'effacement des sous-titres ou la remise à zéro de l'état de lecture Discord. Nettoyage garanti par des finally imbriqués.
3. **Majeur, cohérence conversationnelle :** une réponse LLM streamée dont la connexion s'arrêtait sans signal terminal pouvait être considérée complète. Le marqueur finish_reason=stop est désormais obligatoire ; un arrêt length/refus n'est pas enregistré comme réponse normale.
4. **Majeur, ordonnanceur :** la chaîne vocale anticipée n'avait pas de délai global. Elle utilise maintenant une borne (20 à 180 s selon la configuration ; maximum 180 s) afin de ne pas immobiliser les messages suivants indéfiniment.
5. **Majeur, accusé Discord :** un tour pouvait être marqué « prononcé » avant la fin du nettoyage micro/OBS. L'accusé est émis seulement après le nettoyage réussi et un nouveau contrôle d'autorisation.
6. **PO, coûts :** le fractionnement naïf pouvait envoyer de nombreuses micro-phrases à OpenAI. Cap de six segments, conservation du reliquat, traitement spécifique de certaines abréviations françaises et nombres décimaux.
7. **UX, animation :** pendant un manque de trames fournisseur, la source Discord lisait des silences mais ne notifiait pas le modèle ; des niveaux de bouche non nuls pouvaient rester affichés. Les trames de silence informent désormais l'avatar d'un niveau zéro.

### Critères de recette à réaliser par Terra après merge

- Comparer **sur les mêmes phrases et dans les mêmes conditions Discord/téléphone** le temps fin de prise de parole → première trame audible, médiane et cas lent, entre le mode WAV historique, PCM progressif et mode anticipé par phrases. Ne pas annoncer de pourcentage tant que la mesure n'est pas faite.
- Vérifier une réponse simple et une réponse longue, interruptions « silence »/« reprends », perte réseau, sortie de canal et reconnexion, sans reprise de paroles déjà émises ni synthèse facturée en double.
- Pendant une pause audio, vérifier bouche fermée ; après arrêt, vérifier micro disponible, sous-titres vides et session prête à la réponse suivante.
- Comparer les **coûts API réels** par réponse complète. Le nombre d'appels TTS du mode anticipé n'est plus illimité mais peut rester supérieur au mode simple.
- Ne pas activer JADE_EARLY_VOICE dans la configuration partagée avant validation explicite des résultats ; conserver le retour instantané possible au mode simple via le drapeau.
- Relancer la CI sur le **commit de merge** plutôt que d'interpréter les checks de cette PR comme une recette de l'assemblage local de Terra.

## Revue complémentaire : qualité opérationnelle et observabilité (13 novembre)

### Décisions PO

- Le mode **PCM progressif sans fractionnement du texte** reste la valeur par défaut pour Discord : un appel TTS par réponse, compatibilité inchangée avec les sorties locales et les mocks.
- `JADE_EARLY_VOICE=1` reste une **expérimentation à activer manuellement**, et non un changement de production imposé. Jusqu'à six appels TTS par réponse peuvent augmenter le coût et introduire des pauses entre phrases.
- **Critère d'acceptation utilisateur** : Jade répond à une seule sollicitation sans doublon, reprend correctement après « silence »/« reprends », n'émet plus de son après un changement de canal, libère le micro et ferme la bouche à l'arrêt. Le temps perçu sur téléphone et le coût réel doivent être mesurés en situation, pas extrapolés de tests.

### Corrections techniques supplémentaires

1. **Mémoire et fluidité** : la conversion 24 kHz mono → 48 kHz stéréo traite désormais des tranches d'au plus 20 ms. Elle ne transforme plus un gros paquet complet en mémoire avant de pouvoir appliquer la backpressure Discord. Les entrées exceptionnellement longues cèdent régulièrement la main à la boucle asynchrone.
2. **Mesures vérifiables** : `OpenVoiceBridge.last_pcm_metrics` expose seulement des compteurs numériques de la **dernière lecture PCM de la session toujours valide** :
   - `first_nonzero_read_ms` : délai entre création du lecteur et première trame non nulle **consommée par le thread Discord** ;
   - `prebuffer_silence_frames` : trames de silence volontaires du prébuffer initial ;
   - `underrun_silence_frames` : trames de silence forcées faute de données après démarrage. Multiplier par 20 ms pour obtenir la durée de sous-alimentation ;
   - `max_queued_frames` : profondeur maximale observée de la file, bornée par sa configuration ;
   - `frames_read` : trames effectivement remises au lecteur, y compris les silences.
   Aucun texte, audio, identifiant de salon ou transcript n'est stocké dans ces statistiques. Elles sont effacées à la fermeture et ignorées après révocation ou déplacement de session.
3. **Résilience sans duplication facturable** : une connexion WebSocket Realtime devenue inactive peut être remplacée une fois **si le problème survient lors de la configuration avant `response.create`**. Aucune répétition de requête après `response.create`, quand le fournisseur a potentiellement déjà généré ou facturé de l'audio. Ce cas est couvert par un test hors ligne.
4. **Régression de transfert** : tests pour mémoire bornée sur bloc PCM volumineux, métriques prébuffer/sous-alimentation, connexion WebSocket inactive et impossibilité de réattribuer les métriques d'une session révoquée à une nouvelle session.

### Limites de l'observabilité

Les mesures internes ne disent **pas** quand le téléphone a effectivement rendu le son, ni quand l'utilisateur a fini de parler. Elles ne démontrent donc pas seules un gain sur le délai fin de parole → audition. Terra devra comparer à l'écoute et, si nécessaire, instrumenter aussi la chaîne STT/LLM de bout en bout. La qualité du rééchantillonnage linéaire, les pauses entre plusieurs appels TTS et la stabilité DAVE doivent être testées sur le matériel réel.

## Limites et risques

- Les queues bornées appliquent une backpressure au fournisseur. Le timeout de réception fournisseur est distinct du budget global qui autorise la backpressure normale ; confirmer les limites en conditions réelles.
- La conversion PCM est une interpolation linéaire pure Python : qualité audio à comparer en conditions réelles (notamment x1,5).
- Une erreur après les premières trames ne peut retirer les mots déjà entendus : aucune relance automatique ne doit les répéter.
- Les checks synthétiques ne certifient ni le transport DAVE réel ni la performance perçue sur téléphone.
- Aucun merge et aucun déploiement automatiques. Terra décide de l'intégration.

## Dernière revue de cohérence (13 novembre, reprise)

- **Métriques par session** : remise à zéro de `last_pcm_metrics` lors d'une révocation explicite de session et d'une rotation de canal. Le contrôle de génération à la fin d'une lecture reste en place ; ainsi l'ancienne session ne peut pas exposer ses mesures à la nouvelle.
- **Sous-titres OBS** : toutes les phrases du mode vocal anticipé sont maintenant publiées via un fichier temporaire puis un remplacement atomique, pas seulement la première. Le parcours PCM normal et le nettoyage final restent inchangés.
- **Régressions ciblées** : remplacement de session, déplacement de canal, et mise à jour complète du sous-titre pour chaque segment. Pas de nouveau drapeau ni dépendance externe.
- **Validation** : consulter les checks du dernier commit de la PR avant la fusion ; les validations hors ligne ne remplacent pas l'essai Discord sur téléphone.
