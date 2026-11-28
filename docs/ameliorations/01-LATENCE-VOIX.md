# Latence, capture vocale et synthèse progressive

**Objectif produit :** temps de réaction court et régulier, sans déguiser un délai de réflexion par une phrase de remplissage. Aucune cible chiffrée n'est encore démontrée sur le PC de Jade.

| ID | Priorité / état | Amélioration proposée / condition de réussite |
| --- | --- | --- |
| LAT-02 | P1 / E | Remplacer les seuils Discord actuels (~500 ms et seuil d’énergie relatif) par un **VAD plus adaptatif** si la recette le justifie ; mesurer les compromis, sans couper les hésitations et phrases françaises. |
| LAT-03 | P1 / E | Abandonner la capture micro PC en fenêtres fixes d'environ 3 s au profit d'un VAD local qui déclenche STT dès la fin de la phrase ; préserver anti-écho et refus des bruits. |
| LAT-04 | P2 / P | Essayer le **STT incrémental / streaming audio** pour préparer une réponse avant fin d'enregistrement ; gérer hypothèses de transcription révisées et conflits d'identité. |
| LAT-08 | P2 / P | Fan-out PCM unique **uniquement vers les sorties autorisées** (pas de broadcast automatique), bouche et sous-titres synchronisés sur les trames consommées ; éviter WAV intégral/temporaire et démarrages ffplay/FFmpeg par réponse. |
| LAT-11 | P1 / P | Hors mode Live mobile (lot DEV-040/046–051), garder à chaud les sessions/connecteurs nécessaires à un tour probable, avec bornes de coût et fermeture en inactivité ; comparer froid/chaud sans payer silencieusement 24 h/24. |
| LAT-13 | P2 / P | Mettre en concurrence non bloquante les lectures mémoire et reconstitutions d'historique quand l'identité et les scopes le permettent ; benchmark : gains potentiellement petits, ne pas surarchitecturer. |
| LAT-14 | P2 / P | Cache de préfixe de prompt et de contexte stable, prompts compacts ; ne pas envoyer systématiquement 48 messages ou des souvenirs sans rapport. Vérifier économies de tokens et qualité des réponses. |
| LAT-15 | P2 / P | **Barre d'interruption véritable hors mode Live mobile (lot DEV-040/046–051)** : couper diffusion et génération, libérer la file et reprendre une conversation après le mot d'arrêt ; barge-in sans réintroduire l'écho de Jade. |
| LAT-19 | P2 / E | Ajuster le budget de réponse, la longueur habituelle et les fins de tour sans rendre Jade artificiellement expéditive. Le backend actuel conserve par défaut `reasoning_effort=low` et `max_completion_tokens=2048` (tokens de réflexion inclus) : mesurer les compromis avant tout changement de configuration ou de moteur. |
| LAT-20 | P2 / P | Étudier hors mode Live mobile (lot DEV-040/046–051) le VAD sémantique / détection adaptative de fin de tour ; test des pauses, interruptions, chevauchements et bruits Discord. |
| LAT-21 | **P3 / D** | **Mesure du début de lecture audio réellement consommée côté client** : au-delà des jalons serveur de [DEV-024](../backlog/01-DEVELOPPEMENT.md), instrumenter lorsque possible la première trame PCM non silencieuse effectivement remise au lecteur logiciel sur PWA/PC/Discord, avec horloges corrélées, abandons/interruptions et p50/p95. **Limite physique :** cette mesure ne prouve jamais que l'humain a entendu le son (volume, Bluetooth, périphérique muet) ; afficher « lecture constatée » ou « mesure indisponible », pas « audible confirmé ». Condition de lancement : protocole testable et coût nul ou négligeable, sans requête LLM supplémentaire ni ralentissement perceptible. |
| LAT-22 | **P3 / D** | **Attribution et rapprochement du coût réel par tour** : compléter les tokens fournisseur déjà instrumentés dans [DEV-024](../backlog/01-DEVELOPPEMENT.md) par des tarifs versionnés, une estimation clairement étiquetée et un rapprochement ultérieur avec des relevés officiels **uniquement s'ils permettent réellement cette granularité**. Distinguer dépenses STT/LLM/TTS, coûts agrégés et données non disponibles ; interdiction d'afficher un montant calculé comme « facture exacte ». Préférer le suivi global [NEW-01](11-CAPACITES-COMPORTEMENT-CONTROLE.md) si l'API n'expose pas les données par requête. Critère de lancement : faisabilité vérifiée et bénéfice supérieur à la complexité. |

**Transfert du 25/11, précisé le 26/11 :** LAT-17 est reprise dans le [lot Live mobile](../backlog/PLAN-LIVE-MOBILE.md), initialement DEV-040, maintenant ventilé entre DEV-040 et DEV-046..051. LAT-11/15/20 ne couvrent plus ce périmètre ; les autres canaux restent prospectifs. Le flag Discord réservé OFF ne constitue pas son implémentation.

**Promotion du 22/11/2026 :** LAT-10 est maintenant suivie en [DEV-030](../backlog/01-DEVELOPPEMENT.md), au statut À faire. Aucun timeout TTS n'a été modifié dans ce lot.

## Critères de recette à conserver

- Première **réponse utile audible**, pas seulement première trame vide ou « attends ».
- Une réponse écrite ne paie **aucun TTS** sans demande vocale explicite.
- Aucun double son ni fuite locale/Discord lors d'un turn vocal ; première parole Discord non retardée par un joueur PC inutilisé.
- Cible de recherche, **non contractuelle** : première réaction simple vers 0,5–1,5 s après fin de parole en conditions favorables, p95 mesuré séparément. L'atteindre dépend du backend et du réseau.

**Sources :** [plan latence](../history/gpt6-jade/PLAN-LATENCE-20261110.md), [passation streaming](../history/gpt6-jade/HANDOFF-STREAMING-TTS-20261113.md), [voix/intention](../history/gpt6-jade/HANDOFF-CODEX-VOICE-INTENTS-20261113.md), [état de develop](../handbook/TECHNICAL.md), conversation du 16/11/2026.

### État des fonctionnalités déjà livrées

Le PCM progressif Discord et mobile, la connexion TTS partagée et les premières mesures de latence sont suivis dans les cartes DEV-007/008 et REC-006/029, déjà livrées et/ou validées. Le **profilage complet** est transféré en [DEV-024](../backlog/02-RECETTE.md#rec-034-ancienne-dev-024--lat-01--métrologie-de-bout-en-bout-multi-canal). Les pistes ci-dessus concernent des capacités **supplémentaires** et ne rouvrent pas ces validations.
