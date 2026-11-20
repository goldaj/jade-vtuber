# Latence, capture vocale et synthèse progressive

**Objectif produit :** temps de réaction court et régulier, sans déguiser un délai de réflexion par une phrase de remplissage. Aucune cible chiffrée n'est encore démontrée sur le PC de Jade.

| ID | Priorité / état | Amélioration proposée / condition de réussite |
| --- | --- | --- |
| LAT-01 | P0 / C | **Profiler tout le tour de bout en bout** : fin réelle de parole, VAD, début/fin STT, mémoire, file, IA, premier token, première trame TTS, premier son entendu et fin audio. Collecter médiane, p95, coût et durée, séparément pour Discord/PC/mobile. Pas de texte privé dans télémétrie exportable. |
| LAT-02 | P1 / E | Remplacer les seuils Discord actuels (~500 ms et seuil d’énergie relatif) par un **VAD plus adaptatif** si la recette le justifie ; mesurer les compromis, sans couper les hésitations et phrases françaises. |
| LAT-03 | P1 / E | Abandonner la capture micro PC en fenêtres fixes d'environ 3 s au profit d'un VAD local qui déclenche STT dès la fin de la phrase ; préserver anti-écho et refus des bruits. |
| LAT-04 | P2 / P | Essayer le **STT incrémental / streaming audio** pour préparer une réponse avant fin d'enregistrement ; gérer hypothèses de transcription révisées et conflits d'identité. |
| LAT-05 | P1 / E | **Connexion Realtime partagée** : le pool est maintenant injecté dans la synthèse tamponnée (DEV-007) ; mesurer le bénéfice de reconnexion sur le PC. |
| LAT-06 | P1 / E | Généraliser la **lecture PCM progressive** là où la destination l'autorise : le chemin Discord est déjà raccordé sous conditions, y compris avec `--all-channels` et `ffplay` réservé au micro PC. Mesurer le gain réel, les modes dégradés, l'annulation et la part des réponses qui repassent en WAV tamponné. |
| LAT-07 | P2 / E | Étendre le **premier segment de texte → TTS avant fin du LLM** ; code early voice déjà présent et désormais éligible sur Discord dans `--all-channels`, mais opt-in et à mesurer sur le PC. Début de phrase fiable, prosodie, limites de nombre de synthèses, annulation et coûts à comparer. |
| LAT-08 | P2 / P | Fan-out PCM unique **uniquement vers les sorties autorisées** (pas de broadcast automatique), bouche et sous-titres synchronisés sur les trames consommées ; éviter WAV intégral/temporaire et démarrages ffplay/FFmpeg par réponse. |
| LAT-09 | P1 / E | Hotkey VTS désormais asynchrone (DEV-006) ; évaluer les autres sorties facultatives à partir des mesures réelles. |
| LAT-10 | P1 / E | Harmoniser les **deadlines TTS** entre API audio, synthèse Realtime, streaming, lecture et annulation. Le délai général de l'API est configurable (défaut `JADE_API_TIMEOUT=20 s`) et ne correspond pas aux autres délais de livraison ; vérifier les valeurs effectives dans le code et la configuration du poste, plutôt que reprendre un ancien chiffre de timeout. |
| LAT-11 | P1 / P | Garder à chaud les sessions/connecteurs nécessaires à un tour probable, avec bornes de coût et fermeture en inactivité ; comparer froid/chaud sans payer silencieusement 24 h/24. |
| LAT-13 | P2 / P | Mettre en concurrence non bloquante les lectures mémoire et reconstitutions d'historique quand l'identité et les scopes le permettent ; benchmark : gains potentiellement petits, ne pas surarchitecturer. |
| LAT-14 | P2 / P | Cache de préfixe de prompt et de contexte stable, prompts compacts ; ne pas envoyer systématiquement 48 messages ou des souvenirs sans rapport. Vérifier économies de tokens et qualité des réponses. |
| LAT-15 | P2 / P | **Barre d'interruption véritable** : couper diffusion et génération, libérer la file et reprendre une conversation après le mot d'arrêt ; barge-in sans réintroduire l'écho de Jade. |
| LAT-16 | P2 / P | Accélérer le mobile, actuellement WAV envoyé puis renvoyé en JSON Base64 : transport streaming audio bidirectionnel, file bornée et lecture progressive, y compris sur réseau mobile. |
| LAT-17 | P2 / P | Comparer le pipeline existant (STT → IA → TTS) à un **dialogue vocal Realtime natif**, en conservant intentions, persona et mémoire. A/B sur phrases identiques, p95, coûts, interruptions et français. |
| LAT-18 | P1 / C | Tester l'effet de la voix Étincelle, 1,25×, pitch +2 demi-tons : naturels des sept intentions, artefacts FFmpeg/Rubber Band, CPU, délai ajouté ; mesurer l'intérêt d'un pitch en flux. |
| LAT-19 | P2 / E | Ajuster le budget de réponse, la longueur habituelle et les fins de tour sans rendre Jade artificiellement expéditive. Le backend actuel conserve par défaut `reasoning_effort=low` et `max_completion_tokens=320` (tokens de réflexion inclus) : mesurer les compromis avant tout changement de configuration ou de moteur. |
| LAT-20 | P2 / P | Étudier le VAD sémantique / détection adaptative de fin de tour du backend temps réel ; test des pauses, interruptions, chevauchements et bruits Discord. |

## Critères de recette à conserver

- Première **réponse utile audible**, pas seulement première trame vide ou « attends ».
- Une réponse écrite ne paie **aucun TTS** sans demande vocale explicite.
- Aucun double son ni fuite locale/Discord lors d'un turn vocal ; première parole Discord non retardée par un joueur PC inutilisé.
- Cible de recherche, **non contractuelle** : première réaction simple vers 0,5–1,5 s après fin de parole en conditions favorables, p95 mesuré séparément. L'atteindre dépend du backend et du réseau.

**Sources :** [plan latence](../history/gpt6-jade/PLAN-LATENCE-20261110.md), [passation streaming](../history/gpt6-jade/HANDOFF-STREAMING-TTS-20261113.md), [voix/intention](../history/gpt6-jade/HANDOFF-CODEX-VOICE-INTENTS-20261113.md), [état de develop](../handbook/TECHNICAL.md), conversation du 16/11/2026.

### Travail local du 20 novembre

Sur `develop`, LAT-06/LAT-16 avancent avec la diffusion PCM progressive vers la PWA et la préparation parallèle du pitch ; le flux d'entrée reste un WAV complet et le LLM ne diffuse pas encore sa réponse avant sa fin. Gain réel et recette Android restent à mesurer ; aucun duplex n'est annoncé. Détails dans la [passation](../operations/handoffs/2026-11-20-codex-couts-voix-mobile.md).
