# Compte rendu des étapes

Chaque lot doit indiquer : livrable, validation observée, limites et niveau de confiance,
sans présenter les mocks comme des tests d'API réels.

## MVP Discord — D0, 3 novembre 2026
- Base `bb44d7a` installée depuis le lock sur Windows dans un environnement isolé
  avec Python 3.11.1, Poetry 2.2.1 et extras Discord vocal/VTS ; `pip check`,
  135 tests, compilation, démo, préflight et contrôles LFS réussis.
- CI GitHub tests Windows/Linux et scan des secrets réussis sur ce même SHA.
  Le faux secret utilisé par l'autotest est devenu déterministe après un échec
  intermittent ; il ne constitue pas une clé réelle.
- FFmpeg, ffplay et ffprobe ont été copiés vers D: et leurs empreintes vérifiées.
  Le [plan d'exécution](PLAN-EXECUTION-MVP-20261103.md) précise l'installation,
  les gates suivants et les recettes physiques non encore réalisées.

## MVP Discord — début D1, 3 novembre 2026
- Un appel TTS et un appel STT OpenAI réels, sans microphone et sans relance,
  ont réussi sur une phrase synthétique ; audio effectif 2,41 s. Durées d'appel
  observées 3,47 s et 2,63 s. Le montant exact n'a pas été relevé.
- Un appel STT supplémentaire sur le même WAV a aussi validé le modèle recommandé
  `gpt-transcribe` (1,25 s et mots attendus). Aucun audio humain n'a été capturé.
- La taille déclarée dans l'en-tête WAV reçu était indéterminée ; la durée a été
  calculée sur les octets PCM effectifs. Aucune écoute ni capture humaine réelle.
- Les modèles de dialogue, TTS et STT actuellement configurés sont annoncés comme
  retirés en 2027. Dates, sources officielles et adaptation nécessaire sont dans
  le [plan](PLAN-EXECUTION-MVP-20261103.md) ; ne pas changer seulement les noms
  de modèles sans vérifier leurs interfaces.

## MVP Discord — premières protections vocales, 3 novembre 2026
- Validation locale de ce lot : 201 tests hors ligne et compilation réussis ;
  scan des modifications préparées sans alerte. Des essais synthétiques couvrent
  notamment la révocation avant et pendant la sortie locale/OBS. L’arrêt effectif
  reste soumis à l’ordonnancement et aux lecteurs ; aucune garantie temps réel.
- Le vocal exige désormais une liste privée de participants autorisés et un
  consentement explicite. Une session distincte est révoquée en cas de changement
  des participants ou de déconnexion ; les travaux et lectures en cours sont
  annulés. Les membres introuvables dans le cache et les bots tiers sont refusés.
- Une réponse vocale est liée à son locuteur, son salon et sa session. La
  rediffusion globale d'autres sources précédemment ajoutée est suspendue en
  attendant un routage autorisé par source et destination, afin d'éviter une
  fuite entre conversations.
- Des briques autonomes de segmentation PCM et de pertinence sans mot d'activation
  sont testées hors réseau mais pas encore raccordées au bridge. Aucun vocal réel
  n'a été testé ; la recette avec les participants informés reste indispensable.

## Reprise Terra — connexions et sécurité, 3 novembre 2026
- Twitch : six anciens jetons distincts refusés par la validation distante. Sur
  accord explicite du propriétaire, nouveau jeton obtenu et validé avec lecture
  et autorisation d'écriture ; aucune écriture dans le chat. Le connecteur
  `TwitchIRC` s'est authentifié et a rejoint le canal configuré en lecture.
  L'ancienne configuration est préservée et la nouvelle configuration complète
  est sauvegardée dans le dépôt privé, avec intégrité vérifiée.
- Discord : le jeton bot a été reconnu ; appartenance au serveur, accès et
  permissions du salon vocal vérifiés par API. Le connecteur Discord du projet a
  atteint l'état prêt sur la passerelle, en présence invisible, puis s'est fermé
  proprement. Aucun message n'a été envoyé et aucun salon vocal n'a été rejoint.
- La diffusion Discord élargie, initialement prévue comme option, a ensuite été
  suspendue : le routage entre sources et sessions doit être sécurisé avant son
  activation. Le transport vocal réel, l'envoi réel de chat et les interactions
  avec les participants restent à recetter séparément.
- Un contrôle spécialisé des secrets sur les pushes et PR, avec historique
  récupéré et autotest synthétique, complète la CI. Les octets Git LFS ne sont
  pas couverts par le scan Git ; voir `docs/gpt6-jade/SECRET_SCANNING.md`.
- À la demande du propriétaire, le renouvellement automatique du nouveau jeton
  est activé dans la configuration privée ; la sauvegarde distante initiale est
  confirmée. Rotation, conflits et pannes sont testés avec des doubles ; aucun
  renouvellement réel du nouveau jeton n'a été déclenché pendant la première
  recette. Après expiration, un renouvellement réel a ensuite réussi : nouveau
  jeton revalidé, sauvegarde distante privée synchronisée et copie locale de
  sauvegarde vérifiée. Aucun message de chat n'a été envoyé.
- Les connexions Twitch et Discord sont autorisées dans la configuration privée,
  mais leur démarrage et l'envoi de messages exigent toujours leurs options
  explicites. Les 134 tests locaux réussissent. Une course d'arrêt Twitch est
  couverte par des tests ; le démarrage et l'arrêt immédiat réels ont été vérifiés
  sans message ni appel payant.

## Contre-revue Astra finale — 2 novembre 2026
- Conservation vérifiée des 324 chemins suivis de la version intégrée et des 103
  objets LFS ; aucun changement runtime/configuration/tests/dépendances dû à la
  migration publique, à fins de ligne près. Les 84 tests et la démo réussissent.
- Scans publics et contrôle des sauvegardes privées réalisés ; aucun secret connu
  détecté. Les limites binaires, deux écarts fonctionnels hérités et le renforcement
  nécessaire du contrôle CI sont décrits dans
  [la reprise Terra](../migration/2026-11-02/08-ASTRA-CONTROLE-DEPOT-PUBLIC.md).
- Aucun correctif applicatif effectué pendant cette passe ; arrêt de la revue et
  poursuite éventuelle sous Terra sur `develop`.

## Consolidation sur une seule branche — 2 novembre 2026
- `main` réunit le moteur, les configurations d'exemple, la documentation et les
  ressources 2D. Les anciennes branches ont été comparées aux sources intégrées ;
  le seul travail divergent restant est documenté dans `docs/archives`, avec ses
  valeurs sensibles retirées, sans réactiver l'ancien runtime expérimental.
- L'historique original et les instantanés antérieurs sont sauvegardés en privé.
  Les secrets actifs restent dans la configuration privée externe au dépôt.
- Le moteur dispose de tests hors ligne ; les fonctions vocales Discord et les
  plateformes connectées restent à valider en conditions réelles. Les choix de
  comportement qui différaient dans l'ancien travail sont signalés dans l'archive.

## Préparation de publication — 2 novembre 2026
- Une copie locale de l'historique a été filtrée pour retirer les configurations
  sensibles connues. Le contrôle de tous ses objets Git accessibles ne retrouve
  aucune des 19 valeurs connues ; un scanner d'historique ne signale rien. Ces
  contrôles ne garantissent pas l'absence de secrets inconnus ou dans les binaires.
- Les 103 objets LFS du HEAD courant ont été vérifiés ; le script de vérification
  des ressources et `git lfs fsck HEAD` réussissent. Un coffre local hors dépôt
  conserve les configurations et une sauvegarde privée de l'ancien historique.
- L'export privé inclut les fichiers nécessaires à une utilisation autonome et,
  sur demande, un portrait existant dont l'intégrité est vérifiée. Les 84 tests
  automatisés et `compileall` réussissent dans la copie assainie ; le portrait et
  l'export ont été vérifiés. Confiance élevée sur ces contrôles locaux.
- Après réécriture distante, la CI Linux a réussi ; la première CI Windows a
  révélé un désaccord UTF-8 / page de codes Windows dans un test de préflight
  exécuté depuis l'aperçu. L'encodage du processus de test a été explicité et
  la reproduction locale initialement en échec réussit. Une nouvelle CI est requise.
- La branche `develop` distante a été réécrite ; deux références de PR anciennes
  subsistent sur GitHub et nécessitent un traitement distinct. Les anciens secrets
  doivent être révoqués après remplacement ; ne pas rendre le dépôt public avant
  traitement des références et caches distants. Le micro physique et la voix
  réelle restent à tester ; une simulation ne les valide pas.

## S0 : audit et choix d'architecture (24 octobre 2026)
- Documentation existante : AGENTS, README, historique partiel, configuration privée et plans du modèle lus.
- Branches : develop, master, handle_stream, elevenlabs-stream, refacto, stream_chat et speechtotext-discord inspectées. Seule la dernière diverge.
- Choix du propriétaire : STT/TTS **OpenAI uniquement** et faible latence prioritaire ; migration hors du modèle/routine originaux.
- CI, moteur et connecteurs : en développement ; aucun service réel ni test de performance effectué.

## S1–S3 : fondations, orchestration et texte (2026-10-24)
- Commit `d8a835b` : branche isolée, décisions STT/TTS OpenAI et Codex handoff.
  `develop` a reçu uniquement une note de coordination et la référence AGENTS.
- Commit `448155b` : `src/jade_runtime/{config,messages,dialogue,orchestrator,openai_services,output}.py`,
  entrée `main.py` en démo hors ligne par défaut, dialogue en Unicode et mémoire
  par plateforme/canal, anti-doublon par ID et queue bornée.
- Commit `d87ad56` : dépendances vocales tierces supprimées du manifeste, extras
  transport/lecture facultatifs, ancien `poetry.lock` 2025 obsolète retiré
  (recréer avant tout déploiement), CI GitHub Actions.
- **Validation observée** : [CI 40096765659](https://github.com/goldaj/jade-ai-vtuber/actions/runs/40096765659)
  `completed: success`, tests unittest offline, compileall et dépendances voix.
- **Confiance : élevée** pour les contrats et la démo hors ligne ; **moyenne**
  pour le chat OpenAI réel (SDK et identifiants non testés via compte) ;
  **nulle** pour fonctionnement voix/micro/twitch en direct à ce stade.
- No API call, no secret transfer, no hardware and no paid charge during validation.

## S4–S5 : OpenAI TTS / STT microphone (2026-10-24)
- `openai_services.py` utilise **OpenAI uniquement** pour les deux directions
  voix : `gpt-4o-mini-tts` (WAV), `gpt-4o-mini-transcribe` (FR).
  Aucun compte sollicité dans Chat, modèles modifiables via configuration privée.
- Sous-titres OBS écrits/effacés en `finally`, audio WAV joué en série via
  `ffplay` optionnel ; pas de promesse de synchronisation phonème-par-phonème.
- Commit `09d654b` : capture micro optionnelle `sounddevice` (lib de matériel,
  **pas une IA vocale**), seuil RMS de silence afin d'éviter les dépenses évidentes
  et transcription via OpenAI exclusivement. Mode `--live --mic --voice` explicite ;
  capture suspendue durant la réponse. Aucun micro utilisé en CI.
- **Validation observée** : [CI 40096886045](https://github.com/goldaj/jade-ai-vtuber/actions/runs/40096886045)
  réussie sur `09d654b`, inclut tests de pipeline voix simulés, seuil RMS et WAV.
- **Confiance élevée** sur contrat du pipeline test mock, **moyenne** sur SDK OpenAI,
  **faible** sur audio PC (ffplay/PortAudio non présents dans l'environnement Chat)
  et **non mesurée** pour latence véritable.

## S6–S8 : Twitch texte, VTube Studio, Discord texte (2026-10-24)
- `3657607` : adaptateur IRC **TLS** Twitch avec réponse PING/PONG,
  lecture des PRIVMSG, `id=` transport, reconnexion et envoi opt-in limité ;
  `discord.py` utilisé seul, accès au chat de serveurs uniquement, sans DMs
  ni propagation des mentions par défaut. Import tiers au moment de l'usage.
- `fb39399` : VTube Studio WebSocket **localhost seulement**, authentification
  par token privé, déclenchement de hotkey explicitement configurée ;
  aucune modification du rig/Cubism ou du package r20.
- `cacce60` : `main.py` `--live --twitch/--discord/--vts` avec activation explicite
  de chaque plateforme et envoi dans les chats **désactivé par défaut**.
  Mise à jour du README et commandes pour installation des extras.
- **Validation observée** : [CI 40097290324](https://github.com/goldaj/jade-ai-vtuber/actions/runs/40097290324)
  `success` ; tests automatiques hors-ligne parser Twitch, Discord et simulateur
  WebSocket VTS. **Aucune connexion réelle** aux plateformes.
- **Confiance élevée** sur parsers et garde-fous, **moyenne** sur compatibilité
  des services réels. IRC Twitch ne couvre pas EventSub, et son OAuth doit être
  testé sur un vrai compte.

## S9 : Discord vocal expérimental (2026-10-24)
- `2614d4d` : `discord_voice.py` réécrit sur le transport
  `discord-ext-voice-recv` (PCM brut et **aucun autre moteur STT/TTS**),
  paquets par auteur, limite 12 usagers/8 paquets, 2 secondes par segment,
  filtrage des silences avant appel OpenAI, partage de la queue Jade.
  Extension `discord-voice` facultative, permissions explicitement activées.
- `d03cdc8` : `main.py --live --discord --voice --discord-voice`,
  la voix IA OpenAI peut être rejouée dans le canal (même WAV) ; sous-titres
  restent valables. Fonction désactivée par défaut et consentement des
  participants exigé dans README. Pas d'enregistrement persistant par le bridge.
- **Validation observée** : [CI 40097552037](https://github.com/goldaj/jade-ai-vtuber/actions/runs/40097552037)
  réussie sur `d03cdc8`, test PCM stéréo et STT *mock*.
- **Confiance moyenne** sur les contrats Python / protection mémoire ;
  **faible** sur la capture vocale Discord et la synchronisation lecture réelle,
  car aucune session Discord, codec, permissions ni périphérique testés.
- Remarque : la segmentation fixe 2 s est une base expérimentale. Séparation
  robuste des tours et gestion des interruptions demandent un vrai essai audio.

## S10 : API texte locale préparatoire pour téléphone (2026-10-24)
- `20045dc` : `src/jade_runtime/local_http.py` POST /message,
  `Authorization: Bearer`, token privé >= 32 caractères, taille limitée, accès
  strictement `127.0.0.1`, aucun CORS/public LAN. Retour asynchrone de la
  réponse du vrai dialogue Jade, aucune clé exposée. Pas de paiement en tests.
- `da2b4b6` : interface `main.py --live --http` opt-in et README.
  **Ne prétend pas fournir un accès réseau direct du téléphone** :
  tunnel sécurisé/TLS nécessaire pour une autre machine.
- **Validation observée** : [CI 40097757946](https://github.com/goldaj/jade-ai-vtuber/actions/runs/40097757946)
  réussie sur `da2b4b6`, tests TCP loopback/jeton et champs non autorisés.
- **Confiance élevée** sur HTTP local contrôlé, **faible** sur intégration
  téléphone réelle sans tunnel/TLS et UI dédiés.

## S11 : nettoyage de l'ancien runtime (2026-10-24)
- `ebc202a` : **16 anciens modules supprimés**, y compris ElevenLabs,
  SpeechRecognition, vieux Discord VoiceClient/ffmpeg, TwitchIO et le consumer
  2025 ; historique Git et sources LFS restent intacts.
- `prompt_chat.txt` actualisé sans références obsolètes aux services ou aux
  faux états de fonctionnalité. `credentials.py` tolère les IDs Discord absents.
- `docs/gpt6-jade/LEGACY-AUDIT.md` détaille les modules supprimés et
  les équivalents. Nouveau contrôle empêchant une dépendance TTS/STT tierce
  de revenir dans le paquet actif.
- **Validation observée** : [CI 40097862020](https://github.com/goldaj/jade-ai-vtuber/actions/runs/40097862020)
  `success`, suite unittest + compileall + audit des dépendances.
- **Confiance élevée** sur absence de dépendance alternative et compilation ;
  **moyenne** pour les interactions externes non testées en vrai.
- `poetry.lock` historique retiré, le verrou de dépendances devra être
  régénéré et audité sur le PC avant une installation contrôlée/déploiement.

## Passation et clôture du chantier GPT-6 Chat (2026-10-24)
- `f529d70` : guide complet `HANDOFF.md`, priorités Codex
  `NEXT-PRIORITIES.md`, README refondu, note de coordination synchronisée,
  test smoke CLI sans clé OpenAI.
- **CI du dernier commit de code + documentation** :
  [40098104186](https://github.com/goldaj/jade-ai-vtuber/actions/runs/40098104186)
  `completed: success` au commit `f529d70` (installation editable, compilation,
  suite unittest, contrôle dépendances, démo hors ligne).
- **PR brouillon** :
  [#1](https://github.com/goldaj/jade-ai-vtuber/pull/1), cible `develop`,
  **ni fusionnée ni déployée**.
- `develop` contient uniquement la note de coordination Codex et le lien
  depuis AGENTS ; aucune source runtime changée dans `develop`.
- Codex doit encore valider environnement Windows, lock Poetry, API facturées,
  microphones/audio, OAuth Twitch, API Discord, VTube Studio et téléphone sous
  TLS/VPN. **Confiance élevée** sur tests hors ligne ; **faible/moyenne** sur
  intégrations externes non vérifiées.
- Répertoire `jade-modeling/**` et ses versions r20/r21/Git LFS inchangés.

## S12 : prototype d'interface web locale et sessions séparées (2026-10-24)
- Page de chat HTML/CSS/JS servie par le serveur loopback `GET /`, sans framework ni jeton embarqué.
- Saisie manuelle du jeton, conservé en mémoire JS uniquement ; aucune
  persistance du token ou des messages, texte injecté via `textContent`.
- `POST /message` accepte désormais une session opaque optionnelle (ASCII
  [A-Za-z0-9_-], longueur 1 à 64), sans casser les anciens clients.
- Chaque session possède son propre historique `Dialogue`; le bouton Nouvelle
  discussion en ouvre une nouvelle. Tests HTTP hors ligne couvrant isolation,
  validation et livraison de la page.
- **Limite** : GET n'est accessible que via 127.0.0.1, accès téléphone exige
  toujours tunnel HTTPS/VPN et authentification, non réalisés dans Chat.
- Validation CI : consulter l'exécution liée au commit HEAD de cette étape.

## S13 : diagnostics hors ligne et recette de connexion privée (2026-10-24)
- `src/jade_runtime/diagnostics.py` et `main.py --preflight` contrôlent la
  configuration sélectionnée et les dépendances locales sans appeler OpenAI,
  Discord, Twitch, VTube Studio, ni capturer un microphone.
- 7 tests unitaires couvrent les conditions d'activation, secrets masqués et
  préflight CLI ; résultats à vérifier sur le commit HEAD en CI.
- `PHONE_TAILSCALE.md` donne une procédure **manuelle** pour un tunnel HTTPS
  restreint au tailnet, avec contrôle des ACL et commande d'arrêt ; aucune
  exposition réseau n'a été configurée depuis Chat.
- Les appels réels OpenAI, le micro Windows, le son, Discord, VTS et l'accès
  physique au téléphone restent **non validés** à ce stade.

## S14 — Audit préparatoire de migration (2026-11-02)

- Dossier [migration du 2 novembre](../migration/2026-11-02/README.md), carte des neuf branches, traitement des anciennes branches, plan par lots et relais manuel Astra puis Terra.
- Baseline source research `df544ed` ; develop distant `6420e24`, six commits documentaires supplémentaires. Aucun merge exécuté.
- Validation locale Windows/Python 3.11 dans venv neuf : **51 tests OK**, compilation, diagnostic, démo `/exit`, `pip check` et préflight statique **109 fichiers** réussis.
- Huit défauts reproduits avec doubles synthétiques ; quatre constats supplémentaires de code/contrat/tests. Aucun correctif runtime appliqué, travaux différés conformément à la demande.
- CI SHA exact toujours failure, jobs sans runner ni étape ; cause inconnue. Aucun essai réel de compte/API/appareil, aucun LFS téléchargé, aucune recette 2D.
- Confiance élevée sur graphe, tests locaux et reproductions ; limitée sur intégrations réelles, endurance et première mise en service. Le propriétaire confirme l’absence de production active. Journal : [index](../conversations/INDEX.md).

## S15 — Contre-lecture Astra (2026-11-02)

- Plan validé avec [précisions d’exécution](../migration/2026-11-02/06-ASTRA-REVIEW.md) : arrêt global avant fermeture du TaskGroup, capture physique, lecteurs frères, résultats HTTP/échéances, sessions, connexions Discord et séquence push/CI/merge.
- Neuf références distantes inchangées, PR #2 ouverte en brouillon ; huit reproductions rejouées, défauts toujours présents. Les 51 tests de S14 ne sont pas présentés comme réexécutés.
- Aucun correctif runtime, merge ou push ; reprise Terra prête. Installation verrouillée, CI finale et essais live restent à effectuer dans les lots prévus.

## S16 — Corrections de l’intégration Terra (2026-11-02)

- Merge local `f44a7fb` : documentation supplémentaire de `develop` conservée, aucune modification d’asset. Branche `codex/jade-runtime-integration-20261102`.
- Arrêt immédiat/gracieux borné, admissions fermées, expiration HTTP, limites de connexions et sessions ; nettoyage à l’échec du démarrage et tests d’arrêt applicatif. Les délais ne prouvent pas l’arrêt d’un pilote ou d’une bibliothèque qui refuse l’annulation.
- Capture à propriétaire unique et coordination micro/parole ; annulation ffplay et lecteurs frères ; sorties texte isolées des échecs de voix. Surcharge Twitch/Discord, mentions Discord, initialisation et buffers vocaux corrigés.
- Préflight complété ; CI préparée pour Windows/Linux ; verrou Poetry 2.2.1 généré et installé sur Windows en environnement isolé avec extras Discord, voix, micro et VTS. Aucun matériel réel testé.
- Vérification locale observée : **79 tests hors ligne OK**, compilation et démo CLI ; `poetry check --lock` et `pip check` réussis. Ne constitue pas une preuve CI distante ni une recette de service.
- Limites : navigateur déconnecté non détecté immédiatement en attendant HTTP ; fermeture d’une bibliothèque native résistante et audio matériel non certifiés. Consentement vocal, salons Discord, budget, tokens et essais des services nécessitent une recette réelle distincte.
- Premier candidat `53f6fdf` : CI GitHub Windows/Linux et contrôle publication réussis ; le diagnostic runner est redevenu fonctionnel, sans cause historique identifiée. Le propriétaire choisit une recette texte/voix/micro à budget minimal. Préflight du poste : clé OpenAI absente ; lecteur ffplay existant reconnu en ajustant le PATH du processus ; aucun matériel ou appel API testé. Un changement documentaire ultérieur requiert à nouveau une CI sur son propre commit.
- Candidat `b890eff` : CI GitHub Windows/Linux et hygiène réussies, y compris sur la PR. Aucun fichier `.env` actif n’a été retrouvé dans le clone ou le coffre prévu ; une valeur OpenAI présente dans l’historique privé a été authentifiée par une simple lecture de métadonnées de modèle, sans génération ni sortie de valeur. Entrée et sortie audio détectées, sans capture ni lecture. Le propriétaire préfère réaliser l’essai micro plus tard ; ne pas le lancer automatiquement. Reprise : [recette et intégration restantes](../migration/2026-11-02/07-REPRISE-RECETTE.md).

## S17 — Simulation micro et essai texte (2026-11-02)

- À la demande du propriétaire, deux scénarios hors ligne utilisent du PCM synthétique et simulent périphérique et SDK : pipeline capture→STT→dialogue→TTS→lecteur et absence d’appels en cas de silence. Les sept tests de sécurité audio passent également. Cela ne valide aucun périphérique ni aucune API vocale réelle.
- Suite complète locale : **81 tests OK**. Un essai texte via le runtime puis un diagnostic direct ont été refusés par OpenAI : HTTP 429 `credit_balance_exhausted`. La lecture des métadonnées de modèle ne prouve pas que le compte peut payer une génération ; aucune réponse texte réelle n’a été obtenue.
- Le propriétaire recharge son compte et préviendra pour reprendre. Ne pas répéter l’appel facturé avant son message ; ensuite retester le texte, vérifier CI et SHA puis fusionner la PR conformément à sa demande. La recette micro simulée est acceptée comme incomplète ; ne pas annoncer une validation physique.
- Après confirmation du propriétaire, une seule génération texte réelle via `gpt-4.1-mini` et le runtime Jade a réussi : réponse correcte en 1,72 s. La requête était synthétique, sans micro ni transcription réelle. Le propriétaire autorise la fusion après cette recette incomplète ; vérifier les checks du SHA final et conserver les limites de la simulation.
