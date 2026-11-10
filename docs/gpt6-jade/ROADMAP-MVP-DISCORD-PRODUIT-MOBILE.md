# Jade : MVP Discord puis compagnon audio et visuel sur téléphone

> **Mise à jour du propriétaire — 10 novembre 2026 :** le serveur privé est
> dédié à Jade. Toute personne présente dans son salon peut participer, sans
> liste individuelle ni confirmation de consentement. Cette décision remplace
> les anciennes exigences contraires ci-dessous ; le reste de la feuille de route
> et la limitation au salon prévu restent applicables.

**Statut : spécification produit et technique pour Codex, non implémentée.**  
**Date : 3 novembre 2026.**  
**Dépôt officiel :** https://github.com/goldaj/jade-vtuber (public).  
**Branche de travail :** develop. Ne pas fusionner vers main sans décision du propriétaire.  
**Propriétaire de la vision produit :** utilisateur. **Responsable de la conception détaillée et de l'exécution :** Codex, après revue du code et des dépendances actuelles.

Ce document fixe **deux livrables successifs** : un MVP Discord complet voix + image, puis un produit dédié pour téléphone, sans dépendance obligatoire à Discord. Il définit la cible, les limites du code présent, l'architecture envisagée, les lots et les critères de recette. **Les choix techniques proposés sont à éprouver** ; ils ne signifient pas que l'intégration a été développée ni validée physiquement.

## 1. Vision et décisions produit

Jade tourne **sur le PC Windows de l'utilisateur**, qui exécute le moteur de conversation, le dialogue avec le modèle IA, la transcription et la synthèse vocale OpenAI, et l'avatar via VTube Studio. L'utilisateur peut **lui parler depuis son téléphone et voir son avatar animé** en même temps, chez lui ou à distance. Le téléphone est un terminal d'interaction, et non le lieu où le moteur IA doit obligatoirement s'exécuter.

### Règle conversationnelle ferme : aucun mot d'activation

**Il ne faut pas prononcer « Jade » pour avoir une réponse.** Jade doit répondre **quand on lui parle et qu'une intervention appelle une réponse**, naturellement, sur la base du contexte, de l'interlocuteur et de la fin de son tour de parole.

Ce n'est **ni** un mode où elle répond automatiquement à chaque bruit ou phrase entendue, **ni** un assistant qui exige un nom, un préfixe ou un bouton « parler » à chaque interaction. La décision de répondre doit être prise par une couche dédiée de **détection de tour et de pertinence** :

- Quand l'utilisateur et Jade sont seuls dans un salon privé, une intervention intelligible et terminée est normalement destinée à Jade ; elle répond sauf indice clair de parole parasite, de demande de silence ou d'absence de besoin de réponse.
- Pour plusieurs participants, elle distingue, autant que possible, les paroles qui s'adressent à elle de la conversation entre humains. En cas d'incertitude importante, elle ne doit pas interrompre tout le monde. La politique est configurable par salon et utilisateur autorisé.
- Elle comprend les suivis contextuels sans réveil verbal : « Pourquoi ? », « Et demain ? », « Attends, explique autrement » doivent prolonger l'échange en cours.
- Elle doit respecter « silence », « arrête de parler », un bouton sourdine et la sortie du salon. Un nouvel échange normal après réactivation n'exige toujours pas de prononcer son nom.
- Ne pas confondre **absence de wake word** et **écoute/transcription sans consentement** : seules les sessions vocales activées avec information des participants sont analysées.

**Ce changement remplace la règle actuelle de réponse basée sur la présence du nom dans la transcription, pour les sessions vocales interactives de Jade.** Il ne faut pas casser les règles historiques de Twitch/Discord texte sans décision séparée. L'implémentation peut utiliser un classifieur de pertinence, des règles déterministes et des états de session ; aucun modèle, seuil ou coût ne doit être imposé sans essais comparatifs.

### Autres décisions existantes à préserver

- **STT et TTS : OpenAI exclusivement.** Les librairies PCM, FFmpeg, WebRTC et de capture sont des transports/lecteurs, pas des moteurs STT/TTS concurrents.
- Le moteur de dialogue reste remplaçable (OpenAI aujourd'hui ; moteur local possible ensuite), sans réécrire les interfaces.
- **Pas de caméra de l'utilisateur** et pas de suivi facial nécessaire.
- **Latence faible** prioritaire ; cible d'une expérience naturellement conversationnelle, avec un premier objectif opérationnel de réponse ou d'erreur intelligible en moins de 60 secondes dans les cas nominaux. Les percentiles de latence devront être mesurés, pas promis.
- Préserver la sécurité du dépôt public, les secrets hors Git et les assets Git LFS.
- Le modèle graphique professionnel r21 suit son chantier propre. **Le package r20 peut servir au MVP sous réserve de vérification native** ; le r21 final n'est pas un prérequis bloquant du MVP.

## 2. Deux périmètres strictement séparés

| | **MVP Discord** | **Produit mobile complet** |
| --- | --- | --- |
| Interaction mobile | Téléphone connecté au salon vocal Discord | Navigateur mobile / PWA dédiée Jade |
| Entrée audio | Capture vocale du bot Discord, avec consentement | Microphone du navigateur sur HTTPS |
| Compréhension | STT OpenAI + analyse de pertinence sans mot d'activation | Même politique, adaptée à une conversation 1:1 |
| Réponse audio | TTS OpenAI joué par le bot Discord | Flux audio vers le navigateur, faible latence |
| Visuel | VTube Studio affiché par **un partage écran/vidéo manuel depuis le PC** | Vidéo de l'avatar intégrée dans la page Jade |
| Animation | Expressions/hotkey et mouvement de parole simple validés | Lip-sync amélioré, états émotionnels et synchronisation A/V |
| Réseau | Discord assure le transport distant | Accès privé Tailscale + signalisation + média sécurisé |
| Interface | Application Discord existante | UI spécifique : avatar, texte, sous-titres, micro, état et réglages |
| Autonomie | PC allumé, lancement du partage au besoin | PC allumé ; lancement et reconnexion simplifiés |
| Indispensable pour valider | Vraie conversation voix + avatar visible sur téléphone | Parcours sans Discord bout en bout |

**Interdiction de glissement de périmètre :** ne pas commencer WebRTC, la refonte UI ou le r21 professionnel pour masquer un MVP Discord non recetté. À l'inverse, ne pas présenter Discord comme l'architecture cible définitive.

## 3. État réel du dépôt develop au cadrage

Documents de départ : AGENTS.md, README.md, docs/conversations/INDEX.md, docs/gpt6-jade/DECISIONS.md, TASKS.md, NEXT-PRIORITIES.md, PHONE_TAILSCALE.md, docs/migration/2026-11-02/08-ASTRA-CONTROLE-DEPOT-PUBLIC.md.

| Fichier / composant | Existe | Reste à prouver / créer |
| --- | --- | --- |
| main.py | Démo hors ligne et flags --live, --voice, --mic, --discord, --discord-voice, --vts, --http, --preflight | Démarrage Windows réel conjoint, supervision, diagnostics |
| src/jade_runtime/dialogue.py, orchestrator.py, messages.py | Dialogue modulaire, queue bornée, historique RAM par (plateforme, canal), antiredondance | Session conversationnelle vocale, décision de pertinence et tours |
| openai_services.py | Dialogue OpenAI, STT WAV, TTS WAV ; modèles configurables | Tests STT/TTS facturables réels, latence, gestion des coûts |
| discord_text.py | Client discord.py, intents, connexion du bridge vocal | Authentification/permissions/connexions réelles, reprise |
| discord_voice.py | Transport Discord PCM, segmentation fixe 2 s, RMS, files bornées, transcription OpenAI, lecture TTS FFmpeg | Fin de tour, pertinence, écho, qualité et vraies sessions |
| output.py | Synthèse sérialisée, ffplay local, lecteur secondaire Discord, sous-titres OBS | Routage par destination, double sortie audio, animation au bon moment |
| vtube_studio.py | WebSocket localhost et déclenchement de hotkey VTS | Test VTS réel, hotkeys r20, expression/visèmes/bouche |
| microphone.py et voice_pipeline.py | Capture du **micro PC** et demi-duplex | Ne pas confondre avec audio Discord ou micro du téléphone |
| local_http.py et phone_ui.py | Page chat texte et POST /message protégés par bearer en loopback | **Aucun** média mobile, WebRTC ni chat vocal navigateur |
| PHONE_TAILSCALE.md | Guide HTTP HTTPS privé via Tailscale Serve | Installation/ACL/recette mobile ; transport média distinct |
| jade-modeling | Sources 2D et objets LFS ; r20 et chantier r21 | Vérifications réelles du package actif/rig/export |

**Écart important constaté dans le code :** DiscordVoiceBridge._consume transmet un message discord_voice sans force_reply ; Dialogue.should_reply ne répond par défaut que lorsque « Jade » apparaît, qu'un préfixe explicite est utilisé ou qu'un tirage aléatoire l'autorise (taux par défaut 0). **Supprimer cette dépendance au nom dans le parcours vocal, sans activer un force_reply global indiscriminé.** La bonne couche métier doit décider si un **tour terminé et pertinent** est éligible, puis le faire traiter par le dialogue.

**Autre écart :** SpeechOutput diffuse vers Discord seulement les réponses dont la source est discord_voice. Garder un routage sécurisé par défaut et ne pas élargir les origines autorisées implicitement. Dans main.py, la hotkey VTube Studio est appelée **avant** la synthèse TTS ; elle peut être désynchronisée de la voix. Le texte de sous-titres OBS est affiché d'un bloc et n'a **pas** de timing mot/phonème.

**Niveau de preuve :** dernière contre-revue du 2 novembre = 84 tests unitaires locaux et démo réussis ; elle ne certifie **pas** la connexion Discord vocale réelle, micro réel, audio réel, VTube Studio réel ni le téléphone. Revalider sur le HEAD au moment d'exécuter.

## 4. Architecture transverse proposée

L'application doit posséder **un seul cerveau et des adaptateurs de transport** :

    Discord voice       Navigateur mobile       Texte Discord/HTTP/Twitch
          |                    |                           |
          v                    v                           v
    Capture/PCM          Capture/WebRTC                Normalisation
          |                    |                           |
          +----------> VAD / tours de parole <-------------+
                              |
                              v
                     OpenAI STT (si audio)
                              |
                              v
          Gestion de session + interlocuteur + pertinence
                 (aucun mot d'activation obligatoire)
                              |
                    décision : répondre ?
                        /             \
                      non             oui
                      |                |
             ignorer sans réponse   Dialogue Jade
                                         |
                                     OpenAI TTS
                                         |
                            Bus de sortie par session
                          /          |            \
                    Discord WAV   Web audio     VTS/OBS
                     + texte      + sous-titres  + visuel

Le bus de sortie ne doit pas envoyer par hasard une réponse de Twitch, d'un autre utilisateur ou du web dans un salon Discord privé. Chaque réponse porte une **identité de session, un destinataire/transport et un identifiant de tour**. Les messages vocaux d'une session ne doivent pas contaminer l'historique d'une autre, même si le moteur est partagé.

### 4.1 Contrat de tour de parole

Définir à minima les états IDLE / LISTENING / SPEECH_DETECTED / TRANSCRIBING / DECIDING / THINKING / SPEAKING / COOLDOWN / MUTED / ERROR, avec transitions, délais limites et annulation. Les événements doivent porter session_id, speaker_id, turn_id, source, timestamps monotones et état d'autorisation, **sans audio/transcription dans les logs**.

- Une VAD **non IA vocale** ou une segmentation locale permet d'éliminer les silences et de regrouper un tour entier avant d'appeler le STT OpenAI. Une VAD n'est **pas** une transcription : elle n'enfreint pas la règle OpenAI STT/TTS.
- Paramètres initiaux **à tester**, non imposés : silence terminal approximatif 500–900 ms, borne de segment 10–15 s, pré-roll bref, seuil de durée de parole et protection contre segments trop petits. Respecter limite de taille, backpressure et usage RAM.
- Éviter les coupures des phrases longues et l'envoi de deux transcriptions pour un seul tour. Si segment partiel, assembler les fragments proprement et ne répondre **qu'au tour validé**.
- Ne pas rediffuser sa propre voix : ignorer les utilisateurs bots, gérer les retours de haut-parleur, bloquer ou atténuer les entrées durant la lecture dans le MVP demi-duplex, puis expérimenter barge-in/interruptions plus tard.
- En cas d'API lente, timeout, sortie, annulation ou déconnexion : invalider le tour, libérer ressources et éviter l'émission tardive d'une réponse obsolète.

### 4.2 Moteur de pertinence sans nom d'activation

Introduire une unité testable du type ConversationTurnDecider, indépendante de Discord et du backend LLM. Contrat possible :

    decide(session_context, speaker, final_transcript, audio_metadata)
      -> {should_reply, reason_code, confidence, policy, turn_id}

La décision tient compte de l'auteur autorisé, de la nature de la session, de l'état précédent, de la question/interpellation, des liens avec le dernier tour et des signaux « je parle à quelqu'un d'autre ». Elle **ne dépend pas de la présence du nom Jade**. Le nom reste un élément linguistique possible, jamais une condition de réponse.

Politique proposée, **prioritaire pour le MVP privé** :
1. **Salon dédié avec l'utilisateur seul face au bot :** après fin de tour, répondre par défaut à une intervention naturelle, y compris « Salut », « Tu penses quoi de ça ? », « Et pourquoi ? ». Ignorer silence, bruit, fragments trop ambigus ou phrases explicites d'aparté ; la réponse doit être pertinente au contexte, non mécanique.
2. **Salon avec d'autres humains :** répondre si le contexte indique que l'on s'adresse à Jade ou que la réponse est attendue ; ne pas commenter chaque conversation entre humains.
3. **Suivi de conversation :** conserver un état actif temporaire configurable après une réponse, sans exiger un mot de réveil à chaque tour. Une nouvelle phrase adressée à Jade doit pouvoir réactiver le dialogue naturellement.
4. **Suppression volontaire :** commande vocale naturelle de silence ou mute UI coupe les réponses jusqu'à réactivation ; aucune transcription en dehors d'une session consentie, et possibilité d'arrêter entièrement l'écoute.
5. **Incertitude :** ne pas prendre une décision irréversible sur la seule présence de « ? » ou de mots-clés. Un classifieur de pertinence léger peut être utilisé après STT si nécessaire, mais son coût/latence, les faux positifs et la confidentialité sont à mesurer. Fallback documenté, testable et déterministe ; ne pas faire un second appel LLM pour chaque parole si l'usage n'en justifie pas le coût.

**Recommandation d'implémentation :** ne pas enlever Dialogue.should_reply pour toutes les sources ; fournir une autorisation de réponse explicite générée **en amont** par le moteur de tours vocaux validés, avec contrôles source/session. Refuser les segments Discord hors canal/participants autorisés. Attention aux classifieurs trop stricts qui feraient perdre des demandes courtes ou des questions de suivi ; priorité au naturel en tête-à-tête.

Cas de recette unitaires obligatoires : salutation sans nom, question directe sans nom, suivi « et pourquoi ? », phrase courte après réponse, pensée à voix haute sans sollicitation, conversation entre deux personnes, bruit/silence, autre utilisateur non autorisé, interruptions, microphone réécoutant le TTS, arrivée de nouveaux participants, muting et déconnexion. Noter faux déclenchements **et** questions légitimes manquées.

## 5. MVP Discord : lots de réalisation et critères d'acceptation

### D0. Base propre et sécurité

- Examiner HEAD develop/main, différences, docs AGENTS et revue Astra ; ne pas restaurer l'ancien runtime diverg ent ni les secrets historiques.
- CI : tests hors ligne, compilation, scan de secrets sur chaque changement (point P2 ouvert de la revue), dépendances à versions contrôlées, Git LFS vérifié.
- Sur Windows, cloner develop, Python 3.11, Poetry 2.2.1 compatible lock, installer extras discord-voice et vts et outils FFmpeg (ffmpeg/ffplay selon sorties), récupérer LFS.
- Valider démo hors ligne et preflight **sans compte, sans micro et sans appel payant**. Corriger les anomalies locales avant toute connexion.
- Consigner les étapes Windows/PyCharm réelles, prérequis, emplacement des exécutables, erreurs et versions effectivement testées.
- **Gate D0 :** installation reproductible, tests offline verts sur le SHA exact, démo validée, secrets hors dépôt.

Commandes indicatives (adapter au poste et au lock ; ne pas lancer les modes live sans accord explicite) :

    git lfs pull
    poetry sync --only main -E discord-voice -E vts
    poetry run python -m unittest discover -s tests -v
    poetry run python -m compileall -q src main.py
    poetry run python main.py
    poetry run python main.py --preflight --live --voice --discord --discord-voice --vts

Le preflight est **sans appel** aux fournisseurs, même lorsque live est présent dans les paramètres. Les réglages privés se font via l'environnement/JADE_SECRETS_FILE, jamais dans ces commandes publiées.

### D1. Dialogue et voix OpenAI sur le PC

- Valider texte OpenAI en configuration réelle contrôlée, puis un petit fichier audio STT et TTS réel, avec budget d'essai explicite, sans boucle de test facturable.
- Écouter le WAV via ffplay, contrôler langue française, voix, volume et codecs, et confirmer que le TTS ne produit pas de sortie sur la mauvaise carte audio.
- Instrumenter les durées : fin d'énoncé -> STT, STT -> LLM, LLM -> TTS, TTS -> début de lecture. Journaliser **durées et codes d'erreur**, jamais payloads vocaux ou secrets.
- **Gate D1 :** un échange local démontré, coûts/appels relevés, échec propre si API indisponible. La présence de sounddevice ou ffplay sur PATH n'est pas une recette.

### D2. Bot vocal Discord opérationnel

- Créer/configurer (sur le compte choisi par l'utilisateur) le bot et un **salon vocal privé de test**. Ne demander que les permissions nécessaires : rejoindre/parler, recevoir l'audio, intents si nécessaires au texte ; vérifier les paramètres du portail développeur Discord et les versions de SDK. L'utilisateur autorise l'ajout au serveur.
- Vérifier de bout en bout : arrivée du bot, réception PCM **uniquement** des participants autorisés et informés, encodage 48 kHz stéréo -> WAV, STT, dialogue, TTS, restitution via Discord depuis le même salon.
- Remplacer la segmentation fixe 2 secondes par une reconnaissance de fin de tour adaptée (voir section 4), sans perdre les protections de limite de buffers/queue.
- Intégrer le moteur de pertinence décrit section 4.2 : **aucun besoin de dire « Jade »**.
- Contrôler le flux audio : avec JADE_AUDIO_OUTPUT=none, écouter la réponse une seule fois via le bot Discord. Ne pas supposer que la présence du WAV dans le fichier temporaire garantit que Discord l'a diffusé. Tester aussi la déconnexion au milieu d'une lecture et l'arrêt propre.
- Prendre en compte le filtrage des autres bots, le retour micro/haut-parleur, le silence, les erreurs de permissions, le reconnexion et une file saturée.
- **Gate D2 :** conversation réelle depuis Discord sur le téléphone sans mot d'activation, au moins 10 tours de test variés dont questions de suivi, aucune double voix et aucune boucle d'auto-réponse. Le propriétaire valide oralement la qualité.

Commande indicative **après autorisation** et configuration privée : 

    poetry run python main.py --live --voice --discord --discord-voice

Ne pas activer --mic pour capter le micro du PC quand l'utilisateur parle depuis Discord mobile, sauf essai local séparé.

### D3. Avatar visible et animé sur le PC

- Vérifier le modèle r20 réellement chargé dans VTube Studio ; récupérer assets LFS, contrôler le package exporté, ne jamais supposer r21 fini.
- Activer l'API locale de VTube Studio et obtenir son jeton via une procédure locale privée ; vérifier authentification et hotkey de prise de parole/expression avec une action visible. Le plugin ne doit se connecter qu'à localhost.
- Réconcilier la temporalité : le déclenchement visuel **au début de lecture audio** et retour à idle en fin/échec, plutôt que l'actuelle hotkey déclenchée avant la synthèse vocale ; protéger les états en cas de TTS interrompu.
- Au MVP, une expression animée cohérente / mouvement de bouche simple peut suffire. Le **lip-sync continu** n'est considéré livré que si une vraie animation dépend du signal audio (ex. amplitude et lissage, paramètres VTS compatibles avec le rig). Un déclenchement unique de hotkey n'est **pas** du lip-sync.
- **Gate D3 :** avatar affiché, repos/mouvement à la parole vérifiés à l'œil, aucun suivi caméra requis ; rig r20 utilisable. Documenter ce qui reste rudimentaire.

### D4. Visualisation sur Discord mobile

**Voie MVP privilégiée : partage manuel depuis le client Discord PC de l'utilisateur.** Ce n'est pas le bot qui émet une diffusion d'écran.

1. Ouvrir VTube Studio sur PC et cadrer Jade. Si nécessaire, créer une scène OBS dédiée avec fenêtre/capture VTube Studio, fond et sous-titres.
2. Avec **le client Discord utilisateur sur PC**, rejoindre le salon et lancer Go Live / partage de fenêtre VTube Studio ou OBS (ou étudier VTubeStudioCam / OBS Virtual Camera comme **entrée webcam** selon le client et les tests). Éviter de partager tout l'écran et les notifications privées.
3. Sur téléphone, rejoindre le salon vocal, regarder la diffusion et vérifier que la **voix du bot** est audible. La piste audio du stream est **désactivée ou isolée** si elle contient la voix de Jade, sinon elle produirait un doublon/écho.
4. Mute du micro du compte Discord PC si la seule entrée voulue est le téléphone ; éviter toute capture des haut-parleurs du PC.
5. Vérifier droits de diffusion, flux vidéo réellement reçu sur le téléphone, son, décalage, arrêts et reconnexion.

**Important :** OBS Virtual Camera **ne diffuse pas à elle seule sur Internet** ; elle expose une caméra virtuelle à un client. De même, un bot Discord utilisant l'API officielle ne doit pas être supposé capable de démarrer Go Live. Le MVP accepte une étape utilisateur sur le PC.

**Gate D4 / recette finale MVP :** depuis le téléphone, l'utilisateur **voit Jade**, prononce une question **sans dire son nom**, obtient une réponse vocale pertinente, puis pose un suivi sans réveil. Jade réagit visuellement pendant sa réponse. Test à distance en réseau cellulaire si possible ; délai parole->audio mesuré et absence d'écho/double audio. Les limites manuelles du visuel sont explicitement assumées.

### D5. Stabilisation et notice d'exploitation MVP

- Script/lanceur local de démarrage **sans secrets embarqués** : préflight, services nécessaires, options de port, erreurs compréhensibles, arrêt et nettoyage ; respecter les processus préexistants du PC.
- Redémarrages contrôlés Discord, panne réseau, quotas API, sortie du salon, ordinateur en veille, absence de modèle VTS, fermeture OBS.
- Table de diagnostic : pas de voix ; Jade répond à côté ; Jade ne répond pas ; pas de vidéo mobile ; lèvres figées ; echo ; audio en double ; facturation excessive.
- Documenter autorisations Discord, consentement audio, politiques d'accès, coût et durée de session. Ne pas laisser le bot écouter un salon quelconque en permanence sans activation explicite.
- **Sortie MVP** : preuves (logs techniques expurgés + checklist de recette), limitation clairement connue, et décision de démarrer le produit mobile. Aucun faux « terminé » sur la base de mocks.

## 6. Produit complet : architecture cible proposée

Le produit complet doit offrir un **écran unique** :

- Avatar Jade occupant la majorité de l'écran et animé.
- État clair : « connectée », « écoute », « comprend », « réfléchit », « parle », « connexion perdue », « micro désactivé ».
- Sous-titres et historique texte accessible, sans couvrir excessivement l'avatar.
- Microphone (autorisation système et mute), contrôle du volume, bouton interrompre/stop, reconnexion et nouvelle conversation.
- Un **mode conversation naturelle** par défaut quand la session est active : **pas de mot d'activation**. Contrôle explicite pour désactiver l'écoute.
- Ergonomie portrait et paysage, tactile, réseaux mobiles ; PWA installable seulement si sa valeur est prouvée.

**Transport cible à expérimenter : WebRTC** (audio du navigateur vers le PC, audio TTS/vidéo VTube Studio/OBS du PC vers le téléphone), avec signalisation HTTPS authentifiée. Il faut sélectionner une pile serveur maintenable après prototype (par exemple un serveur WebRTC côté PC ou une bibliothèque Python adaptée), évaluer la charge CPU, le codec audio, l'encodage vidéo, le navigateur Android/iOS et la stabilité.

**Attention au piège réseau : Tailscale Serve sait exposer un service HTTP(S) local ; cela ne prouve pas que les flux média WebRTC/ICE/UDP passeront automatiquement à travers le proxy Serve.** Prévoir un spike de connectivité média au début du produit complet. Étudier les candidats ICE via le tailnet, les ACL et ports du pair, un relais TURN privé si nécessaire, ou un transport alternatif via TLS/WebSocket avec compromis de latence documenté. Ne pas ouvrir de port public ni utiliser Tailscale Funnel par défaut. Le choix final devra découler d'un test depuis le téléphone sur Wi-Fi et en 4G/5G.

### 6.1 Frontière de sécurité

- Continuer à lier l'API HTTP applicative à 127.0.0.1 ; exposition **privée** via Tailscale Serve, règles tailnet restrictives, HTTPS et authentification applicative.
- Le micro navigateur nécessite HTTPS et permission utilisateur. Jamais d'activation invisible de la capture ni de tentative d'obtenir la caméra.
- Conserver les secrets sur le PC : API OpenAI, jeton Discord, VTS, authentification Jade. **Aucun** de ces secrets dans le frontend, Git, URL, journaux, enregistrements d'écran, localStorage, sessionStorage ou service worker.
- Authentifier **la signalisation et l'accès au média** : session temporaire à expiration, contrôle d'Origin/CSRF si cookies utilisés, autorisation de chaque transport et restriction des clients non autorisés. Les navigateurs ne permettent pas d'ajouter librement un header Authorization à une ouverture WebSocket : ne pas improviser un jeton persistant dans la query string ; choisir un handshake éphémère sûr ou de la signalisation HTTP authentifiée.
- Définir durées limites et protections contre déni de service : session inactive, taille et débit des uploads audio, requêtes concurrentes, frames, nombre de clients et ressources vidéo.
- **Vie privée :** par défaut aucun stockage durable de WAV/transcriptions ; mémoire dialogue bornée en RAM aujourd'hui. Une mémoire persistante éventuelle est un chantier séparé et opt-in. Attention : les flux de transcription envoyés au fournisseur STT sont des données transmises au service, à expliquer.
- Permettre un arrêt immédiat de l'écoute et une révocation de session ; détruire pistes média, processus d'encodage et buffers à l'arrêt.

### 6.2 Modèle vidéo et lip-sync

Pour le produit mobile, produire la vidéo depuis **VTube Studio sur PC** : fenêtre capturée de façon restreinte, caméra virtuelle VTubeStudioCam ou scène OBS, selon disponibilité et mesure CPU. Ne pas présumer que la caméra virtuelle est un flux réseau ; un encodeur/serveur doit prendre la source et l'envoyer vers le navigateur.

Pour le son : une **seule génération TTS OpenAI par réponse**, distribuée aux sorties explicitement autorisées. Le son entendu dans le navigateur doit correspondre au mouvement du personnage. La synchronisation peut commencer par amplitude d'enveloppe WAV lissée, puis utiliser des paramètres de bouche du modèle r20/r21 seulement après vérification de leurs mappings VTS. Une hotkey ponctuelle n'est pas équivalente.

Proposer des états visuels : neutre/idle, écoute, pensée, parle, erreur, expressions contextuelles limitées. Refuser l'animation agressive ou erratique déclenchée à chaque chunk réseau. Tester désynchronisation A/V, coupures de son, frames perdues et latence de capture.

### 6.3 Architecture de sessions

Une conversation mobile doit rester isolée de Discord et du chat texte. Le mécanisme actuel d'historique en RAM par (platform, channel) est une base **mais pas une véritable identité inter-transport**. Introduire si nécessaire un SessionManager avec identifiants imprévisibles, session liée à l'utilisateur authentifié, durée de vie et reconnexion, sans fusion d'historiques par simple nom.

Pipeline de sortie avec événements de haut niveau :

    user_speech_started
    user_speech_finished
    transcript_final
    turn_accepted / turn_ignored(reason)
    generation_started / generation_finished
    audio_playback_started / audio_playback_finished
    avatar_state_changed
    session_disconnected / session_reconnected

Utiliser un état par session et annuler les réponses périmées ; conserver l'ordre des tours. Les événements ne doivent pas révéler une transcription à une autre session.

### 6.4 Latence, capacités et robustesse

Instrumenter, dans chaque environnement, les durées P50/P95 et maximum : fin de parole → VAD ; VAD → STT ; STT → pertinence ; pertinence → LLM ; LLM → premier audio TTS ; audio TTS → audio joué ; vidéo → image affichée ; décalage A/V. Mesurer latence Wi-Fi/4G, CPU/RAM du PC, coût par session et échecs. Le MVP WAV complet n'est pas forcément assez rapide ; évaluer la synthèse vocale en streaming **chez OpenAI** si besoin, sans introduire un fournisseur TTS alternatif.

Gérer : autorisation micro refusée ; permission révoquée ; téléphone verrouillé et app passée en arrière-plan ; réseau changé ; VPN déconnecté ; PC en veille ; quotas OpenAI épuisés ; ressource VTube Studio fermée ; session expirée. Ne pas promettre que le navigateur continuera à enregistrer/parler écran verrouillé : tester réellement et afficher les restrictions OS.

## 7. Lots du produit complet (après acceptation MVP)

| Lot | Livrable Codex | Validation minimale |
| --- | --- | --- |
| P0 — Spike médias et réseau | Prototype WebRTC ou solution alternative privée ; source vidéo VTS/OBS ; preuve de connectivité | Audio/vidéo du PC sur **vrai téléphone** Wi-Fi et réseau mobile ; aucun port public |
| P1 — Contrat conversation multimodal | Abstraction entrée/sortie/session, bus d'événements, annulation et routage | Tests de séparation des sessions et de non-rediffusion |
| P2 — Micro navigateur et flux retour | Capture HTTPS, autorisations, transport vers STT OpenAI, retour TTS | Conversation audio sans Discord, sans prononcer le nom |
| P3 — Avatar intégré | Flux vidéo et contrôleur d'animation synchronisé | Avatar sur téléphone et mouvement cohérent à la voix |
| P4 — Interface mobile | UI responsive, sous-titres, mute, états, reconnexion, historique RAM | Recette portrait/paysage, Android/iOS ciblés |
| P5 — Sécurité et stabilité | Auth éphémère, ACL, limites, supervision, nettoyage des ressources | Tests d'accès refusé, panne VPN/PC/API, absence de fuite |
| P6 — Optimisation et livraison | Mesures latence/coûts, qualité de réponse et packaging de démarrage | Parcours utilisateur reproductible et documenté |

**Ne pas réaliser simultanément le MVP Discord et le produit P0–P6.** Achever et mesurer le MVP ; le spike média P0 peut ensuite invalider WebRTC et conduire à une autre implémentation **sans changer la vision produit**.

## 8. Tests et preuves obligatoires

**Tests automatisés sans services externes :**
- Décision de pertinence sans wake word pour questions, salutations, suivis et demande de silence.
- Non-réponse aux silences, bruits, voix du bot, utilisateurs non autorisés et apartés entre humains.
- Segmentation de phrases complètes, protection contre déclenchements répétés, anti-écho et anti-doublon.
- Plusieurs tours rapprochés, annulation, queue saturée, déconnexion pendant STT/LLM/TTS, arrêt.
- Routage sécurisé : jamais de lecture d'une source tierce dans une destination non autorisée.
- Secrets masqués, accès HTTP non authentifié refusé, sessions isolées.
- Pas de média ni de facture réelle en CI.

**Recettes physiques manuelles :**
- D'abord Discord sur téléphone : 10 échanges au moins, dont 3 sans le mot « Jade », plusieurs suivis courts, une requête interrompue, un silence volontaire, un aparté et une panne simulée.
- Le critère important n'est **pas** de mentionner Jade dans 3 exemples : **aucun** échange ne doit l'exiger. Les questions courantes sans son nom doivent déclencher normalement.
- Puis Discord voix + fenêtre visuelle réellement visible depuis le téléphone, avec mouvements cohérents, sans double son.
- Pour le produit, recommencer l'épreuve sans Discord, sur Wi-Fi et sur réseau mobile, et contrôler autorisation, reconnexion et fidélité des sous-titres.
- Rapports : timestamp du test, machine/OS, navigateur/version, SHA du code, modèle r20/r21, services activés, étapes, observations, durées/consommation, anomalies, statut. Jamais de secrets ni de voix enregistrée sans opt-in explicite.

### Critères de sortie clairs

**MVP Discord livré** seulement lorsque le propriétaire peut, depuis son téléphone, *parler naturellement sans appeler Jade par son nom, entendre la réponse de Jade dans Discord, voir son personnage bouger dans Discord*, avec une procédure de lancement sur le PC qui marche, et une liste explicite des limitations (notamment le partage d'écran manuel).

**Produit complet livré** seulement lorsque le propriétaire réalise le **même parcours sans Discord**, en voyant Jade et en lui parlant dans une seule interface privée sur téléphone, avec sécurité, reprise sur erreur et latences mesurées.

## 9. Gouvernance, dépendances et interdictions

- Suivre les règles de AGENTS.md et docs/gpt6-jade/TERA-ASTRA-WORKFLOW.md. Exécution ordinaire sous Terra/Tera, escalade motivée sous Astra si nécessaire ; bascule humaine et non automatique. Le propriétaire reste décisionnaire des revues et des fusions.
- Sur develop : préparer un plan d'implémentation par lots, puis coder en commits indépendants, avec tests et comptes rendus au fur et à mesure. **Ne pas fusionner main sans autorisation.**
- Vérifier la compatibilité de discord-ext-voice-recv, discord.py, FFmpeg et de la chaîne audiovisuelle actuelle sur Windows ; ne jamais introduire deux SDK Discord concurrents.
- Réutiliser l'orchestrateur et les sources r20/r21, ne pas ramener l'ancien runtime, ne pas retoucher les assets binaires sans besoin explicite, ne jamais omettre Git LFS.
- La migration publique a été auditée mais le scan de secrets en CI doit encore être durci : traiter avant les futures extensions importantes. Aucun secret ou configuration privée dans ce document ni dans les commits.
- Ne pas faire de capture, de transcription, de connexion à un salon ou d'appel API payant en dehors d'une session d'essai explicitement convenue avec le propriétaire. Le consentement des autres participants est une exigence du produit.
- Chaque lot : code/livrables, tests réellement exécutés, statut simulé ou physique, risques, blocages et prochaine action dans docs/gpt6-jade/TASKS.md ou un CR dédié.

## 10. Questions d'ingénierie que Codex doit trancher et documenter

1. Quelle VAD locale / politique de fin de tour offre le meilleur compromis faux déclenchements, coût STT, latence et maintenance sur le PC cible ?
2. Comment faire passer un tour vocal pertinent vers Dialogue sans rendre tous les transports systématiquement bavards ni modifier leur politique d'origine ?
3. Comment détecter une prise de parole qui s'adresse à Jade **sans jamais imposer son nom**, surtout en groupe ? Comparer règles + contexte, classification légère, fenêtre d'échange, et mesurer précision/rappel.
4. Comment attacher correctement l'identité Discord (user_id) aux tours PCM, la session, et l'autorisation ; ne pas se contenter du display_name susceptible de changer/collisionner ?
5. Quel chemin d'animation r20 réellement fonctionnel (hotkey, paramètres bouche) et quel moment de déclenchement par rapport au vrai WAV joué ?
6. Quelle méthode de diffusion Discord PC est la plus robuste dans la pratique : partage VTube Studio, scène OBS, caméra virtuelle VTubeStudioCam, caméra OBS ? **Valider visuellement**, ne pas supposer que la caméra virtuelle diffuse seule.
7. Pour le produit complet, comment la signalisation HTTPS privée rejoint-elle les transports médias dans Tailscale ? Quelles ACL/ICE/UDP/port et alternatives faut-il tester ?
8. Quel routage de la sortie audio évite l'écho ou la double restitution quand Discord voix, stream vidéo et lecture locale coexistent ?
9. Quelle politique de reconnexion, interruption et état des sessions tient sur un PC parfois en veille et un téléphone en réseau cellulaire ?
10. Quelle mesure de performance et quels garde-fous tarifaires assurent une expérience utile sans facturation silencieuse excessive ?

Ces points sont **des décisions à documenter par essais**, pas des raisons pour bloquer indéfiniment le premier MVP.

## 11. Ordre d'exécution pour Codex

**Maintenant, sur develop :** audit rapide HEAD, correction des prérequis/sécurité restants, puis D0.  
**Ensuite :** D1 (IA/voix PC), D2 (Discord voix et pertinence sans mot d'activation), D3 (avatar VTS), D4 (partage visuel sur Discord mobile), D5 (stabilisation).  
**Après validation par le propriétaire :** P0 (faisabilité média privé), puis P1 à P6 (application mobile complète).

Ne déclarer une étape finie qu'avec des preuves conformes à son gate. Si un élément exige le PC ou le téléphone réel, fournir au propriétaire une procédure de test précise et laisser l'étape **à recetter**, plutôt que de la considérer terminée à partir des tests simulés.

## 12. Références utiles

**Dans le dépôt**
- https://github.com/goldaj/jade-vtuber/blob/develop/AGENTS.md
- https://github.com/goldaj/jade-vtuber/blob/develop/docs/gpt6-jade/DECISIONS.md
- https://github.com/goldaj/jade-vtuber/blob/develop/docs/gpt6-jade/NEXT-PRIORITIES.md
- https://github.com/goldaj/jade-vtuber/blob/develop/docs/gpt6-jade/PHONE_TAILSCALE.md
- https://github.com/goldaj/jade-vtuber/blob/develop/docs/migration/2026-11-02/08-ASTRA-CONTROLE-DEPOT-PUBLIC.md
- https://github.com/goldaj/jade-vtuber/blob/develop/jade-modeling/MODEL2D_CODEX_STATE.md

**Documents externes à vérifier lors du développement**
- Discord, Go Live / partage d'écran et visionnage mobile : https://support.discord.com/hc/fr/articles/360040816151-Go-Live-et-Partage-d-%C3%89cran
- Discord, visionnage de flux depuis mobile : https://support.discord.com/hc/en-us/articles/360058862134--Mobile-Screenshare-FAQ
- OBS, caméra virtuelle : https://obsproject.com/kb/virtual-camera-guide
- VTube Studio, webcam virtuelle (Windows) : https://github.com/DenchiSoft/VTubeStudio/wiki/FAQ
- Accès HTTPS privé Tailscale Serve : https://tailscale.com/docs/features/tailscale-serve
- Microphone navigateur / contexte HTTPS et permission : https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia

**Décision produit actée le 3 novembre 2026 :** Jade répond lorsqu'on lui parle et qu'une réponse est pertinente. **Prononcer son nom ne sera jamais une condition préalable à l'interaction vocale.**
