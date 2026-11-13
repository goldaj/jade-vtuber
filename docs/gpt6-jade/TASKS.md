# Compte rendu des étapes

Chaque lot doit indiquer : livrable, validation observée, limites et niveau de confiance,
sans présenter les mocks comme des tests d'API réels.

## Évolution demandée le 13 novembre — texte Discord et personnalité

- Participation spontanée rehaussée de **15 % à 30 %**, délai minimal
  conservé de trois minutes par salon, sans appel LLM pour la lecture passive.
- Le prompt standard de Jade présente Goldaj comme son père dans l'univers du
  personnage et autorise des marques d'affection timides et rares ainsi que
  l'appellation « papa » ponctuelle, exclusivement pour Goldaj. Le chargement
  du prompt externe préserve cette relation sans écraser le prompt privé.
- Tests de cohérence ajoutés. Les résultats CI du **dernier commit** doivent
  être vérifiés avant fusion ; aucune preuve de fonctionnement Discord réel
  ou de relance du processus PC n'est établie par la fusion GitHub.

## Chantier isolé — participation écrite Discord (13 novembre 2026)

- Branche `feat/discord-text-contextual-20261113` depuis `develop` après
  confirmation de la fusion de la PR #1 (streaming vocal).
- Lecture passive en mémoire bornée par salon ; mentions directes et fils de
  réponse, relances du même auteur après envoi réussi, questions spontanées
  limitées par probabilité et cooldown. La voix existante reste distincte.
- Paramètres : `JADE_DISCORD_TEXT_AUTO_RATE=0.30` (0 pour désactiver
  l'initiative) et `JADE_DISCORD_TEXT_COOLDOWN_SECONDS=180`.
- Tests unitaires hors ligne ajoutés ; le résultat CI du dernier SHA doit
  être vérifié avant toute fusion. Pas de recette Discord réelle ni d'appel
  facturé dans cette intervention.
- Passation complète : [Discord texte](HANDOFF-DISCORD-TEXT-20261113.md).
  `develop` et `main` restent inchangées.

## Intégration Terra / GPT-6 — streaming vocal (13 novembre 2026)

- Fusion du chantier parallèle : PCM Discord par blocs, connexion TTS Realtime
  réutilisée et mode optionnel de réponse par phrases. Le flux de phrases garde
  une seule lecture Discord continue, avec un maximum de six segments par réponse.
  Le réglage de débit `JADE_TTS_SPEED` vaut 1,5 par défaut et accepte 0,25–1,5.
- Corrections de l'intégration : maintien des commandes « silence » chevauchant
  la fin de lecture, données PCM découpées sur un octet, file de phrases qui ne
  boucle pas si la lecture s'arrête, annulation et fermeture bornée du WebSocket,
  historique prudent après interruption, hotkey VTS déclenchée avec la première
  phrase sans attendre la réponse entière.
- Essai API réel court, hors Discord et sans microphone : génération de texte par
  flux réussie ; deux synthèses PCM ont confirmé le réglage ×1,5 et la réutilisation
  du même WebSocket. Premier PCM observé après 3,28 s à froid puis 0,88 s pour
  l'appel suivant. Exemples isolés, pas une comparaison avant/après ni une
  mesure de la latence entendue sur téléphone. Coût exact non mesuré.
- Sur le code d'intégration : **391 tests hors ligne réussis** et compilation
  Python réussie sous Windows. Sur le merge `4ee1879`, les vérifications
  [Windows/Linux](https://github.com/goldaj/jade-vtuber/actions/runs/43415450313)
  et le [scan de secrets](https://github.com/goldaj/jade-vtuber/actions/runs/43415450337)
  ont réussi. Ces résultats ne sont pas attribués à un autre commit.
- Aube reste la voix souhaitée : aucun identifiant API Realtime compatible n'a
  été confirmé dans les sources officielles consultées. Le timbre existant est
  conservé ; Brise est une voix de l'API Live distincte, sans équivalence établie.
  Voir le [plan initial](PLAN-LATENCE-20261110.md).
- La recette téléphone, le résultat du partage d'écran et le gain perçu sont à
  constater avec le propriétaire ; le mode phrases peut être désactivé avec
  `JADE_EARLY_VOICE=0` si besoin.
- Le travail GPT-6 et le checkpoint Terra sont présents dans l'historique de
  `develop` ; la branche distante GPT-6 et la branche locale temporaire ont été
  supprimées après vérification de leur intégration. `main` n'a pas été fusionnée.
- Lors du lancement demandé, le processus Jade est actif, le bot est connecté au
  vocal Discord et une fenêtre « Jade — modèle animé r20 » est présente. Ce
  lancement utilise le mode phrases et le débit 1,5. Le partage automatique n'a
  pas été engagé : la capture de la fenêtre Discord a expiré après nouvelle
  sélection. Le compte PC était connecté ; partager manuellement la fenêtre
  Jade depuis Discord pour l'essai téléphone. La présence d'une fenêtre ne prouve
  ni son contenu visible ni une transmission vidéo réussie.

## État courant — voix rétablie et relais latence (10 novembre 2026)

- Panne réelle DAVE corrigée par le verrou `davey==0.1.7` avec `discord.py==2.7.1` :
  la version 0.2.0 exige des transitions de clés absentes de ce consommateur.
  Le propriétaire confirme maintenant que Jade répond depuis son téléphone.
- Validation après changement de dépendance : **330 tests hors ligne réussis**,
  compilation, cohérence du lock Poetry et `pip check` réussis. Les résultats CI
  antérieurs ne sont pas attribués au nouveau commit ; consulter ses checks GitHub.
- Nouveau [portrait r21](../../assets/branding/README.md) appliqué au profil du bot
  Discord, puis confirmé par relecture API. Sources artistiques préservées.
- Le propriétaire a vu le modèle bouger en local. Le rendu essayé est r20 dans
  sa fenêtre autonome ; VTube Studio est installé mais son connecteur n'est pas
  configuré dans l'environnement actif. Partage vidéo téléphone différé, dernière
  session Discord PC contrôlée encore à reconnecter. Procédure et limites dans
  le [guide avatar](UTILISATION-AVATAR-DISCORD.md).
- Au contrôle de clôture, aucun processus temporaire Jade de diagnostic encore
  actif ; pas de nouvelle écoute ni appel OpenAI lancé pour cette documentation.
  VTube Studio et les services sans rapport sont laissés dans leur état.
- [Plan de réduction de latence](PLAN-LATENCE-20261110.md) prêt : mesures simples,
  PCM progressif, connexion TTS durable, puis texte par phrases. Développement
  à attendre sous Terra. Confiance élevée sur le tamponnement observé dans le
  code ; gain chiffré, coût final et synchronisation téléphone non mesurés.
- Complément du 13 novembre : demande de voix française Aube et vitesse ×1,5
  intégrée au lot A bis du plan. Aube est documentée dans ChatGPT, sans identifiant
  API confirmé pour Jade ; Brise appartient à l'API Live, sans équivalence
  démontrée. ×1,5 est pris en charge par Realtime mais reste à implémenter sous
  Terra. Aucun changement de voix/vitesse ni appel vocal effectué pour ce complément.

## MVP Discord — étape 1 : moteur OpenAI
- Moteur principal : dialogue `gpt-6-luna`, STT `gpt-transcribe` et TTS Realtime
  `gpt-realtime-2.1-mini` par défaut. Anciennes configurations explicites conservées ;
  code vocal partagé avec la démo, client isolé et relances automatiques coupées.
- Suite complète : 289 tests hors ligne réussis. Installation neuve sur D: issue
  du lock : OpenAI 3.42.1 et WebSockets 15.0.1, sans extra VTS. Essai réel court
  sur ce lock : texte 2,20 s, voix 4,80 s, transcription synthétique 0,83 s.
  Trois appels ; coût exact non mesuré. Aucun micro humain ni haut-parleur utilisé.
- Clés et fichier privé inchangés. Les réglages de modèle étaient absents du
  fichier privé et de l'environnement vérifiés : les nouveaux défauts s'appliquent.

## Démo Windows animée — 9 et 10 novembre 2026
- Démo en préparation avec exécutable, installateur par utilisateur et guide :
  modèle Live2D r20, mouvement d'attente, sept expressions, retour neutre et
  ouverture de bouche liée au niveau audio. La clé OpenAI du visiteur reste en
  mémoire ; aucune clé n'est fournie. Le r21 n'est pas un export final validé.
- Le 9 novembre, courts essais réels `gpt-6-luna` et `gpt-realtime-2.1-mini`,
  puis chemin intégré texte→dialogue→voix WAV réussis sur entrée synthétique ;
  le coût exact n'a pas été relevé. Le même jour, une sortie audio silencieuse
  a été écrite vers PortAudio. Pas de micro, d'écoute humaine ou de transcription
  réelle de voix humaine. `gpt-transcribe` avait été essayé sur audio synthétique.
- Le 10 novembre, 282 tests hors ligne et compilation réussis. Le rendu OpenGL
  hors écran du modèle r20 a affiché sept images d'expression distinctes ; des
  paramètres de visage contrôlés sont revenus à leur valeur initiale après remise
  au neutre. Ces contrôles ne constituent pas une recette visuelle ou audio humaine.
- Le 10 novembre, l'installateur a été installé puis désinstallé dans un dossier
  de recette isolé sur D:. Les 2 705 fichiers installés correspondent au stage ;
  imports, interface, première frame et renderer fonctionnent avec un PATH
  Windows minimal. Les commandes des sept expressions, du neutre et de la bouche
  ont été acceptées par le renderer installé. La capture de fenêtre a expiré :
  le contrôle visuel humain et la recette sur un autre PC restent ouverts.
- Scan Gitleaks sans alerte sur le stage ; aucune des neuf valeurs privées connues
  ni des variantes de chemin recherchées dans les fichiers et modules PyInstaller
  décompressés en mémoire. Ce contrôle ne garantit pas l'absence de secrets inconnus.
  ZIP : SHA-256 `e1d09bb0a48d5dc7a2017bfe5a7c08f8adbb79cc41aaa9b1192863fc9bece0e0`.
  L'installateur n'est pas signé numériquement.
- La démo ne configure pas Twitch ou Discord ; les modèles du runtime principal
  restent à migrer indépendamment de ceux de la démo.

## Démo Windows autonome — 3 novembre 2026
- Archive locale avec exécutable Windows, portrait statique r21 et ressources
  du modèle r20. Dialogue simulé hors ligne : aucune IA, voix ou animation.
- Exécutable extrait testé avec PATH minimal, sommes du paquet vérifiées, scans
  ciblés sans alerte ; 203 tests locaux et compilation réussis.
- Capture visuelle de la fenêtre expirée ; rendu visuel et VTube Studio non
  recettés. Documentation et empreinte dans [la notice](../../demo/windows/README.md).

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

## MVP Discord — raccordement vocal D2, 3 novembre 2026
- Le bridge regroupe les tours, applique la pertinence en session privée et
  transmet seulement les tours acceptés. Les participants réels sont figés ;
  une incohérence de snapshot révoque la session, y compris pendant la sortie.
- Revue indépendante : correction des courses de changement de participants,
  d'arrêt, de sortie et de nettoyage des sous-titres ; files, tailles et
  demi-duplex contrôlés. 219 tests hors ligne et compilation réussis.
- Pas de validation audio humaine, Discord vocal réel ni caméra ou téléphone.
  Seuils acoustiques expérimentaux ; groupe silencieux et pas de barge-in oral.
  Le cache Discord et l'arrêt des lecteurs ne sont pas atomiques ou temps réel.

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
- La segmentation PCM et la pertinence sans mot d'activation sont désormais
  raccordées au bridge et testées sur audio synthétique. En tête-à-tête une
  phrase pertinente peut recevoir une réponse sans nom ; en groupe, faute de
  signal fiable d'adresse directe, le mode reste silencieux. Le demi-duplex ne
  permet pas l'interruption orale pendant la réponse. Aucun vocal réel n'a été
  testé ; la recette avec les participants informés reste indispensable.

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

## S18 — Moteur et préparation du vocal Discord (2026-11-10)

- Le moteur principal utilise les modèles et le transport TTS Realtime partagés avec la démo ; dialogue, synthèse et transcription ont été essayés séparément avec un signal synthétique et un budget minimal. Aucun microphone physique n'a été utilisé.
- Le parcours vocal Discord accepte les personnes et les autres bots sans liste ni confirmation ; seule la propre voix de Jade est ignorée. Il suit son déplacement dans un autre salon, une connexion vocale à la fois. Les réponses issues d'autres sources peuvent aussi être diffusées dans le salon actif.
- La réception prend en charge le chiffrement DAVE avec les versions verrouillées du transport. Des essais synthétiques couvrent notamment les déplacements, les reconnexions et la continuité de l'écoute après une réponse. Une connexion vocale réelle puis une déconnexion propre ont réussi, sans écoute, émission ni appel OpenAI. La réception audio DAVE réelle et la conversation humaine restent à recetter.
- Travail sur `develop` uniquement ; `main` reste inchangée. Ne pas confondre ces vérifications avec une validation du téléphone, de l'audio physique ou de la synchronisation de l'avatar.
- Validation hors ligne de cette étape : 319 tests réussis et compilation Python réussie. Le scan de secrets du contenu préparé a réussi ; ces contrôles ne remplacent pas une recette audio réelle.

## S19 — Avatar r20 pour le MVP Discord (2026-11-10)

- Option `--avatar` : fenêtre Live2D r20 existante et mouvement de bouche approximatif lié au volume pendant la lecture locale ou Discord, arrêt au repos ; pas de synchronisation phonétique revendiquée. Le processus graphique ne reçoit ni clé, ni transcription, ni audio.
- Le modèle s'est lancé lors d'un essai graphique local caché. Installation neuve sur D: des extras verrouillés Discord vocal et avatar, imports et `pip check` réussis ; 37 tests ciblés de transport et d'avatar réussis dans cet environnement.
- Procédure et partage manuel de fenêtre : [utilisation de l'avatar Discord](UTILISATION-AVATAR-DISCORD.md). La perception de la synchronisation, le partage réel, le téléphone et la conversation vocale bout en bout restent à recetter ; r21 demeure distinct.
- Validation globale de l'état préparé : **328 tests hors ligne**, compilation, contrôle LFS et 202 fichiers du manifeste réussis. Préflight complet avec la configuration privée réussi sans appel ; connexion Discord réelle et intent des messages vérifiés séparément sans capture ni message envoyé. Scan Gitleaks et comparaison ciblée aux valeurs privées connues : aucune fuite détectée dans les modifications préparées. Une recherche ne garantit pas l'absence absolue de secrets.

## S20 — Silence vocal et lancement pour recette distante

- La commande d'arrêt peut être transcrite pendant la lecture ; les autres phrases entendues durant la lecture ne déclenchent pas de dialogue. L'état silencieux bloque aussi les sorties vocales d'autres sources jusqu'à « reprends », tout en gardant les sorties texte et la connexion.
- Suite locale : **330 tests hors ligne réussis** ; compilation Python réussie. Les scénarios d'arrêt et de reprise sont simulés ; pendant la lecture, la détection d'arrêt utilise OpenAI STT et son coût ainsi que l'écho restent à mesurer en conditions réelles.
- Lancement demandé par le propriétaire depuis son téléphone : runtime local avec Discord vocal, avatar r20 et option Twitch ; connexion vocale Discord et fenêtre de l'avatar constatées. La conversation, le son perçu et le partage du modèle vers le téléphone restent à recetter. Le compte Discord du PC demande une reconnexion avant le partage de fenêtre.
