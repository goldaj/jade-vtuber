## PWA · Config épurée et préférences conservées (27 novembre 2026)

- L’onglet **Config** remplace Profil. **Paramètres** contient le sélecteur **Modèle** puis les cases **Mode Live**, **Voix activée**, **Animations de la chambre**, **Réagir aux secousses** et **Recevoir les rappels sur ce téléphone**. Les paragraphes permanents demandés sont retirés ; les erreurs utiles restent visibles.
- Les réglages de voix, notifications, modèle, décor, animation, secousses et filtre des logs sont sauvegardés automatiquement sur ce téléphone. Les changements de modèle/décor ne sont conservés qu’après réussite ; leur indisponibilité temporaire n’efface pas un choix précédent. Live conserve sa préférence serveur. Le micro et les sessions audio ne redémarrent jamais au rechargement.
- **Décor** et **Recentrer** disposent d’un bandeau propre au-dessus de la scène de l’Accueil. Le bandeau disparaît dans les mini-scènes et en plein écran. Les boutons du salon, de connexion et de secours affichent un état enfoncé à l’appui.
- Le suivi OpenAI ne présente que les dépenses du jour/mois, la dernière actualisation et le lien de facturation. **Gestion GIT de la branche develop** conserve les actions et logs ; actualisation et défilement des logs sont automatiques. **Associer un compte** conserve les trois étapes dans les termes demandés.
- [Passation et vérifications](../operations/handoffs/2026-11-27-chatgpt-mobile-config.md). Les essais physiques Redmi/OpenAI des recettes existantes restent distincts de ces vérifications d’interface.

## Live mobile intégré sur develop (26 novembre 2026)

**Présent dans `develop`, depuis le lot `90ec0c7` issu de `feat/live-mobile-20261126`.** Le propriétaire autorise l’intégration le 26/11 pour effectuer son test mobile. La mise à jour concurrente `b4a85e8` (DEV-053 / ART-014) est conservée ; les recettes réelles restent ouvertes. [Architecture](../architecture/LIVE_MOBILE.md) · [passation et preuves](../operations/handoffs/2026-11-26-chatgpt-live-mobile-implementation.md).

- Live est sélectionné par défaut sur mobile, sans plafond financier. Config conserve le choix Live/classique côté serveur. Sur Accueil et en plein écran, un appui sur le micro démarre la capture et le suivant la coupe. La pastille est rouge pendant la connexion ou l’échange avec le micro ouvert, bleu foncé en veille avec le micro ouvert et bleu clair dès la coupure du micro. Elle est ancrée en haut à droite de la scène dans toutes les vues. Seul l’Accueil fenêtré affiche le mot « Live ». Le classique garde son appui maintenu.
- Audio Live WebRTC avec pré-roll local, bail exclusif, contrôle heartbeat et watchdog ; arrêt fort au changement de fil/modèle, texte, son OFF, arrière-plan, perte de contrôle ou durée. Idle ferme seulement la génération fournisseur ; aucune reprise de capture après un arrêt fort.
- Fermeture fournisseur suivie jusqu’au terminal ou à l’état inconnu. La demande explicite de reprise peut retirer une ancienne génération connue dont le bail est révoqué et la fermeture tentée, avec l’usage final conservé comme indéterminé. La création ambiguë sans identifiant reste bloquante. Une erreur SQLite ne bloque pas la demande de clôture. Le mode classique reste disponible si Live est indisponible.
- Même persona, histoire, mémoire et outils Jade ; délégations dans le worker/arbitre existant, effets idempotents et curation différée. Aucun budget financier mobile ne conditionne ces opérations. Le dialogue oral natif Live peut se dérouler pendant un tour d'un autre canal.
- Chat par segments, pièces jointes privées et états de lecture explicites. Le lecteur WebRTC joue la voix distante et un analyseur synchronise la bouche et la motion de réponse de l’avatar. Les tours natifs peuvent choisir un mouvement r21 à partir d’indices dans la transcription. Les réponses déléguées reprennent l’intention réelle du moteur de dialogue. Le graphe Web Audio reprend la sortie si la lecture du lecteur est refusée.
- Usages cumulés et métriques passifs, sans plafonds quotidiens/mensuels ni arrêt pour dépense. Les anciennes variables de montant Live sont ignorées. Une panne du suivi d'usage ne désactive pas le mobile ; le registre de sessions et le journal métier restent nécessaires. Coûts backend incomplets explicitement identifiés. La politique Discord ci-dessous reste indépendante du mobile.
- Config explique les indisponibilités et les erreurs de chargement ; les refus fournisseur distinguent authentification, accès au modèle, quota fournisseur et connexion, sans publier de contenu privé.
- Friponne est la voix enregistrée choisie par le propriétaire. `JADE_LIVE_VOICE_STYLE=friponne` et son identifiant privé sélectionnent ce profil sur mobile et Discord Live. Jade parle dans un registre aigu avec un accent francilien. La consigne lui demande d’enchaîner les mots un peu plus vite et de ménager une courte pause avant une pique. Pétillante reste disponible avec son propre profil. Brise est la voix de départ du catalogue.

**Correctif de reprise du 27/11 (DEV-055) :** permissions d’événements serveur au format objet conforme à l’API, validation avant réseau et contrôle par le SDK officiel dans le test du corps HTTP. Le message de fin de réponse disparaît dès l’arrêt ; les diagnostics restent visibles. Le kit vocal ne mentionne plus de budget mobile. [Preuves](../operations/handoffs/2026-11-27-chatgpt-live-resume.md).

**Suivis :** sept développements transférés en REC-044 à REC-050, À valider, avec tests automatisés et recette OpenAI/Redmi restante. [REC-052](../backlog/02-RECETTE.md#rec-052--voix-friponne-avec-lavatar-de-jade-ancienne-dev-041), ancienne DEV-041, suit l’essai de Friponne avec r21. La demande complémentaire du 27/11 engage l'automatisme Discord ci-dessous.

## Discord Live automatique et commande manuelle (27 novembre 2026)

- `src/jade_runtime/discord_config.py`, **`DISCORD_ENABLED = True`** : Discord écrit et vocal disponibles dans le lancement habituel, avec choix automatique Live/classique. **`False`** : tous les transports Discord sont désactivés, même avec `--all-channels` ou les options Discord explicites. Redémarrage requis ; anciens flags privés Discord ignorés.
- Total API du mois civil Europe/Paris : toutes les lignes OpenAI de l'organisation, tous produits/projets/canaux, plus l'usage du compte Tavily configuré, convertis en EUR avec une source de change datée. Rafraîchissement toutes les cinq minutes et contrôle local pendant la voix.
- Seuil **50 EUR** si les données monétaires sont complètes avec une couverture explicitement fraîche ; **40 EUR** pour les relevés estimés standard. Données essentielles indisponibles ou devenues trop anciennes : classique avec motif. Seuil atteint : classique jusqu'au mois suivant, verrou persistant après redémarrage. Les limites du reporting ne permettent pas de garantir une facture finale plafonnée.
- Primaire WebSocket Live avec PCM natif en solo ; en groupe, STT et règles de participation existantes avant l'envoi cadencé du tour admis. Sortie sur Discord, mémoire/histoire/outils communs avec identité de transport vérifiée et pièces jointes dans le texte du vocal.
- Fermeture sur seuil, présence, canal, déconnexion ou arrêt ; les états incertains sont persistés et ne provoquent aucun replay automatique de l'énoncé en classique. Aucune nouvelle capture/session payante au simple démarrage du bot.
- **Config → Suivi Discord** affiche les minutes GPT-Live observées pour le mois civil Europe/Paris. **Activer GPT-Live sur Discord**, coché par défaut et mémorisé côté serveur, autorise la politique automatique. Décocher coupe la session et empêche une nouvelle ouverture Live. La prochaine parole admissible utilise alors le classique. La sortie vocale est réservée au moteur Live tant que sa session la détient. L’arrivée dans le salon vocal ne déclenche plus de salut.
- Aucun budget financier mobile, aucune modification de sa préférence ni fermeture mobile du fait de cette politique. La consommation mobile contribue seulement au total observé pour Discord.

**Suivi : DEV-052 → REC-051, À valider.** Code et tests automatisés livrés ; audio réel, accès des comptes et comportement Discord/Redmi restent à observer. [Architecture](../architecture/DISCORD_LIVE.md) · [Passation et preuves](../operations/handoffs/2026-11-27-chatgpt-discord-auto-live.md).

## Contrôle distant PyCharm sur develop (24 novembre 2026)

Le contrôleur privé Windows et le superviseur de processus PyCharm Run remplacent le déploiement mobile par changement de branche. Le mode Debug n'est plus pris en charge dans cette configuration, et la branche develop est fixe pour les mises à jour. Log live et page de secours disponibles via Tailscale Serve /control ; tâche à l'ouverture de session et raccourci invisible prévus. **Intégré sur develop ; redémarrage simple confirmé, mise à jour à recetter.** Le fast-forward conserve les modifications locales non conflictuelles, refuse les écrasements et expose les erreurs Git, le SHA distant du dernier fetch et le résultat distinct du redémarrage. Voir [guide](../operations/reference/REMOTE-PYCHARM-CONTROL-20261123.md).

# État de develop — fonctionnalités codées

## PWA · Décors interchangeables Chambre/Cuisine (22/11/2026)

- Le bouton « Décor », disponible **uniquement dans l’Accueil fenêtré**, permet de choisir **Chambre** ou **Cuisine**, sans remonter le modèle Live2D. Le choix reste commun à tous les onglets et est sauvegardé sur le téléphone ; un paramètre explicite `?room=bedroom|kitchen` prime sur ce choix. Décor et Recentrer occupent une barre au-dessus de la scène, sans couvrir le dessin. Le sélecteur est absent des mini-scènes Chat/Rappels/Config et de tout plein écran immersif.
- Chambre : le portrait vertical `room-bedroom-portrait.avif` s’affiche dès le chargement du salon ; ses animations restent inchangées. Cuisine : nouveau décor illustré vertical `room-kitchen-portrait.avif` (941 × 1672), entièrement statique, chargé au premier choix. Les deux pièces utilisent le même cadrage portrait ; le modèle r21 debout conserve les mêmes réglages de caméra dans les deux décors.
- Le passage en cuisine suspend la boucle JavaScript de la chambre. Aucun effet de décor n'est chargé pour la cuisine. Recette visuelle Android restante : proportions du personnage et du mobilier, cadrage Accueil, plein écran et mini-scènes.

### Mini-scènes et double appui (26/11/2026)

- Chat, Rappels et Config donnent la priorité au sommet de la tête et au visage ; le bas du personnage peut être coupé. La chambre conserve le repère commun du corps assis et de la tête animée, avec une limite de taille sur les cadres courts. Le fond et ses animations couvrent ensemble toute la miniature. Le r21 en cuisine reprend la caméra portrait de la chambre ; le modèle classique debout conserve le cadrage de repli.
- Un **double clic souris ou double appui tactile/stylet sur la scène** ouvre le plein écran depuis les quatre onglets ; le même geste le ferme et restitue l’onglet de départ. Le bouton dédié reste disponible. Les contrôles, le défilement, les glissements et les gestes à plusieurs doigts sont exclus ; un événement souris synthétique après le tactile ne provoque pas de seconde bascule.
- Le plein écran natif et son repli CSS utilisent le même chemin. Le modèle reste monté et le microphone conserve son état. [Passation, mesures de cadrage et validation](../operations/handoffs/2026-11-26-chatgpt-mobile-scenes.md).


## PWA · Jade r21 et modèle classique (26/11/2026)

- Le micro mobile enregistre pendant l’appui et termine l’énoncé au relâchement. Le WebSocket reçoit les trames pendant la prise lorsque la connexion est prête. Dans Config, **Réagir aux secousses** permet au r21 d’accompagner une secousse volontaire sur l’Accueil et en plein écran. [Fonctionnement et recette](../operations/handoffs/2026-11-26-codex-mobile-ptt-shake.md)
- Sur l’Accueil et en plein écran, deux doigts zooment le r21. Un appui maintenu sur Jade permet de la saisir, de la déplacer et de la poser au relâchement. Le cadrage laisse une partie du modèle visible et **Recentrer** restaure la vue de référence. Les mini-scènes utilisent leur cadrage de base. [Gestes et recette](../operations/handoffs/2026-11-26-codex-mobile-gestures.md)
- **Jade actuelle (r21, révision mobile v49.1)** s’affiche au démarrage, debout dans la chambre et la cuisine. **Config → Modèle** permet de retrouver Jade classique (r20), assise en chambre et debout en cuisine, puis de revenir au r21. Chaque nouvelle ouverture restaure le modèle choisi ; le r21 est le défaut uniquement en l’absence de choix enregistré. Le r20 sert de repli si le r21 est indisponible.
- Chaque bascule coupe le micro et le son et annule la réponse mobile en cours. Le chargeur libère le modèle sortant, ses textures et, en chambre classique, le corps assis, avant de charger le suivant. Config affiche le résultat réel. Une libération incertaine bloque le chargement.
- Le r21 tire un geste A ou B une fois par réponse. Il prend une expression avant la voix, la garde durant les pauses et la tient environ 600 ms après la lecture. L’audio pilote l’ouverture de la bouche, l’intention pilote sa forme. Le paquet livré via Git LFS sert par défaut et `JADE_MOBILE_SECOND_MODEL_DIR` peut désigner un paquet de remplacement. [Contrat technique](TECHNICAL.md#sélection-du-modèle-mobile-26112026) · [Recette des intentions](../operations/handoffs/2026-11-26-codex-mobile-intentions.md)
- Le r21 mobile dispose de la course de regard élargie du rig v45.2 et de deux gestes révisés par intention. Le regard, les paupières, les sourcils et les appuis composent la pose durant la phrase. Le vrai clignement et l’articulation restent indépendants. [Recette des variantes](../operations/handoffs/2026-11-26-codex-mobile-intentions.md#quatrième-étape--dix-variantes-restantes)
- Les oreilles du r21 suivent le souffle avec un léger retard, puis jouent un mouvement propre à chacune des sept intentions. Elles gardent l’attitude pendant la parole et reviennent progressivement à la respiration. [Recette des oreilles](../operations/handoffs/2026-11-26-codex-mobile-oreilles-r21.md)

## Splash de lancement PWA (22/11/2026)

- Image propriétaire `splash-jade.png` servie et affichée plein écran au lancement de l'interface HTML, puis retirée automatiquement. Sur la **connexion par jeton**, la même image reste nette en fond jusqu'à l'entrée dans le salon ; une carte compacte légèrement sous le centre affiche seulement l'icône, « Espace privé de Jade », « Jeton d'accès », le champ et « Entrer dans le salon ». Le formulaire et l'authentification ne changent pas. Android contrôle toujours **la phase native préalable**, constituée de l'icône, du nom et du fond du manifeste. L'icône SVG est ajoutée comme ressource vectorielle alternative ; les PNG restent des fallbacks à source raster 96 px.
- Chargement sans appel IA ni capture, UI/Live2D intacts. Recette sur Redmi Note 13 non encore réalisée.

## PWA · Nouvelle DA Jade inspirée de la robe (22/11/2026)

- **Maquette propriétaire retenue :** dernier concept botanique avec Jade visible dans sa chambre, icône florale aux deux fleurs, vert sauge / vert profond / blanc crème / jaune doux. Nouveau thème CSS séparé de la scène Live2D et des animations.
- **Navigation mobile (révision 22/11) :** quatre onglets : Accueil avec scène et saisie sans rappels, Chat, Rappels (liste visible, formulaire de création replié, case de notification dans Config), Config (boutons de redémarrage mieux séparés). Activités supprimé. L'icône florale SVG est rétablie dans l'en-tête. Le plein écran montre Jade et son décor, le bouton de sortie et le microphone centré en bas (même contrôle vocal, état et préférence audio conservés), et conserve le modèle Live2D monté ; repli immersif CSS si Fullscreen API indisponible.
- **Portée :** UI de la PWA mobile et icônes installables ; pas de changement des fonctionnalités Discord ou du modèle Live2D ni des images de décor existantes. Validation physique Android et rendu dépendant de la licence SDK restent à recetter.

## DEV-036 · Rappels persistants et notifications Web Push Android (22/11/2026)

- **Présent dans le code develop :** rendez-vous et rappels internes stockés dans la base privée jade-reminders.sqlite3 ; outil modèle pour créer/lister/corriger/annuler, avec autorisation propriétaire sur PWA et compte Discord lié ; scheduler indépendant des appels OpenAI et reprise des échéances après redémarrage.
- **PWA :** panneau des rappels, permission explicite Web Push, inscription et désinscription, service worker qui reçoit un identifiant opaque, notification générique et ouverture/focalisation du rappel détaillé après authentification.
- **Conditions :** pywebpush + clés VAPID hors Git, PC allumé et en ligne, téléphone/navigateur compatibles, permissions actives. Push accepté n'est pas un affichage prouvé ; fermeture forcée, optimisation batterie et coupures réseau peuvent empêcher la réception.
- **Preuve de recette :** aucun essai physique Android ou livraison push réelle dans cette session. DEV-036 reste En cours ; calendrier Google/Outlook, récurrence et exécution conversationnelle Android permanente non implémentés.

**Référence :** sources de `goldaj/jade-vtuber`, état préparé pour `develop` sur la PR #34 (21 novembre 2026). **Code raccordé = fonctionnalité implémentée** ; la recette Android/Discord physique reste indépendante, et la configuration privée du PC peut remplacer les valeurs par défaut.

## Livrables PR #38 — code présent, recette en attente (22 novembre 2026)

- **REC-031 (ex DEV-021) :** tâches privées intercanaux et transferts Discord vers destinations explicitement autorisées, recette réelle manquante.
- **REC-032/033 (ex DEV-022/023) :** rappel local lexical et cache mémoire de présence ; recherche très ancienne, L1 et déclenchement d'ouverture PWA partiels.
- **REC-034 (ex DEV-024) :** jalons, durées, p50/p95, tokens, STT mobile, sans coût par tour exact ni preuve d'audition physique.
- **REC-035 (ex DEV-025) :** signaux d'apartés ; discussions multi-fils non pleinement reconnues.
- **REC-036 (ex DEV-026) :** personnalité mémorielle corrigible ; évolution expérientielle plus profonde différée P3.
- **REC-037 (ex DEV-020) :** superviseur local Windows et administration mobile ; pas de recette physique.
- **DEV-010** : décor mobile animé en calques et validé par le propriétaire, **Done** ; **OPS-015** : inventaire artistique **Bloqué** dans l'attente de tokens Codex.

**REC-031/032/033/034 sont Done après validation du propriétaire ; REC-035/036/037 restent À valider.** Les réserves historiques sont détaillées dans l'[audit](../operations/handoffs/2026-11-22-audit-technique-fonctionnel-ci-pr38.md) et dans la vue REC.

## Quick wins VIS-04 / RTE-12, développés le 22 novembre 2026

- **DEV-027, Live2D mobile :** la PWA coupe le ticker PixiJS et l'auto-actualisation du modèle quand l'onglet est caché ou le composant démonté ; pour l'avatar hors viewport, **DEV-029 (VIS-07)** introduit désormais une grâce de **6,5 secondes** avant la pause. Le dialogue, la voix et les connecteurs restent actifs. L'absence d'IntersectionObserver est gérée ; reprise sans nouveau modèle ni relance de l'Idle, et expression visuelle neutralisée après une vraie pause. La batterie/FPS Android ne sont pas encore mesurés réellement.
- **DEV-028, livraison :** les destinations initialement planifiées sont distinctes des événements `delivery_evidence` : confirmation d'acceptation par l'API Discord texte, fin de lecture ffplay ou consommation audio Discord. Les redirections mobiles/HTTP et Twitch sans accusé réel ne sont jamais présentées comme livrées ; aucun statut n'affirme que l'utilisateur a entendu le son. Pas de contenu privé dans ces nouvelles preuves.
- Les tests et conditions de recette sont dans [la passation](../operations/handoffs/2026-11-22-chatgpt-vis04-rte12.md) et la [backlog DEV](../backlog/01-DEVELOPPEMENT.md). **Statut de recette réel à vérifier avant Done.**

**DEV-030 (LAT-10, P1) a été inscrit dans la backlog au statut À faire** ; aucun timeout vocal n'a été modifié. Voir la [passation VIS-07/LAT-10](../operations/handoffs/2026-11-22-vis07-lat10-quickwins.md).

## Explications d'indisponibilité NEW-20 (DEV-031, 22 novembre 2026)

- **Fonctionnel :** erreurs utilisateur explicites (délai, connexion, saturation, autorisation, service) décrites en français sans appeler le LLM ; aucune assertion de livraison ou de résolution non confirmée.
- **Discord texte :** uniquement demande directement adressée à Jade, message incident dans le salon/MP d'origine si le tour a échoué avant la première tentative de livraison. Une réponse déjà engagée, un tour spontané ou annulé n'est jamais doublé ; échec du transport d'incident sans nouvelle tentative.
- **Mobile / HTTP local :** JSON d'erreur authentifié enrichi sans rompre les anciens champs ; le client affiche le motif et garde le texte lorsque seul l'audio échoue.
- **Prudence :** pas d'incident vocal payant envoyé en Discord/Twitch/OBS, pas d'intelligence factice du LLM sur une opération qu'il n'a pas vue. Le comportement détaillé et les limites sont décrits dans la [passation](../operations/handoffs/2026-11-22-new20-incidents-and-new25-retirement.md). **Recette matérielle encore requise avant Done.**
- **Catalogue :** NEW-25 est retirée par décision explicite, aucune autre proposition multilingue active trouvée. Cette décision n'altère pas la langue française existante de Jade.

## Recherche web facultative (REC-038, 22 novembre 2026)

- `JADE_WEB_ENABLED=0` par défaut : aucune recherche web à l'installation ni en veille. Une fois activé, le modèle de dialogue peut appeler librement `jade_web_search` uniquement pendant un tour auquel Jade répond ; ses réponses sans recherche ne déclenchent pas d'appel supplémentaire.
- Fournisseur actif : Tavily via l'adaptateur `src/jade_runtime/web_providers/tavily.py`, remplaçable à travers le contrat `SearchProvider`. Le moteur de dialogue, Discord, PWA et les fichiers de logs ne dépendent pas de Tavily directement.
- Le journal utilise un **dossier privé par défaut `D:/Jade/private/jade-web-search/`**, voisin de `JADE_MEMORY_DB_PATH` (réglage `JADE_WEB_LOG_DIR`) : chaque démarrage live avec recherche web activée crée un nouveau JSONL horodaté avec PID, sans supprimer les sessions précédentes. L'ancienne variable `JADE_WEB_LOG_PATH` reste acceptée comme chemin historique converti vers un dossier voisin ; l'ancien fichier unique reste intact. Toute tentative acceptée est journalisée avant l'appel réseau avec date UTC, requête, raison explicite et provenance ; résultats, statut, coût en crédits disponible et durée sont ensuite ajoutés. Une interruption brutale peut laisser une ligne `started` sans statut final. Un échec d'écriture du journal empêche l'appel réseau.
- Budget : maximum 10 recherches par tour par défaut (réglable de 1 à 10 via `JADE_WEB_MAX_PER_TURN`), recherche `basic` et jusqu'à 5 sources ; coût IA de la continuation de l'outil distinct des crédits Tavily. Pas de compte ni de clé Tavily dans le dépôt. **REC-038 `Done` sur validation explicite du propriétaire le 22/11/2026**, pour la recherche Internet fonctionnelle observée sur son PC ; la CI dédiée web est réussie, les scénarios complémentaires non démontrés restent des réserves documentées dans la vue REC.
- **Politique de réponse web :** Jade synthétise les résultats sans exposer par défaut les URL ou les listes de sources ; lien unique/minimal sur demande explicite ou nécessité directe, et pas d'URL prononcée à l'oral sans demande. Les URL restent présentes dans le journal persistant.

## Fonctions présentes

| Domaine | État observé dans le code |
| --- | --- |
| Lancement | `main.py --all-channels`, launcher Windows, préflight, tous les connecteurs en une instance, sans choix de plateforme |
| Orchestration | `ArbitratingQueue`, `TurnArbiter`, file bornée, équité, **un tour principal à la fois** |
| Discord | Texte, MP, vocal Live ou classique PCM/STT/TTS, sessions, anti-écho et reconnexion. Classifieur social hybride facultatif avec budget séparé. L’arrivée au salon vocal conserve la mise à jour de présence et n’envoie plus de salut. |
| Twitch | IRC entrée/sortie, reconnexion/PING, un seul tour à la fois, solo actif 100 %, groupe 30 % et interpellations directes |
| Dialogue | `prompt_chat.txt`, backend OpenAI configurable ; reprise SQLite intégrale des **24 dernières heures sans plafond de nombre de tours**, mais composition **sélective du prompt** par pertinence locale et budget caractères (réversible par `JADE_SELECTIVE_CONTEXT_ENABLED=0`) |
| Mémoire volontaire DEV-012 | L'outil facultatif natif `jade_save_memory` est disponible au LLM conversationnel sur profil mémoire actif, y compris en streaming vocal. Jade choisit de ne rien écrire ou de proposer L2 (ordinary, 365 j) / L3 (Core, sans purge automatique) ; SQLite vérifie identité, consentement, preuve et périmètre, et renvoie un statut avant la réponse finale. Aucune requête LLM supplémentaire si aucun appel ; une continuation en cas d'action. Les résultats de la curation asynchrone préexistante restent indépendants et ne sont pas réinjectés au LLM. Recette sur matériel réel et approbation DEV-012 encore ouvertes. |
| Demandes explicites de souvenirs | Texte ou voix : toute identité vérifiée avec mémoire active peut demander une mémorisation, enregistrée exclusivement en `kind=ordinary` (durée limitée et portée personnelle/salon) ; même une demande de Core est réduite à l’ordinaire. Jade choisit elle-même ses `core_self` et `core_relationship` via sa curation autonome, aucune commande humaine d’ajout Core. |
| Mémoire | Rappel des souvenirs individualisés désactivé pour les réponses publiques Discord/Twitch/vocal, conservé dans les échanges privés autorisés ; propositions autobiographiques `core_self` de tiers refusées. SQLite v5 privée : L1 brut 7 jours, reprise intégrale 24 h mais injection sélective au modèle ; L2 ordinaire 365 jours ; Core sans purge. **Curation groupée par pertinence** (3 candidats / lot maximum, délai initial 18 s), épinglage de personne au moment de mise en file et contrôle de cohérence d'identité lors des écritures différées. Repères de personnalité issus des mêmes souvenirs autorisés, sans LLM supplémentaire ; autonomie Core conservée |
| Identités | Config Goldaj partagé par micro PC et PWA mobile authentifiée ; mémoire automatique Discord pour compte identifié (serveur, vocal et MP), sans commande d'oubli global ni blocage de réinscription ; Twitch manuel ; liaison Goldaj vers Discord/Twitch par code à usage unique expirant en 5 min, association durable ; **rappel privé transversal des souvenirs sélectionnés entre comptes liés**, sans reprise d'historique brut ni injection inter-canaux dans les salons publics ; déliaison et portées préservées ; suppression individuelle des souvenirs autorisés |
| Discord MP | Cache borné des véritables canaux privés entrants en cas de cache Discord absent ; succès de livraison nécessaire avant mémorisation durable d'une réponse. Tests physiques DEV-019/REC-002 en attente. |\n| Discord voix/texte | Même historique volatil pour un compte dans le vocal et **son chat textuel natif**, sous la même session ; autres salons distincts |
| Mobile | PWA privée/Tailscale Serve : texte, **WebSocket PCM16 montant progressif avec STT à la fin de l'énoncé, TTS sortant progressif, annulation et fin de phrase locale**, WAV HTTP historique en secours avant connexion duplex ; Live2D Web, décor animé et coûts organisationnels (solde prépayé indisponible) |
| Audio | STT/TTS OpenAI, PCM progressif sous conditions, voix Étincelle `shimmer` 1,25×, pitch optionnel via FFmpeg Rubber Band ; pool Realtime partagé WAV/PCM |
| Émotions | Sept intentions ; **deux expressions faciales r20 + deux libellés PWA par intention**, synchronisation expression/bouche, toggle global |
| Préfiltrage économique | Salutations routinières et doublons écartés avant la curation groupée ; coût exact par composant encore à instrumenter. |\n| Observabilité | Jalons `jade.latency` configurables, et **réservations de dépenses USD estimatives** pour initiatives et classifications sociales en SQLite ; métriques d'usage fournisseur réellement facturé et recette physique restent à recueillir |
| Démonstrations | Démo Express simulée uniquement comme démonstration distribuée ; console hors ligne comme mode du vrai runtime. Renderer r20 intégré au code applicatif |

## Limitations fonctionnelles actuelles

1. **Routage :** Discord/Twitch/HTTP écrits ne déclenchent plus de TTS ni de hotkey VTS dans le callback. Le fallback vocal Discord n'utilise plus ffplay local et masque ses sous-titres OBS partagés. MP et sources privées restent exclus des sous-titres OBS. Le routeur central multi-audience et le filtrage du rendu 2D restent à développer ; recette mixage OBS nécessaire.
2. **Streaming :** Discord vocal utilise le PCM progressif (session autorisée) même si ffplay est disponible pour le micro PC ; le mode phrases reste opt-in, mais le fallback WAV Discord vocal ne joue plus en local. Le hotkey VTS ne retarde plus le début de voix standard.
3. **Concurrence :** l'orchestrateur attend la fin du tour et de sa diffusion pour avancer, même si la curation et les connecteurs peuvent travailler à côté.
4. **Mémoire :** rappels par identité/salon et autres portées liées **uniquement en privé** ; sélection lexicale locale et curation groupée intégrées, mais pas encore de préchargement de présence L1/L2, index FTS approfondi ni de recherche sémantique profonde. La fenêtre SQLite 24 h reste intacte.
5. **Mobile :** WebSocket duplex réseau intégré (PCM entrant par fragments, STT après fin de l'énoncé et sortie TTS progressive) ; ce n'est **pas** une conversation OpenAI Realtime audio continu, ni un APK natif. Tailscale Serve/Chrome Android et vraie latence restent à recetter.
6. **Graphique :** l'avatar Windows autonome r20 démarre avec `--all-channels`. Le raccordement des 14 motions r21 y reste à réaliser dans DEV-001.
7. **Modèle IA :** Luna demeure la valeur de configuration par défaut ; un moteur Realtime conversationnel léger sans Luna est prévu ultérieurement, pas intégré.
8. **Installation :** les ports, SDK, comptes et ressources effectifs sont fournis par le PC et sa configuration privée ; le code n'est pas un inventaire des secrets du poste.

## Références sans duplication

[Manuel](README.md) · [architecture](TECHNICAL.md) · [atlas des parcours](../architecture/atlas-fonctionnel-2026-11-16/README.md) · [passation dialogue](../history/gpt6-jade/DIALOGUE-LOW320-HISTORIQUE-PARTICIPATION-20261115.md) · [backlog prospectif](../ameliorations/README.md).

Les PR, audits et CI antérieurs sont conservés dans [`docs/history/gpt6-jade/`](../history/gpt6-jade/) et [`docs/history/conversations/`](../history/conversations/). Ils conservent leur date historique, sans se substituer à ce document ou au code actuel. Les passations actives des agents figurent dans [`docs/operations/handoffs/`](../operations/handoffs/).


## DEV-032 → REC-039 : documents (22/11/2026, recette propriétaire Done)

Le moteur partagé propose une création de fichier réelle, ouverte **par défaut à tout utilisateur Discord identifié par le transport** (sans liaison SQLite Goldaj obligatoire) et aux utilisateurs authentifiés de la PWA privée. Les modes `owner` et `allowlist` restent facultatifs. La création produit une liste de pièces jointes dans `Reply`. Les transports Mobile HTTP/NDJSON/WebSocket et Discord texte/vocal suivent cette liste. Les artefacts privés sont conservés au plus 24 h sur disque ; le nettoyage Discord effectue la suppression des messages concernés avec réessai. Les paramètres non secrets sont `JADE_DOCUMENT_DIR`, `JADE_DOCUMENT_ACCESS_MODE` et `JADE_DOCUMENT_ALLOWED_DISCORD_IDS`. Réception de pièces jointes entrantes non prévue. Le code et les tests automatisés sont validés sur Linux/Windows par la [CI du SHA dc8f0fb2](https://github.com/goldaj/jade-vtuber/actions/runs/45043574769). Le propriétaire accepte explicitement le plafond de longueur lié aux tokens et le PDF minimal. **Recette propriétaire validée sur l'ensemble des parcours PWA/Discord, incluant la confidentialité selon son acceptation globale le 22/11/2026 : [REC-039 Done](../backlog/02-RECETTE.md).**
