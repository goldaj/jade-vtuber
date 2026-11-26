## 2026-11-26 — Zoom et déplacement tactile de Jade r21

- `avatar-gestures.js`, `app.js` et le salon gèrent le pincement à deux doigts, la saisie tactile après appui maintenu et le bouton Recentrer. La zone est réservée à l’Accueil et au plein écran avec le r21 actif. Les gestes consommés sont exclus du double appui.
- `avatar.js` applique une transformation locale et bornée au r21 par-dessus le cadrage d’origine. Le gateway sert le module après la connexion et les deux workflows Node rejouent ses interactions. [Recette et limites](handoffs/2026-11-26-codex-mobile-gestures.md)

## 2026-11-26 — Jambes du r21 continues jusqu’au bord de la chambre

- Sur l’Accueil en chambre, le décalage au-dessus du micro remontait aussi le bord inférieur du canvas WebGL. `jade-theme.css` prolonge la surface du r21 vers le bas de la valeur du décalage. `avatar.js` calcule toujours le zoom et la position de la tête à partir de la toile de cadrage. Le bord de la scène détermine ainsi le recadrage.
- Le test de cycle compare les positions et la taille de la tête avec une surface de rendu agrandie.

## 2026-11-26 — Cadrage mobile du r21 calé sur celui du classique

- `avatar.js` applique les mêmes cadrages de scène aux deux modèles. Le r21 adapte sa taille et sa position aux repères du visage du r20, puis le corps debout suit à la même échelle.
- `jade-theme.css` donne aux deux modèles la même composition de chambre. En chambre très large, le r21 reprend le cadrage des mini-scènes pour garder la tête visible. Les tests de cadrage comparent l’emplacement et l’échelle du visage lors de la bascule.

## 2026-11-26 — Jade r21 devient le modèle mobile par défaut

- Le catalogue de `mobile_gateway.py` sert le r21 v45.1 de la livraison Git LFS sous un manifeste Web et quatre expressions complémentaires. `avatar-models.js`, `avatar.js` et Profil chargent le r21 debout dans les deux pièces par défaut et proposent le r20 classique avec sa présentation assise en chambre.
- Le lecteur r21 boucle son repos et raccorde les sept paires de motions aux intentions mobiles. Les paramètres d’yeux et de bouche restent indépendants des gestes. Le cadrage des vues en pied tient compte du sol et le CSS recadre ensemble le décor chambre et ses effets en paysage. Le chargement exclusif conserve le repli r20 en cas d’échec.
- `app.js` coupe l’enregistrement, le son, le duplex et les requêtes de conversation avant le déchargement. Les fragments tardifs sont ignorés. Le serveur surveille aussi la déconnexion des requêtes mobiles en mode JSON.
- Les tests couvrent le défaut r21, le repli, le manifeste et les expressions Web, les quatorze gestes et la coupure. La [passation du volet PWA de DEV-001](handoffs/2026-11-26-codex-mobile-r21.md) consigne les résultats et la recette Android restante.

## 2026-11-26 — Préparation du choix de modèle dans la PWA

- Demande du propriétaire : préparer un emplacement pour un second modèle, sans le raccorder maintenant. Profil propose « Modèle actuel » par défaut et « Nouveau modèle — à venir » désactivé. Le choix est propre à la session ; consulter Profil ne charge aucun modèle supplémentaire.
- `avatar-models.js` lit un catalogue privé validé ; `avatar-model-loader.js` et `avatar.js` sérialisent les remplacements et libèrent le modèle précédent avant le suivant. L’interface reflète le modèle réellement chargé, les chargements et les échecs ; une erreur de remplacement déclenche le repli prévu, sans annoncer une sélection réussie. Une libération non confirmée bloque une nouvelle allocation.
- `seated-scene.js` sépare le corps hybride du décor portrait : le corps est retiré avant le déchargement, ses images tardives sont invalidées et il peut être reconstruit au retour au classique. Le décor déjà validé et ses animations restent indépendants du modèle ; un profil complet ne charge ni le corps assis ni les expressions/Idle spécifiques au r20.
- `config.py`, `main.py`, `mobile_gateway.py` et `.env.example` préparent `JADE_MOBILE_SECOND_MODEL_DIR`, **vide par défaut**. Le second emplacement n’est disponible qu’avec un dossier explicitement configuré et un paquet portable valide. Aucun parcours automatique des livraisons r21/v45.1, aucun nouvel asset activé et aucune modification de configuration privée dans cette mission. Les nouvelles ressources Web sont ajoutées à l’export autonome.
- Validation locale complète : **747 tests Python**, **13 suites JavaScript**, syntaxe de 12 modules, preflight, compilation, export autonome et contrat documentaire réussis. Recette Chromium avec SDK réel : un seul modèle vivant, corps classique retiré/recréé, chargement obsolète libéré, panne de texture récupérée et caches stables après des bascules répétées. Les trois nouveaux tests sont raccordés aux deux workflows CI. Le [compte rendu de mission](handoffs/2026-11-26-chatgpt-mobile-model-selection.md) précise les preuves et les limites ; le vrai second modèle reste non branché.

## 2026-11-26 — Mini-scènes centrées sur le visage et plein écran au double appui
- Demande directe du propriétaire : réserver le sélecteur Chambre/Cuisine à l’Accueil fenêtré ; donner la priorité au sommet de la tête et au visage dans Chat, Rappels et Profil ; ouvrir/fermer le plein écran par double clic souris ou double appui tactile.
- `mobile_web/jade-theme.css` masque le sélecteur hors Accueil et recadre la composition assise entière. Sur les scènes courtes, sa taille est plafonnée et le décor avec ses animations continue de remplir la largeur sans raccord vertical. `avatar.js` ancre aussi le modèle debout de cuisine/repli sous le bord supérieur. Les réglages de raccord tête/corps restent identiques.
- `app.js` utilise une bascule unique pour le bouton et les gestes, conserve l’onglet et le microphone, exclut les contrôles, glissements, pincements et doubles événements tactiles/souris. Deux tests Node comportementaux sont ajoutés aux workflows hors ligne.
- Vérifications : tests Node de gestes/cadrage, rendu Chromium du vrai r20, enveloppe de tête mesurée sur 486 poses extrêmes et 32 parcours navigateur souris/tactile, plein écran natif/repli CSS, deux décors et quatre onglets. La suite Python, le contrôle documentaire et la CI complètent ces preuves ; résultats dans la [passation](handoffs/2026-11-26-chatgpt-mobile-scenes.md). Aucun essai sur le téléphone physique ni microphone réel n’est revendiqué.
- Remise en cohérence de contrôles préexistants : mock `classList` du test de streaming et ancien contrat de placement du micro ; cellules de dépendances DEV-039/040/041 remises au format attendu, avec les précisions conservées dans les critères. L’export autonome inclut désormais `portrait-bedroom-motion.js`, déjà servi par la PWA mais absent de sa liste explicite ; son test vérifie la présence de toutes les routes de fichiers PWA. Aucun changement de priorité ni de périmètre de ces cartes, ni élargissement de l’export aux SDK ou données privées.

## 2026-11-25 — Sauvegarde Git de Jade v45.1

La [livraison portable](../../jade-modeling/assets/live2d/r21_professional_art/livraison/Jade_r21_v45_1/LISEZMOI.md) réunit l’export jouable et ses sources éditables. Git LFS conserve les binaires. Le catalogue de la copie publique couvre le profil portable et les sources préparées pour le dépôt.

## 2026-11-25 — Livraison autonome et calibration de Jade v45.1

Le paquet installé regroupe le modèle, les quatorze gestes et le profil VTube Studio. Les KRA/PSD, le CMO3 et les sources d’animation sont réunis dans la livraison locale. La relecture en situation couvre appuis, parole, clignement, interruption et retour au repos. Les assets sont disponibles pour DEV-001. [Résultats, réglages et limites](handoffs/2026-11-25-codex-livraison-modele-jade.md)

## 2026-11-25 — Contour des iris de Jade v45.1

Le modèle en service conserve le profil v45 et ses quatorze raccourcis. Les bords des deux iris ont été corrigés en regard haut. Le rythme du balancement complice a été conservé après deux déclenchements isolés dans VTube Studio. [Fichiers de reprise](../../jade-modeling/CONTINUATION.md#base-à-ouvrir)

## 2026-11-25 — Les quatorze gestes de Jade v45

- ART-009 est terminé sur le poste de Jade. Les six paires restantes rejoignent la curiosité dans l’atelier PSD2Live et le paquet VTube Studio. Les pilotes locaux de parole et d’expressions prennent en charge ce paquet. [Catalogue des gestes](../../jade-modeling/CONTINUATION.md#jouer-les-quatorze-gestes) · [Recette](handoffs/2026-11-25-codex-jade-r21-reprise.md)

## 2026-11-25 — Deux gestes de curiosité pour Jade v44

- Le modèle dispose de deux actions jouables en parole. Jade se penche et tend l’oreille dans la première. Dans la seconde, elle cherche dans deux directions et ponctue sa réaction d’un hochement. Ce dernier mouvement a été repris après la première revue au cadrage de diffusion. Les pilotes de parole et d’expressions reconnaissent le paquet v44. [Fichiers et commandes](../../jade-modeling/CONTINUATION.md#déclencher-la-curiosité-dans-vtube-studio) · [Suivi ART-009](../backlog/04-PRODUCTION-2D.md)

## 2026-11-25 — Bouche et transitions de parole de Jade v43

- Les deux poses signalées par le propriétaire ont été reprises dans le rig et dans la peinture. Le paquet v43 a passé la revue en sourire parlé, pendant un clignement et sur une coupure en pleine syllabe suivie d’une seconde réplique. Le pilote associe chaque niveau de bouche à la réplique en cours et relâche les expressions à la fin. [Avant/après et mesures](../../jade-modeling/MODEL2D_CODEX_STATE.md) · [Utiliser le pilote](../../jade-modeling/CONTINUATION.md#piloter-une-réplique-dans-vtube-studio)

## 2026-11-25 — Amplitude des mouvements de Jade v42

- La comparaison avec Huohuo en fonctionnement a conduit à reprendre le suivi de tête, la dynamique des mèches, des oreilles et des bras et le mouvement autonome au repos. Le profil v42 est chargé au cadrage du propriétaire dans VTube Studio. [État du modèle](../../jade-modeling/MODEL2D_CODEX_STATE.md) · [Passation](handoffs/2026-11-25-codex-jade-r21-reprise.md)

## 2026-11-25 — Mouvement secondaire de Jade v41

- L’export natif ajoute la flexion des masses arrière et des oreilles et reprend la mèche du sommet. Le réglage sépare inertie et tressautement dans l’idle. Le pilotage des expressions reconnaît le nouveau paquet. Les retournements et arrêts ont été rejoués dans VTube Studio. [État du modèle](../../jade-modeling/MODEL2D_CODEX_STATE.md) · [Passation](handoffs/2026-11-25-codex-jade-r21-reprise.md)

## 2026-11-25 — Appuis et inertie de jupe de Jade v40

- Le v40 associe appuis latéraux, contre-inclinaison du haut du corps et relâchement du genou libre. Après rejet de la première amplitude, une physique d’ourlet amortie accompagne la boucle de 36 s. Le profil VTS préserve le vent sur les cheveux. Le contrôle couvre les pieds et les combinaisons avec le visage en parole. [État de reprise](../../jade-modeling/MODEL2D_CODEX_STATE.md) · [Passation](handoffs/2026-11-25-codex-jade-r21-reprise.md)

## 2026-11-25 — Épaules et expressions en parole de Jade v39

- Le v39 corrige les fragments sur les deux épaules et rend le regard, les sourcils et la bouche indépendants en dialogue. Le panel a demandé une reprise de l’opacité des iris avant d’accepter le paquet natif. Deux phrases françaises ont piloté la bouche dans VTube Studio pendant les bascules Smile, Sad et repos. La commande de modèle gère les bascules temporisées. [Outil](../../jade-modeling/tools/vts_jade_expression.py) · [État et point de finition](../../jade-modeling/MODEL2D_CODEX_STATE.md)

## 2026-11-25 — Portrait et clignement de Jade v38

- Le v38 relie le cou au mouvement de tête, rétablit la matière derrière les épaules et corrige les contours qui suivaient les mèches. Le cil masque progressivement l’iris et rejoint le dessin de l’œil fermé. Les avis croisés ont conduit à reprendre le fondu des cils et les sous-peintures avant d’accepter ces éléments sur l’export natif.
- [État de reprise](../../jade-modeling/MODEL2D_CODEX_STATE.md) · [Passation](handoffs/2026-11-25-codex-jade-r21-reprise.md)

## 2026-11-25 — Centrage de la bouche de Jade v37

- Le v37 corrige le décalage entre le centre du visage et la bouche relevé sur le v36. Comparé au dessin maître sur cinq poses, le centrage du paquet natif présente un écart maximal de 1,79 px. VTube Studio charge le modèle et répond aux commandes de fermeture et d’ouverture.
- [État de reprise](../../jade-modeling/MODEL2D_CODEX_STATE.md) · [Passation](handoffs/2026-11-25-codex-jade-r21-reprise.md)

## 2026-11-25 — Reprise visuelle de Jade et candidat natif v36

- Après rejet du v34, reprise des grandes découpes depuis le dessin maître et passage de la recette à l’export Cubism SDK 5.0.
- Le v36 est observé plein pied dans VTube Studio. Les poses et les sorties de mouvement ont été vérifiées sur le même paquet natif. Les passages fins au col et aux cils restent ouverts.
- [État de reprise](../../jade-modeling/MODEL2D_CODEX_STATE.md) · [Passation](handoffs/2026-11-25-codex-jade-r21-reprise.md)

## 2026-11-25 — Premier chargement r21 et candidats de finition

- Le premier r21 plein pied a été chargé dans VTube Studio 1.35.10. Le v33 réunit des retouches de l’ourlet, des mains, de la transparence au nez et d’une partie des cheveux arrière.
- Les v33 et v34 sont chargés par l’API VTube Studio. Le v34 ajoute des retouches de coudes, taille et commissures et une calibration des entrées yeux/bouche validée par l’API. Son export passe par PSD2Live. Les corrections restent à observer en mouvement. Les fichiers de travail et le rapport de défauts restent sur D:.
- Base `develop` `c3c17b0`. [État de reprise](../../jade-modeling/MODEL2D_CODEX_STATE.md) · [Passation](handoffs/2026-11-25-codex-jade-r21-reprise.md)

## 2026-11-25 — Préparation de Jade r21 avec les deux MCP

- ART-001/002. Plan de production 2D approuvé, reprise sur le candidat v32 local. Turboism accompagne Cubism PRO 5.3.05. PSD2Live sert aux essais de calques, de rig, de physique et de mouvement. La production attend un feu vert distinct.
- Le plan, les points de reprise et le backlog relatent l’état constaté. L’ourlet du candidat intermédiaire a été observé dans Cubism. L’export et la recette du v32 restent à faire, avec observation en direct par le propriétaire.
- Base `develop` `c3c17b0`. [Plan directeur](../../jade-modeling/MODEL2D_MASTER_PLAN.md) · [Passation](handoffs/2026-11-25-codex-jade-r21-reprise.md)

## 2026-11-24 — Microphone en plein écran mobile

- Le mode immersif natif ou CSS conserve le bouton micro en bas, centré et accessible, sans afficher la navigation, le chat ou le sélecteur de décor. Le bouton unique est déplacé dans la scène à l'entrée, puis revient à son emplacement selon l'onglet à la sortie, sans réinitialiser l'enregistrement ni la préférence de synthèse vocale.
- Fichiers : `mobile_web/app.js`, `mobile_web/jade-theme.css`, contrat de non-régression dédié et état fonctionnel. Aucun changement de proportions du modèle, du décor, des API vocales ni de main.
- Vérification : revue statique des transitions et des sélecteurs, test de contrat ajouté ; CI et essai physique Android à confirmer (entrée depuis Accueil/Chat, enregistrement, écoute et sortie).

## 2026-11-24 — Correction de la mise à jour distante PyCharm

- REC-037 : redémarrage simple confirmé par le propriétaire, mise à jour non effective. Suppression du refus global des modifications locales ; Git fast-forward sans autostash ni écrasement des fichiers ignorés, refus des conflits et des branches divergentes. Fetch explicite de develop, contrôle du SHA réellement lancé, reprise LFS même après un merge antérieur.
- Superviseur : erreurs Git détaillées et filtrées, commandes non interactives, résultats distincts et logs de contrôle visibles sur Android. Les deux interfaces affichent le SHA distant du dernier fetch. Configuration Run et secrets inchangés.
- Tests d'intégration Git locaux ajoutés (fichiers locaux conservés, conflit refusé, diagnostic filtré) ; CI et recette Windows/Android à vérifier. Pour charger ce correctif du parent déjà en mémoire, effectuer une mise à jour locale initiale et relancer une fois la session Run PyCharm. Aucun changement de main.

## 2026-11-24 — Raccordement de la véritable configuration PyCharm « discord & mobile »

- **Diagnostic confirmé par captures du propriétaire :** la configuration effectivement utilisée pointe sur \u0060main.py\u0060 avec les cinq options \u0060--live --discord --discord-voice --voice --mobile\u0060, tandis que le contrôleur ne sait piloter qu'un moteur lancé par le parent persistant. Le symptôme est \u0060pycharm_run_not_available\u0060 (port 8772 absent), même si le contrôleur 8771 est accessible.
- **Correctif sur develop :** le lanceur \u0060tools/jade_pycharm_runner.py\u0060 accepte les options CLI de \u0060main.py\u0060, conserve leur ordre et les transmet au préflight et au processus enfant lors des redémarrages. Le profil partagé de test sans paramètres conserve ses valeurs historiques. En mode personnalisé, l'environnement existant et les valeurs du .env sélectionné ne sont pas remplacés par les réglages audio du profil de test. Le parent géré conserve l'interpréteur PyCharm actif.
- **Tests :** contrats ajoutés pour les cinq options exactes, le passage au parent, le redémarrage et le rejet des drapeaux inconnus. Le résultat de la CI est à vérifier ; la recette Windows/PyCharm/Android reste à réaliser. Le changement à effectuer dans la configuration privée est limité au champ Script path, détaillé dans le guide PyCharm. Aucun changement de main.

## 2026-11-23 — Contrôle distant de la session PyCharm Run (branche expérimentale)

- **Implémenté sur feat/jade-pycharm-remote-control-20261123 seulement :** parent persistant dans Run, moteur unique enfant avec arrêt propre par signal privé, IPC loopback authentifié, contrôleur Windows invisible et indépendant de Jade, mise à jour fast-forward develop uniquement, logs Run dupliqués en fichier privé rotatif, page de secours /control via Tailscale Serve.
- **Windows :** installateur créant une tâche à l'ouverture de session et un raccourci bureau sans fenêtre ; la route Tailscale /control est ajoutée sans remplacer la route / existante, sous réserve des permissions CLI Windows.
- **Android :** retrait de la sélection de branche et de l'ancien endpoint de déploiement ; boutons de mise à jour/redémarrage et logs filtrables dans Profil.
- **Contrôles :** tests unitaires hors ligne ajoutés, validation GitHub CI à observer et recette PC/Android non réalisée. Pas de merge vers develop ni main, ni d'installation effective sur le PC. Référence : [guide spécifique](reference/REMOTE-PYCHARM-CONTROL-20261123.md).

## 2026-11-23 — Jade assise : cou illustré intégré directement dans l’AVIF

- **Graphisme :** correction ciblée de `src/jade_runtime/mobile_web/jade-seated-body.avif` (670 × 940, transparence conservée) à partir du corps assis validé sur `develop`. Reconstruction du cou, des clavicules et de la jonction des épaules sans cheveux ni seconde silhouette ; suppression du fragment de peau détaché. La robe, les bras, les mains, les jambes, les chaussures et le pouf restent issus de l’illustration originale.
- **Rendu :** suppression de la forme de cou PixiJS et du pseudo-élément CSS ajoutés provisoirement. Le corps AVIF et les cheveux arrière/avant restent ordonnés par le compositeur Live2D unique existant ; ni les paramètres de la tête ni les décors cuisine/chambre ne sont déplacés.
- **Contrats :** `tests/test_jade_seated_mobile_contract.py` vérifie l’absence des faux calques et le maintien du rendu assis et du fallback. Vérification manuelle du conteneur AVIF, de l’alpha et des dimensions. L’alignement exact avec la tête en mouvement et le contour sur Redmi nécessitent encore une recette visuelle sur le téléphone.
- **Portée :** uniquement `develop` après fusion de la PR de correction, aucun changement de `main`.

# Journal technique unique — develop

## 2026-11-22 — Correctif popup de connexion masquée par le splash

- **Anomalie constatée sur Redmi (capture du propriétaire) :** l'image de lancement remplissait l'écran sans laisser apparaître le formulaire de jeton, alors que celui-ci se trouve bien dans le HTML.
- **Cause :** le lancement HTML superposait un splash temporaire `z-index:99999` au dialogue `z-index:40`, et le retirait seulement lors de `window.load`, susceptible d'être retardé par les autres ressources.
- **Correctif sur develop :** le dialogue de connexion passe au-dessus du splash transitoire ; `splash.js`, chargé avec `defer`, déclenche sa disparition immédiatement après l'analyse du DOM, indépendamment de `window.load`. Fond net, carte compacte très basse en portrait, sécurité du jeton, autres écrans et animations inchangés.
- **Validation :** contrat automatisé `tests/test_jade_botanical_ui.py` adapté pour empêcher un retour de cette superposition. À vérifier physiquement sur Android avant clôture de `REC-040` (démarrage, ouverture du clavier, sortie et reconnexion, portrait/paysage). Aucune modification de `main`.

## 2026-11-22 — Cuisine animée en trois effets isolés

- **Demande du propriétaire :** animer vapeur de bouilloire, plantes retombantes et lumière au sol, sans déformer le reste du décor et sans toucher aux animations de la chambre.
- **Code :** `mobile_web/index.html` ajoute un conteneur réservé à la cuisine. Trois volutes SVG peu opaques montent au-dessus de la bouilloire ; trois fines extrémités de feuillage SVG oscillent indépendamment à proximité des végétaux existants ; un éclairage radial diffus varie uniquement au niveau du parquet. `styles.css` anime ces calques en `transform`/`opacity` uniquement ; l'image `room-kitchen.webp` et tous ses pixels restent strictement statiques, sans inpainting, masquage ni transformation des éléments du fond. L'ajout de rameaux visuels en premier plan, plutôt qu'un découpage de plantes déjà peintes, évite les trous et déformations de l'image.
- **Isolation :** `room-motion.js` commute les effets selon `room`. La chambre conserve seule sa boucle `requestAnimationFrame` et son rideau ; la cuisine a uniquement des animations CSS. Les deux pièces respectent le mode de mouvement réduit et l'arrêt lorsque la scène ou l'onglet n'est pas visible. Les effets sont positionnés en pourcentages de l'image 4:3, sans dépendre des dimensions d'écran.
- **Tests et suivi :** `tests/mobile_room_selection_test.js` vérifie les transitions, la pause hors écran, l'absence de fuite entre décors, les fallbacks et les calques ; `tests/room_motion_test.js` vérifie la conservation du moteur chambre ; ce test est désormais exécuté par le workflow Linux/Windows `jade-rebuild.yml`. `BRANCH_STATE.md` et `REC-040` sont mis à jour. Recette physique Android du placement exact, du rendu esthétique et de l'absence d'artefacts encore à réaliser. Pas de modification de `main`.


## 2026-11-22 — Deux décors sélectionnables, animations isolées par pièce

- **Décision :** le sélecteur « Décor » propose Chambre (décor existant) et Cuisine (visuel validé par le propriétaire), avec un choix mémorisé dans le paramètre d’URL `room` plutôt que dans un stockage navigateur privé.
- **Implémentation :** `room-kitchen.webp` est un asset local servi par la liste explicite du gateway ; le contrôleur `room-motion.js` sélectionne la source et active les calques animés uniquement pour la chambre. Au passage dans la cuisine, rideau, ombres, reflet et vapeur de la chambre sont cachés et la boucle `requestAnimationFrame` est interrompue ; retour chambre = reprise des effets initiaux. La cuisine ne possède **pas encore d’animations**, en attente de consignes du propriétaire.
- **Portée :** `mobile_web/index.html`, `jade-theme.css`, `room-motion.js`, `room-kitchen.webp`, `mobile_gateway.py`, `tools/jade_publication_export.py` et le test `tests/mobile_room_selection_test.js`. Le modèle Live2D et la logique d’authentification ne changent pas. Aucun impact sur `main`.
- **Vérifications :** invariants visuels et source par pièce couverts par un test Node simulé ; vérifier sur Android les changements répétés, la chambre avec rideau animé, et le rendu final de la cuisine avant validation propriétaire.


## 2026-11-22 — Splash conservé derrière la connexion mobile

- **Décision UX :** le splash `splash-jade.png` devient également l'image nette de fond de l'écran privé de connexion. Aucun voile opaque ni flou ; le contenu existant de l'application reste inaccessible tant que le formulaire est visible.
- **Fenêtre compacte, légèrement abaissée :** icône SVG locale, « Espace privé de Jade », « Jeton d'accès », saisie masquée, « Entrer dans le salon » ; textes d'instruction et note de bas de carte retirés. Mise en page réduite, adaptation en faible hauteur et préservation des zones sûres.
- **Portée :** HTML/CSS PWA et contrat de test seulement ; validateur de jeton, Tailscale, Bearer et `app.js` inchangés. Recette physique sur Redmi et retour après 401 à vérifier dans `REC-040`. [Passation](handoffs/2026-11-22-chatgpt-login-splash.md). Aucune modification de `main`.

## 2026-11-22 — Simplification UX PWA Jade

- **Besoin :** rappels retirés de l'Accueil et Activités supprimé ; Rappels en liste immédiatement visible, formulaire sous accordéon fermé, notifications Android en choix radio exclusif synchronisé avec l'abonnement effectif.
- **Affichage :** icône SVG locale rétablie en haut à gauche ; boutons de redémarrage différenciés dans Profil ; bouton de plein écran transformé en scène exclusive Jade/chambre avec seule commande de sortie visible. Fullscreen API opportuniste et fallback CSS, sans démontage Live2D.
- **Fichiers :** `mobile_web/index.html`, `app.js`, `jade-theme.css`, test d'interface, état fonctionnel et suivi `REC-040`. [Passation](handoffs/2026-11-22-chatgpt-mobile-ux-navigation.md).
- **Contrôles et limites :** syntaxe JS et contrats HTML/CSS contrôlés avant push ; recette Android, push réel et rendu Live2D matériel à valider sur le téléphone. Backend et `main` non modifiés.


## 2026-11-22 — Splash illustré Jade et écran Android

- **Choix du propriétaire :** image exacte `src/jade_runtime/mobile_web/splash-jade.png` déposée sur develop, utilisée pour le premier écran web dès que Chrome a lancé la PWA. Plein écran (ratio vertical, object-fit cover), chargement prioritaire, retrait automatique et non bloquant lorsque la page est prête. Aucune nouvelle permission ni utilisation de tokens ; la chambre Live2D et la conversation restent intactes.
- **Distinction technique incontournable :** Android/Chrome affiche d'abord le splash natif construit depuis le manifeste (icône/nom/couleur), puis affiche le HTML. La PWA ne peut pas remplacer cet écran natif par un fond plein écran. Une version vectorielle SVG est ajoutée au manifeste pour les navigateurs compatibles, tandis que les PNG 192/512 restent des solutions de repli ; leur source raster actuelle ne fait que 96 px, donc une mise à l'échelle 4K ne créera pas de vrais détails.
- **Sécurité et packaging :** le gateway privé autorise uniquement `/assets/splash-jade.png` et `/assets/splash.js`, politique de cache inchangée ; la prévisualisation privée copie l'image et vérifie sa signature/dimensions avant export, sans lire le PNG comme du texte.
- **Validation :** contrat de la PWA enrichi ; recette physique sur Redmi Note 13 toujours requise pour confirmer l'enchaînement splash natif → illustration → accueil. Après mise à jour du manifeste, Chrome peut nécessiter une réinstallation pour renouveler son icône système. Aucun changement main.

## 2026-11-22 — Identité visuelle PWA Jade, maquette finale du propriétaire

- **Décision visuelle :** retenir la dernière maquette validée en conversation : ambiance botanique sobre, fond clair, sauge #C8DCC7, vert profond #2F5D45, crème/blanc et jaune floral #F7D774 ; l'icône est la composition choisie de deux fleurs blanches avec feuillage et arabesques dorées.
- **Priorité Live2D :** préserver la scène et les calques de la chambre existante, les SDK locaux, les expressions/animations, le microphone et le chat. La page Accueil réserve environ la moitié de la hauteur mobile au modèle visible ; le chat reste accessible, sans cacher Jade sous un plein écran de messages.
- **Navigation :** Accueil (chambre + saisie + aperçu des vrais rappels), Rappels (gestion et Web Push de DEV-036), Chat (historique), Activités (raccourcis vers les fonctions existantes), Profil (réglages techniques/identité). Aucun faux service calendrier, fonctionnalité facturée ni notification n'est créé à partir de la maquette.
- **Compatibilité :** CSS autonome jade-theme.css sur le CSS historique, canvas et mémoire conservés dans le DOM lors des changements de vue ; palette du manifest/PWA et icônes alignées ; pas de modification de main. Les ressources restent servies par le gateway localhost derrière Tailscale Serve.
- **Validation :** tests automatisés des routes/manifest/contrats d'interface et CI à lancer après le push ; conformité exacte du rendu dépend du SDK Live2D et de l'écran Android. Un dessin de maquette n'est pas une capture d'interface réelle.
- **Correctif de packaging :** l'exporteur de preview privée conserve maintenant jade-theme.css et icon-source-96.png, car mobile_icons.py dépend de la source raster autorisée ; l'icône est vérifiée sur sa signature PNG et son SHA-256 approuvé avant export, sans tentative de lecture UTF-8 de l'image.

## 2026-11-22 — DEV-036 : rappels persistants, push Android et ouverture ciblée

- **Complément de recette CI :** ajouter l'horloge UTC de chaque tour au contexte outil pour convertir les demandes relatives (« dans 10 minutes »), et conserver le deep link de notification dans l'URL quand une PWA existante doit encore être déverrouillée. Les contrôles automatiques ont signalé une dépendance non canonique dans la carte DEV-036, corrigée par `REC-014, REC-022` avant relance.

- **Décision produit approuvée :** les trois étapes d'origine forment une seule US, avec la création/gestion des rappels, les notifications Web Push après fermeture courante de la PWA ou sur écran verrouillé, et le deep link vers le rappel ciblé. Contrat détaillé et critères d'acceptation dans la [carte DEV-036](../backlog/01-DEVELOPPEMENT.md).
- **Implémentation sur develop :** service SQLite privé et scheduler sans appels IA en veille ; outils Responses sur canaux propriétaire autorisés ; routage Discord limité au salon/MP d'origine ; API mobile authentifiée pour consulter, créer, modifier, annuler, inscrire/désinscrire la subscription ; PWA et Service Worker sans stockage du Bearer ni microphone actif en arrière-plan ; notifications génériques et identifiant opaque, click-to-open.
- **Fichiers :** reminders.py, mobile_gateway.py, mobile_web (app.js, sw.js, index.html, styles.css), config.py, web_search.py, dialogue.py, responses_chat.py, orchestrator.py, main.py, setup_web_push.py, tests/test_jade_reminders.py, documentation de la PWA et du backlog.
- **Risques et limites :** bibliothèque facultative pywebpush et paire VAPID privée à installer sur le PC, compatibilité/fonctionnement Android non encore observés, dépendance PC et accès Internet. Le fournisseur push peut accepter sans que le téléphone affiche ; une coupure après envoi et avant écriture SQLite peut provoquer un doublon. Pas de calendrier externe ni récurrence.
- **Vérifications :** tests automatiques ajoutés pour la persistance, les échéances, l'accès et le scheduler ; leur exécution CI doit être vérifiée séparément. Aucun push réel ni test sur téléphone n'est affirmé. DEV-036 reste En cours avant preuve de recette.

## 2026-11-22 — NEW-16 → DEV-036 : rappels et notifications, backlog uniquement

- **Décision explicite du propriétaire :** promouvoir l'idée prospective `NEW-16` (P2) vers une carte de développement `DEV-036`, au statut **À qualifier**, puis retirer son entrée du catalogue actif des idées. Aucune implémentation autorisée ni démarrée.
- **Périmètre conservé pour qualification :** rappels/événements demandés, échéance et fuseau, destinataire et audience, envoi Discord ciblé ; option de notifications mobiles, modification/annulation, redémarrages, échéances manquées, déduplication, statut réel et déclenchement sans appel LLM permanent. **Choix non décidés** : calendrier interne ou connexion externe, récurrence et mécanisme des notifications mobiles.
- **Suivi sans doublon :** `NEW-16` reste seulement un identifiant d'origine historique ; la carte active est [`DEV-036`](../backlog/01-DEVELOPPEMENT.md). Les index de priorisation et décomptes des idées sont actualisés.

## 2026-11-22 — REC-039 : acceptation fonctionnelle du propriétaire, Done

- **Validation explicite de Goldaj :** « je confirme et valide la recette de l'ensemble de cette US. Tout marche, tu peux mettre à done ». Les parcours PWA écrits/vocaux avaient été confirmés et les anciens échecs Discord MP, salon public écrit et vocal public sont déclarés résolus par cette recette finale réelle. Ne pas prétendre disposer de métriques ou de captures supplémentaires.
- **Intégration :** documents générables par tout utilisateur Discord identifié par défaut (`all`), avec modes `owner` / `allowlist` optionnels et authentification PWA privée inchangée. Livraison sur `develop` au commit [`c4eba34a`](https://github.com/goldaj/jade-vtuber/commit/c4eba34a2e7427ff54aaaffff4d44457694baf3c).
- **Statut :** `REC-039` classée **Done** à la demande du propriétaire, clôturant l'ancienne `DEV-032`. Le catalogue `NEW-16` (P2, rappels et notifications d'événements planifiés) est le prochain sujet **de qualification seulement**, non engagé en développement.

## 2026-11-22 — REC-039 : génération de fichiers ouverte par défaut

- **Décision du propriétaire :** pour faciliter les essais, toute personne disposant d'une identité de transport Discord valide peut demander la génération d'un document. Mode `all` par défaut dans `DocumentService` et `Settings`, sans prérequis de liaison Goldaj ; `owner` et `allowlist` restent facultatifs. La PWA ne perd pas son authentification privée, et les événements synthétiques restent exclus.
- **Tests :** vérification du nouveau comportement en MP, écrit public et vocal Discord, plus tests de conservation du mode `owner`, rejet des messages synthétiques et absence de changement des autres transports. La recette réelle de Discord reste **KO** tant que le propriétaire n'a pas retesté.
- **Attention :** une valeur explicite `JADE_DOCUMENT_ACCESS_MODE=owner` dans un fichier d'environnement privé reste prioritaire sur le nouveau défaut et doit être corrigée séparément si présente.

## 2026-11-22 — REC-039 : corriger le refus systématique de génération sur Discord

- **Recette propriétaire :** mobile texte et voix confirmés OK ; Discord MP écrit, public écrit et public vocal KO, Jade déclarant explicitement l'outil indisponible.
- **Cause dans le code :** `DocumentService.for_turn` donnait le droit mobile directement mais refusait Discord quand la mémoire était désactivée, même avec une association de compte persistée. Le prompt conditionnel pouvait entretenir la confusion entre « pas de permission » et « Discord non pris en charge ». L'état réel de la mémoire du PC n'est pas connu : cause plausible, pas preuve d'exécution privée.
- **Correction ciblée sur develop :** lecture *seule* des identités liées en SQLite lorsque le service mémoire est désactivé, décision d'accès journalisée sans ID/texte, instruction explicite de génération pour un compte Discord déjà lié, et vrai refus de droit pour un tiers. Tests unitaires SQLite lien réel, Discord MP/public/vocal et livraison du fichier simulée. Ni reset de liaison, ni ouverture indiscriminée des autorisations, ni modification de la PWA.
- **Suivi :** REC-039 reste `À valider` tant que les trois parcours Discord n'ont pas été retestés sur le runtime mis à jour ; les deux parcours mobiles sont déjà validés.

## 2026-11-22 — DEV-032 → REC-039 : réalisation achevée, recette en attente

- La [CI Linux/Windows](https://github.com/goldaj/jade-vtuber/actions/runs/45043574769) du SHA `dc8f0fb2` est entièrement verte ; les vérifications Responses API et secrets sont réussies.
- **Décision du propriétaire :** le budget de sortie du modèle est la limite souhaitée de taille des documents ; le moteur PDF minimal est accepté. Ces deux points ne sont pas des manques de développement. La confidentialité et les cinq parcours texte/voix PWA/Discord seront évalués en recette.
- Conformément à la règle de suivi unique, ancienne `DEV-032` retirée des DEV actives et conservée comme référence historique ; **`REC-039` (P2, À valider)** porte seule les scénarios de recette. L'index, la passation et les guides sont alignés. Aucun changement de code ni merge sur `main`.

## 2026-11-22 — DEV-032 : génération et livraison de pièces jointes (travaux sur develop)

- **Cadrage validé par Goldaj** : mobile écrit/oral ; Discord MP/public écrit/vocal (chat associé) ; fichiers véritables, jamais une URL de réponse ; formats PDF/DOCX/TXT/CSV/XLSX/HTML et extensions texte explicites (.py, .js, etc.) ; ZIP de projets multi-fichiers ; Goldaj seulement par défaut via les liaisons d'identité existantes ; configuration `owner|allowlist|all` ; rétention 24 h sur tous les supports.
- **Implémentation :** `documents.py` (outil Responses, génération de formats, stockage privé éphémère, quota, autorisation), `messages.py` (métadonnées de réponse), `dialogue.py`, `web_search.py`, `responses_chat.py` et `orchestrator.py` (outillage partagé), `main.py` et `config.py` (démarrage et réglages). Les fichiers ne sont pas exécutés ni publiés sur GitHub.
- **Livraison :** `mobile_gateway.py`, `mobile_duplex.py`, `mobile_web/app.js` et `styles.css` (pièces jointes avec téléchargement GET privé par Bearer + Tailscale) ; `discord_text.py` (pièces jointes dans le canal d'origine ou le chat vocal, suppression différée après expiration, suivi réessayable après redémarrage).
- **Vérifications :** nouveaux tests `tests/test_jade_documents.py` pour formats, permissions, cycle de vie, refus, ZIP et expiration ; CI Linux/Windows et essais réels PWA/Discord à relever avant clôture. Le moteur PDF de secours est textuel et sa police couvre Latin-1, pas les alphabets Unicode complets ; il reste à confirmer les documents étendus et l'usage réel.
- **Limites connues :** expiration locale ferme à 24 h, suppression de messages Discord au plus tôt à l'échéance par tâche périodique (une panne Discord peut retarder l'effacement côté Discord) ; copies téléchargées/cache hors contrôle ; cette version ne réalise pas d'import de fichiers entrants ni de traitement de longues générations hors du budget de tokens. Ne jamais prétendre que la livraison est validée par une CI seule.
- **Suivi :** carte DEV-032 en cours ; [passation spécifique](handoffs/2026-11-22-chatgpt-dev032-documents.md). Pas de merge sur `main`, aucune utilisation payante de fournisseurs pour les tests.

## 2026-11-22 — Arbitrage produit : quatre cartes à cadrer, six idées retirées

- **Aucune modification de code** : uniquement les choix du propriétaire dans les sources canoniques sur `develop`. Les travaux sur les documents mobiles et la vision ne sont **pas démarrés**.
- **Catalogue :** `NEW-12` retirée car la recherche est déjà validée en `REC-038 (Done)` ; `NEW-19` écartée car Jade conserve une seule personnalité ; `NEW-30` limitée exclusivement aux sondages Twitch (aucun quiz, devinette, mini-jeu ni sondage Discord) ; `NEW-16` réorientée vers rappels d'événements envoyés par message Discord ciblé ou notification mobile autorisée. La suspension existante de Twitch est respectée.
- **Transferts sans doublon vers backlog :** `UX-19 → DEV-032` (documents téléchargeables dans le chat mobile) ; `PER-01 → DEV-033` (réception d'images), `PER-02 → DEV-034` (compréhension visuelle) et `PER-03 → DEV-035` (réaction conversationnelle). Les quatre DEV P2 sont **À qualifier**, à commencer par une discussion UX-19 avant de coder ; leurs lignes prospectives ont été supprimées.
- **Comptabilité :** catalogue `110 → 104` idées actives, dont `21 P1` ; backlog `85 → 89` tâches, `19 → 23` DEV et `11 → 15` P2. La règle du propriétaire impose désormais le retrait immédiat des idées transférées ou rejetées des tableaux actifs.
- **Vérifications :** cohérence des identifiants, liens et décomptes documentaires ; aucune activation de fournisseur, dépense API, connexion à des comptes externes ni merge sur `main`. [Passation](handoffs/2026-11-22-chatgpt-ux19-perceptions-catalogue.md).

## 2026-11-22 — NEW-20 intégré, NEW-25 supprimée du catalogue

- **NEW-20 → DEV-031 (P2, En cours)** : module déterministe de messages d'incident classés (expiration, indisponibilité de connexion, saturation, autorisation, limite fournisseur, autre). Les contenus bruts des exceptions ne sont jamais publiés, pas de nouvelle génération LLM ni de relance payante.
- **Discord :** notification uniquement pour une demande directement adressée à Jade, au canal texte/MP d'origine et si aucune tentative de remise de réponse n'a commencé ; saturation de file signalée aux demandes directes. Aucun message d'incident spontané en Twitch, vocal Discord ni autre canal, aucune double publication en cas de panne d'envoi. Callback facultatif borné à 3 secondes.
- **Mobile et HTTP local :** réponses d'erreur authentifiées enrichies par des champs stables sans modifier le contrat `error` historique ; interface plus explicite. Si la génération de voix échoue après l'obtention de la réponse textuelle, celle-ci est conservée.
- **NEW-25 retirée** : aucune évolution multilingue souhaitée pour le moment. Audit des onze thèmes sans autre ligne d'idée multilingue. Les mentions de « langage naturel » non linguistiques et le comportement français existant restent intacts.
- **Tests et recette :** scénarios hors ligne pour erreurs sans secrets, audience correcte, pas de double message ni nouvelle génération, panne du callback et échec vocal partiel. Recette réelle Discord/PWA encore nécessaire. [Passation](handoffs/2026-11-22-new20-incidents-and-new25-retirement.md).

## 2026-11-22 — VIS-07 développé ; LAT-10 inscrit dans la backlog

- **Décision du propriétaire :** VIS-07 (P1) est transféré du catalogue des améliorations vers **DEV-029 (En cours)**, et LAT-10 vers **DEV-030 (À faire)**. Les deux lignes prospectives sont supprimées sans perte d'historique ; **112 idées actives** subsistent, dont **21 P1**.
- **VIS-07 :** sur le même arbitre que VIS-04, délai d'hystérésis **6500 ms** pour une sortie momentanée du viewport. Retour avant délai : aucune interruption ni redémarrage du ticker. Sortie prolongée : pause graphique effective. Onglet masqué/démontage : arrêt immédiat, sans dépenser 6,5 s de GPU en arrière-plan. Reprise d'une vraie pause : remise au neutre de l'expression, sans rechargement de Cubism ni replay d'Idle, avec voix, bouche, message et mémoire indépendants.
- **Qualité :** tests Node à horloge simulée des oscillations de visibilité, des hard stops et de la neutralisation, lancés dans le workflow Linux et Windows existant ; vérification de la cohérence backlog/catalogue et aucun changement de `main` ou des délais TTS. **Recette Android réelle encore requise** avant de clôturer.
- **LAT-10 :** pas encore développé ; inventorier les délais réellement configurés avant toute harmonisation. [Passation et critères](handoffs/2026-11-22-vis07-lat10-quickwins.md).

## 2026-11-22 — RTE-12 repris : preuves de livraison strictement passives

- La première implémentation DEV-028 était trop intrusive : elle transformait les résultats de `on_reply` et de `_speak_progressive` pour transmettre des accusés à l'orchestrateur. Cette conception a été **rejetée** après réexamen demandé par le propriétaire.
- Les contrats d'origine ont été restaurés depuis la version stable de `main` : aucune livraison, synthèse vocale, reprise WAV, décision de mémoire ni réponse du modèle ne dépend désormais des preuves RTE-12.
- Observateurs ajoutés uniquement **après** confirmation Discord API texte, sortie ffplay avec code 0 ou accusé existant du pont vocal Discord ; corrélation par `ContextVar` du tour, sans contenu privé.
- Les erreurs des deux journaux sont absorbées indépendamment sans influencer les transports. `handoff_completed` reste une information de passage au callback, et non un accusé de réception. Les événements `transport_accepted` et `playback_completed` ne constituent pas une lecture ou une audition humaine garantie.
- Tests de pannes de logs, faux accusés, sortie ffplay, session Discord rejetée, avec le reste de la CI multi-OS. **DEV-028 reste ouvert** pour vérification fonctionnelle sur le Discord réel. [Passation](handoffs/2026-11-22-chatgpt-vis04-rte12.md).

## 2026-11-22 — DEV-027 et DEV-028 : deux P1 engagées

- **Promotion unique après sauvegarde de `develop` sur `main` (PR #41) :** VIS-04 → DEV-027 et RTE-12 → DEV-028, statut `En cours`. Les deux anciennes lignes actives sont supprimées du catalogue prospectif, désormais **114 idées** (23 P1), tout en conservant leurs références historiques.
- **DEV-027 :** `mobile_web/avatar.js` synchronise le ticker PixiJS et `model.autoUpdate` avec visibilité de l'onglet, IntersectionObserver, attachement DOM et présence d'une surface réelle. La pause ne touche pas la voix ni la conversation. Test de cycle de vie JS (démarrage caché, visibilité, hors-champ, retour, absence de l'API d'observation), exécuté sans SDK réel ni coût IA.
- **DEV-028 :** `turn_logging.py` conserve la planification et le handoff mais ajoute des preuves typées distinctes, uniquement après accusé Discord API ou fin réelle de lecture ffplay/Discord. `orchestrator.py` recoupe toute preuve avec les destinations prévues ; `main.py` ne transforme ni mobile/HTTP, ni Twitch sans accusé, ni une destination révoquée en réussite. `output.py` distingue stream simplement traité et échantillons réellement consommés. Aucun texte privé inscrit dans ces événements.
- **QA :** tests de livraison, preuve, annulation et refus de fausse confirmation ; nouveau test navigateur Node dans la CI multi-OS. Recette réelle Android/Discord et mesure batterie non réalisées à ce stade. Détails dans la [passation](handoffs/2026-11-22-chatgpt-vis04-rte12.md). CI générale Linux/Windows sur le HEAD final à contrôler avant un passage éventuel en REC.

## 2026-11-22 — Réparation de CI avant les quick wins VIS-04 et RTE-12

- **Base sauvegardée avant modification :** promotion explicite de `develop` `96b7157` sur `main` via [PR #41](https://github.com/goldaj/jade-vtuber/pull/41), merge `6afbe0c`. Aucun correctif CI ni nouveau développement VIS/RTE inclus dans ce point de référence.
- **Suite de tests mémoire :** retrait de la dépendance implicite à `pytest` dans deux modules découverts par `unittest` ; assertions anciennes réconciliées avec la décision propriétaire (Core L3 décidée par Jade, lectures globales, demandes L2 obligatoires seulement par propriétaire authentifié, absence d'obligation de citation exacte). Les tests maintiennent les protections de profil, provenance, isolation d'écriture et rejet des JSON invalides. Mise à jour des versions attendues de migration SQLite vers `SCHEMA_VERSION` v8.
- **Export privé :** le nouvel arrière-plan et le rideau WebP de DEV-010 sont inclus dans l'allowlist de l'aperçu privé, avec validation du format de fichier, sans ajout d'assets tiers ni de secrets.
- **Périmètre :** adaptation des tests aux comportements approuvés et correction du packaging de l'aperçu privé. Aucun nouveau connecteur, fournisseur, accès ou appel API. CI complète Linux/Windows à confirmer sur le commit final du lot avant de déclarer la réparation terminée.

## 2026-11-22 — OPS-015 suspendu jusqu'au retour de tokens Codex

- **Décision propriétaire :** passage de **OPS-015** (étude des redondances artistiques et outils inutiles) de `À faire` à **`Bloqué`**, pour reprendre lorsque le quota de tokens Codex sera suffisant.
- **Reprise :** sur nouvelle décision du propriétaire, sans échéance ni réactivation automatique ; aucune analyse d'assets ou purge effectuée par ce changement.
- **Périmètre :** documentation de backlog et de suivi uniquement, sans changement du runtime ni de `main`.

## 2026-11-22 — DEV-010 clôturé après validation explicite du propriétaire

- **Décision :** le propriétaire confirme « ok c'est validé » après la fusion de la [PR #40](https://github.com/goldaj/jade-vtuber/pull/40), couvrant le rideau, la fumée et les ombres animés du décor mobile. La carte **DEV-010 est passée de `À valider` à `Done`**.
- **Traçabilité :** tests ciblés de génération graphique, géométrie, animation et cycle de vie réussis ; réserves visuelles documentées dans [la revue DEV-010](handoffs/2026-11-22-dev010-living-room-design.md). Les scénarios Android individuels ne sont pas détaillés dans le retour propriétaire et ne sont pas déclarés tous vérifiés séparément.
- **Portée :** documentation de suivi uniquement. Aucun changement du runtime, de `main`, ni des autres tickets ; les échecs de tests mémoire préexistants restent distincts.

## 2026-11-22 — DEV-010 : décor mobile vivant (rideau, fumée, ombres)

- **Animation :** rideau extrait en WebP transparent et animé autour des attaches, reconstruction stationnaire des pixels occultés, feuillage SVG sur deux plans avec vent commun à plusieurs fréquences, volutes SVG de vapeur bien plus amples et reflets conservés.
- **Performance et accessibilité :** transformations et opacité pilotées au maximum à 30 mises à jour DOM/s, pause hors écran/onglet caché, respect de `prefers-reduced-motion`, retour intégral à l'illustration fixe si une couche ne se charge pas. Aucune API ou dépense IA supplémentaire.
- **Qualité :** génération hors ligne reproductible de deux calques (`room-backdrop.webp` 247 534 octets et `room-curtain.webp` 49 110 octets au dernier relevé de l'étude, valeurs susceptibles d'évoluer), tests Node (amplitudes, cycle de vie, repli) et Python (géométrie et intégrité WebP) réussis sur [la branche isolée](https://github.com/goldaj/jade-vtuber/actions/runs/45025747344). Scanner de secrets PR #40 vert. Les suites CI générales demeurent rouges sur les **mêmes erreurs mémoire déjà présentes sur `develop`** avant cette PR ([baseline](https://github.com/goldaj/jade-vtuber/actions/runs/45024566506)).
- **Backlog :** DEV-010 passe de `À faire` à `À valider`, car l'essai visuel réel sur Android, différents cadrages et mouvement réduit reste nécessaire avant clôture. La peinture du fond derrière le tissu est une approximation prudente et peut bénéficier d'une retouche artistique dédiée.
- **Revue :** [expertises simulées, coûts et réserves](handoffs/2026-11-22-dev010-living-room-design.md). Aucune modification des moteurs de conversation, de mémoire, de l'avatar, des secrets, ni de `main`.

## 2026-11-22 — UX-19 : documents téléchargeables dans le chat mobile (idée P2)

- **Décision propriétaire :** création de **UX-19 (P2 / P)** dans le seul catalogue des améliorations prospectives, pour permettre à Jade de générer des documents et de les envoyer comme pièces jointes téléchargeables directement dans le chat de la PWA mobile.
- **Périmètre prospectif :** génération backend des fichiers, transfert privé et téléchargement mobile, formats adaptés à la demande et gestion de leur durée de conservation. Complément distinct de la bibliothèque documentaire de consultation NEW-13.
- **Suivi :** ajout dans `docs/ameliorations/06-PRODUIT-MOBILE.md`, décompte mis à jour à 5 idées mobiles et 114 idées actives au total. Aucune entrée créée dans la backlog, aucun développement ni déploiement.

## 2026-11-22 — REC-038 validée par le propriétaire : recherche Internet Jade

- **Statut :** REC-038 passée de `À valider` à **`Done`** à la demande explicite du propriétaire, qui confirme que la connexion Internet de Jade fonctionne sur son environnement réel.
- **Preuves :** code Tavily et journaux par session intégrés sur `develop` ; tests automatisés dédiés à la recherche web réussis dans la [CI de `8a801035`](https://github.com/goldaj/jade-vtuber/actions/runs/45022523090) ; [scan des secrets réussi](https://github.com/goldaj/jade-vtuber/actions/runs/45022523125). La CI globale reste rouge sur des tests mémoire préexistants (Linux : 12 échecs, 5 erreurs).
- **Réserves transparentes :** le propriétaire valide le fonctionnement de base, sans attestation distincte de tous les scénarios spécifiques de REC-038 (PWA, oral, limites maximales, journal après plusieurs redémarrages, erreurs réseau). Ces scénarios ne sont pas qualifiés de réussis et restent consultables dans la carte clôturée.
- **Périmètre :** seule la documentation de suivi change ; aucun code, secret, paramètre privé ni branche `main` modifié.

## 2026-11-22 — Historique de recherches web par session

- **Décision :** abandon du journal web unique au profit d'un dossier privé dédié à côté de la mémoire (`D:/Jade/private/jade-web-search/` sur le PC de référence). Un JSONL horodaté et suffixé par PID est créé à chaque démarrage live avec web activé, comme les logs Jade généraux.
- **Technique :** `SearchJournal.start_session` crée un fichier neuf en mode exclusif avant les recherches, avec un événement `session_started` ; journal append-only avec fsync par événement et refus de requête réseau si l'écriture initiale échoue. Le chemin exact figure dans `web_search_journal_started` au démarrage.
- **Configuration :** nouvelle option `JADE_WEB_LOG_DIR`, l'ancienne `JADE_WEB_LOG_PATH` est prise en charge en remplaçant le fichier `.jsonl` par un répertoire voisin sans extension. Aucune migration automatique ni modification de l'ancien historique.
- **QA :** tests hors ligne ajoutés pour la création par démarrage sans recherche, deux fichiers distincts, préservation de l'ancien journal, compatibilité de configuration et impossibilité de journaliser. Résultat CI à contrôler après push. La recette physique Tavily reste REC-038 `À valider`.
- **Limites :** pas de purge automatique, données de recherches sensibles, conservation privée exclusivement sur le PC.

## 2026-11-22 — Recherche Tavily : dix appels possibles par tour

- **Décision produit :** à la demande du propriétaire, le plafond par défaut passe de **3 à 10 recherches par tour** ; Jade garde sa liberté de n'effectuer aucune recherche ou seulement celles nécessaires.
- **Configuration :** valeurs par défaut cohérentes dans `Settings`, `Settings.load()` et `WebSearchService` ; plage explicite `JADE_WEB_MAX_PER_TURN=1..10` inchangée. Une valeur privée explicite continue de primer sur le nouveau défaut.
- **Qualité :** test hors ligne de dix recherches acceptées et de la onzième refusée, avec journalisation. Pas de changement d'API, de fournisseur, de prompt ni de journal. Augmenter la limite augmente le plafond potentiel de crédits Tavily et la latence si Jade multiplie les appels.

## 2026-11-22 — Recherche web : réponses naturelles sans rafale d'URL

- **Retour propriétaire :** Jade ajoutait trop souvent les liens des pages Tavily dans ses réponses, parce que `WEB_PROMPT` l'encourageait à citer les URL.
- **Correction ciblée :** dans `src/jade_runtime/web_search.py`, aucune URL ou liste de liens par défaut. Un lien n'est fourni que sur demande explicite ou s'il est indispensable à l'action, avec le strict minimum. À l'oral, aucun lien prononcé sauf demande.
- **Sans régression de la recherche :** les pages consultées restent attribuées et journalisées en JSONL avec leurs URL ; ni adaptateur Tavily ni protocole de recherche modifiés.
- **Contrôle :** nouvelle assertion de politique dans `tests/test_jade_web_search.py` ; CI hors ligne à consulter après push. La recette REC-038 réelle sur le PC reste `À valider`.

## 2026-11-22 — Recherche Internet Tavily interchangeable et journal privé

- **Décision produit :** recherche web facultative à la demande explicite du modèle conversationnel, sans recherche en veille. Désactivée tant que `JADE_WEB_ENABLED=1` et une clé Tavily privée ne sont pas configurés.
- **Architecture :** contrat `SearchProvider`, implémentation `TavilyProvider` isolée, `WebSearchService` avec 3 appels maximum par tour par défaut. `jade_web_search` coexiste avec les outils mémoire, même sans profil mémoire ; parcours texte et streaming vocal.
- **Journal exhaustif des tentatives passant par l'outil :** JSONL privé persistant hors Git, horodatage UTC, motif, requête, ID de tour, canal, fournisseur, statut, durée, crédits annoncés et résultats. Écriture `started` synchronisée sur disque avant tout réseau, puis `success` / `failed` / `rejected`. En cas d'arrêt brutal après `started`, l'enregistrement reste consultable.
- **Coûts et sécurité :** mode Tavily basic, cinq extraits au plus, pas de HTML brut ni réponse générée par Tavily, pas d'appel de recherche pour les conversations ordinaires. Clé masquée et préflight sans réseau. Aucun secret/version privée commités.
- **Validation :** tests hors ligne nouveaux dans `tests/test_jade_web_search.py`, CI Linux/Windows à vérifier après intégration ; essai Tavily avec la vraie clé et recette Discord/PWA sur PC à faire par le propriétaire. Suivi unique REC-038.

## 2026-11-22 — Branche expérimentale isolée : continuité privée, mémoire et métrologie

- **Périmètre :** travaux `DEV-021` à `DEV-026`, `DEV-010/020` et inventaire lecture seule `OPS-015` sur `feature/jade-multicanal-memoire-observabilite-20261122`. PR #38 brouillon, aucune modification de `develop` ou `main`.
- **Continuité et permissions :** tâches privées du propriétaire, reprise persistante depuis une session/identité liée, quelques commandes françaises univoques et envoi Discord uniquement sur destination explicitement autorisée. Ambiguïtés et actions autonomes supplémentaires exclues.
- **Mémoire/personnalité :** rappel ciblé local, cache anticipé et invalidation SQLite, préférence récente cohérente ; les demandes L2 forcées du propriétaire ne déterminent pas la personnalité de Jade. Aucun moteur ou appel LLM supplémentaire en veille.
- **Métrologie :** quantiles p50/p95 du runtime, durée STT mobile pré-runtime, tokens d'entrée/sortie réellement fournis par Responses. Ne pas déduire un coût USD exact ni une audition effective du premier son sans preuve.
- **Mobile et exploitation :** superviseur indépendant en loopback pour déploiement de branche choisi et reprise du processus, interface privée correspondante. Rideau mobile en repli statique tant que les calques artistiques indépendants ne sont pas disponibles. Audit d'assets non destructif.
- **Correctif de régression :** une validation STT a d'abord provoqué un HTTP 503 vocal (`math` manquant dans `messages.py`) ; import ajouté avant la livraison, et tests de non-régression PWA restaurés.
- **Recette :** 637 tests hors ligne réussis (14 ignorés) sur la suite économique du commit `04f2b10d` et sur les commits suivants de code ; validation physique Windows, Android/Discord et reconstruction CI multi-OS séparée. Les limites exactes sont dans [la passation](handoffs/2026-11-22-dev021-026-multicanal-memoire-latence.md). **Aucun ticket Done** à ce stade.

## 2026-11-22 — QA : fermeture du streaming et curation mémoire sans doublon

- **Correctif runtime (streaming) :** `OpenAIServices` et `ResponsesChat` ferment explicitement les générateurs async imbriqués lors de `aclose()`, y compris le suivi après appel d'outil. Le flux transport est fermé dans le `finally` de `_stream_text`.
- **Correctif runtime (mémoire) :** une demande explicite de souvenir ne déclenche plus de seconde curation LLM en arrière-plan. Le propriétaire vérifié dispose de la file L2, les autres de l'outil volontaire du LLM conversationnel.
- **Backlog :** `OPS-012` est `Classée sans suite`, conservée dans les vues historiques mais pas dans l'index opérationnel actif. Contrôle du graphe de dépendances conservé ; fixture de dépendance inconnue munie de l'en-tête canonique.
- **Confidentialité :** le test attend désormais un contenu privé intégralement masqué, sans balise d'intention explicite. Aucune réduction de la protection du runtime.
- **Validation :** revalidation sur Linux et Windows, sans frais OpenAI.

## 2026-11-22 — QA : tests d'identités et d'écritures mémoire non bloquantes

- Anciennes recettes automatiques `test_jade_explicit_memory_request.py` supposaient que toute demande vocale/Discord imposait un souvenir et que SQLite avait fini avant la réponse. Le contrat validé est différent : Goldaj vérifié force L2 uniquement, Jade décide librement pour les autres et les écritures sont différées.
- Les tests distinguent désormais reconnaissance de la demande, refus de forçage non-propriétaire, appel volontaire `jade_save_memory`, retour asynchrone, isolation des comptes Discord, unicité des mémoires et annulation après changement de profil.
- En cas de panne SQLite, l'accusé de **mise en file** demeure (décision produit) tandis que le test vérifie l'absence de persistence. Aucun assouplissement des protections liées au consentement.
- Validation hors ligne en CI requise ; aucun périphérique physique ni appel facturable utilisé.

## 2026-11-22 — QA : contrat des outils mémoire Responses

- Les quatre tests de `tests/test_jade_openai_memory_tools.py` utilisaient les objets `chat.completions` retirés de Jade. Simulations actualisées en `responses.create` sans changer le but de chaque contrôle : abstention sans appel supplémentaire, continuation après écriture différée, aucun argument d'outil divulgué dans le flux, fermeture des streams.
- Les assertions suivent le contrat validé : l'acceptation de la tentative est immédiate et le résultat SQLite est observé à la fermeture de la tâche, sans imposer une confirmation bloquante au LLM.
- Suite GitHub Linux/Windows à observer avant clôture.

## 2026-11-22 — QA : isolement des journaux et contrats mémoire/asynchronisme

- **Journalisation :** les tests de compatibilité `jade.conversation` isolent le mode sans fichier de session, au lieu de dépendre de l'état global laissé par les autres tests. Aucune émission de texte privé vers la console réelle n'est ajoutée.
- **Voix synthétique :** le mock LLM du scénario PCM/micro fictif utilise maintenant la Responses API et vérifie la même génération unique, sans périphérique réel.
- **Souvenirs volontaires :** le test confirme qu'une demande humaine de Core ne crée pas une Core par commande ; une action volontaire distincte de Jade peut toutefois le faire, et les éléments provenant du contexte antérieur n'exigent pas une citation du dernier tour.
- **Budget/raisonnement :** le test du contrat actuel vérifie `reasoning.effort=low`, `max_output_tokens=2048`, `store=false` et le streaming Responses.
- **Validation :** suite offline à relancer. Les tests d'isolement multicanal/consentement restent prioritaires.

## 2026-11-22 — QA : adapter les simulations OpenAI au contrat Responses

- **Diagnostic :** des tests de conversation, streaming et isolation de clés simulaient encore `chat.completions` alors que Jade utilise la Responses API. Échecs de `FakeClient.responses` absente, pas une preuve d'échec du backend actuel.
- **Correction :** adaptation des réponses synthétiques `status=completed`, `output_text`, événements `response.output_text.delta` / `response.completed`, et du chemin HTTP `/v1/responses`. Contrôles d'un flux tronqué et de fermeture `aclose()` conservés.
- **Vérification :** tests concernés à rejouer en CI Linux/Windows ; pas de requête réelle, ni modification du runtime ou d'assertion de confidentialité.

## 2026-11-22 — QA : restauration SQLite v5 et fiabilisation des vérifications hors ligne

- **Sauvegarde/restauration :** `memory_transfer.py` accepte désormais explicitement les archives de schéma SQLite v5, déjà produites par `export_memory` et validées par `_check`. Hachage SHA-256, schéma, intégrité SQLite, non-écrasement et limites de taille restent obligatoires. Tests existants REC-025 et migration anciens schémas à contrôler en CI.
- **Backlog :** le contrôleur documentaire ne lit les ID que dans le tableau canonique `| ID | Prio | Jalon | Statut |`, et non dans les tableaux de résultats des recettes ; dépendance historique `DEV-011` de `DEV-012` renvoyée vers `REC-026`.
- **Tests :** tests fonctionnels de Luna ne nécessitent plus d'import `pytest` pour être découverts par `unittest` ; le défaut du budget par défaut est mis à jour de 320 vers 2048 dans une assertion ancienne (contrat du 22/11).
- **Vérification :** diagnostic à partir des erreurs réelles GitHub Actions `45001055153`; exécution et vérification complète à confirmer par les workflows sur ce commit. Aucun appel API payant ni test matériel.

## 2026-11-22 — QA : supprimer un faux positif TOKEN_PATTERN sans affaiblir le scanner

- **Diagnostic :** le préflight Linux/Windows du SHA 5feb9a1b7a2b échouait avant les tests avec `BLOCKED: TOKEN_PATTERN` ; un littéral de test de confidentialité dans `tests/test_session_diagnostics.py` avait le format d'une clé.
- **Correction :** construire la même valeur de démonstration en trois segments à l'exécution du test, sans garder de token complet dans le code suivi. Le comportement du test et la détection `TOKEN_PATTERN` du scanner restent inchangés.
- **Vérification :** inspection statique du motif incriminé et des journaux GitHub Actions. Préflight et suite générale doivent être observés sur le commit après push ; aucun succès CI ou test local n'est anticipé.

## 2026-11-22 — REC-006 et REC-029 : clôture produit explicite sur develop

- **Décision du propriétaire :** après revue des logs réels du 22/11, les deux cartes passent de `À valider` à **`Done`**, sans développement ni test supplémentaire requis pour la clôture.
- **Discord REC-006 :** trois recouvrements PCM/TTS positifs constatés. Le tour long dont la synthèse vocale a échoué reste documenté : `tts_completed_ms=null`, `playback_completed=false`, et les statuts de transfert ne constituent pas une preuve d'audition. Le propriétaire accepte cette réserve. **Early Voice demeure refusé/désactivé**, sans requalification.
- **Mobile REC-029 :** deux recouvrements PCM/TTS sur WebSocket avec émission terminée ; les logs navigateur Android ne sont pas joints et les autres scénarios de recette ne sont pas tous prouvés. Le propriétaire accepte de clore la carte sans les exiger.
- **Traçabilité :** `docs/backlog/02-RECETTE.md` mis à jour et [analyse réelle](handoffs/2026-11-22-chatgpt-rec006-rec029-test-log-analysis.md) conservée. **Pas de modification runtime ni de main** : c'est une décision de recette, pas une prétention de résolution des défauts historiques.


## 2026-11-22 — Correctif détecté par la suite REC-029

- **QA :** la première exécution des nouveaux tests ciblés donne 47 réussites et un échec de fermeture du flux PCM lors de l'abandon du lecteur mobile. L'itérateur externe ne refermait pas automatiquement le générateur async interne après `aclose()`.
- **Correctif :** `mobile_audio_stream.speech_events` ferme explicitement l'itérateur interne dans un `finally`, puis restaure le contexte de mesure même si la fermeture échoue. Aucun changement de protocole ou d'appel API ; le test historique de fermeture reste l'acceptation ciblée.


## 2026-11-22 — Exécuter les recettes ciblées même quand l'ancien preflight bloque la CI principale

- **QA :** le workflow existant `jade-responses-migration.yml` inclut désormais les tests hors ligne `test_jade_pcm_timing.py`, `test_jade_output_budget.py` et `test_jade_mobile_audio_stream.py`, en plus de ses 29 tests de régression existants. Déclenchement également sur changements mobile, timing, dialogue et nouveaux tests.
- **Sécurité :** le contrôle `TOKEN_PATTERN` du workflow principal reste strictement inchangé et bloquant. Le workflow ciblé n'appelle pas les API payantes ; il donne un retour sur la correction sans présenter l'échec du scanner historique comme un échec de ces tests.


## 2026-11-22 — REC-029 : mesure PCM mobile et repli vocal des réponses longues (develop)

- **Mobile :** émission PCM HTTP NDJSON ou WebSocket mesurée côté serveur avant le signal TTS `response.done`. La console serveur émet `rec029_mobile_pcm_progress` avec délai d'envoi du premier paquet, fin TTS et verdict ; la console du navigateur Android émet `rec029_mobile_pcm_client`, distinguant premier paquet reçu, premier démarrage WebAudio **programmé**, et fin du flux. Les horloges distinctes PC/téléphone ne sont pas directement soustractibles et ne garantissent pas l'audition matérielle. Aucun audio, token, transcript ni identifiant n'est ajouté à ces événements.
- **Conversation :** les demandes exigeant une réponse longue sont résumées à l'avance en 3 à 5 phrases (~120 mots / ordre de grandeur 320 tokens visibles). Si la Responses API épuise son budget total (raisonnement inclus), Jade produit une phrase standard courte, transmise au TTS habituel, **sans deuxième requête LLM** ni exécution de mémoire sur résultat incomplet. Les vrais échecs réseau et API restent visibles ; Early Voice reste désactivé par défaut.
- **Budget :** plafond technique total par défaut 2048 depuis le correctif précédent ; seuls les tokens effectivement produits sont consommés, pas automatiquement le plafond. `JADE_MAX_COMPLETION_TOKENS` privé conserve priorité. Le TTS de la phrase de repli reste payant quand activé.
- **Modules :** `pcm_timing.py`, `mobile_audio_stream.py`, `mobile_gateway.py`, `mobile_duplex.py`, `mobile_web/app.js`, `responses_chat.py`, `dialogue.py` et tests. Les tests hors ligne et la CI doivent être vérifiés après publication ; aucun appel API réel ni validation Android physique revendiqués. REC-029 et REC-006 restent `À valider` ; les CI antérieures étaient déjà bloquées par `TOKEN_PATTERN` sans modification de ce contrôle.


## 2026-11-22 — Réponse longue tronquée : budget de sortie Luna (develop)

- **Incident réel :** 22/11/2026 08:20 et 08:21, tours Discord vocal 1 et 3 en `status=incomplete` / `reason=max_output_tokens`. Ce n'était pas un plantage du processus ni un défaut TTS : le tour vocal 2 a poursuivi normalement et a confirmé `rec006_pcm_progress=progressive_confirmed` côté lecteur.
- **Cause probable :** `max_completion_tokens=320` par défaut sur la Responses API, partagé entre raisonnement et texte visible ; une réponse longue peut épuiser ce plafond avant toute livraison. La configuration privée peut surcharger cette valeur et n'a pas été inspectée.
- **Correctif préventif :** plafond par défaut relevé à 2048, **sans appel API supplémentaire, retry automatique, changement du niveau de raisonnement ou d'Early Voice**. Ce plafond ne force pas Jade à produire 2048 tokens et peut rester surchargé par `JADE_MAX_COMPLETION_TOKENS`. Le journal de démarrage affiche la valeur réellement chargée ; en cas de nouveau dépassement, `llm_output_limit_reached` indique le budget et les consommations connues sans texte privé.
- **Fichiers :** `config.py`, `main.py`, `responses_chat.py`, tests unitaires du budget et des traces, guide des logs. **Limites :** aucun appel API réel ni test PC ; une sortie dépassant encore 2048 peut rester incomplète. La CI existante échouait déjà au contrôle `TOKEN_PATTERN` sur le commit précédent ; ce contrôle n'a pas été contourné.


## 2026-11-22 — REC-006 : preuve de progression PCM Discord (develop)

- **Besoin :** comparer les instants techniques de la première trame PCM non silencieuse consommée par le lecteur Discord et de la réponse TTS OpenAI terminée, sans confondre ces horodatages avec la durée totale du tour ou le son réellement entendu chez un utilisateur.
- **Implémentation :** trace par lecture vocale et contexte asynchrone dans `pcm_timing.py`, mesure monotone dans `discord_pcm.py`, récapitulatif `rec006_pcm_progress` dans `discord_voice.py`, marquage de `response.done` accepté dans `realtime_tts.py`. Une seule ligne synthétique par tentative PCM, même interrompue ; champs numériques, booléen de recouvrement et verdict, sans voix, transcription, identité ni secret.
- **Périmètre :** pas de changement de routage, de synthèse, de coût API, de mode Early Voice ou de réglage privé. `JADE_EARLY_VOICE=0` reste le choix du propriétaire. Le compteur commence au démarrage de la lecture Discord, pas au début de la question ; une trame consommée localement ne prouve pas l'audition distante.
- **Vérification :** tests hors ligne ciblés ajoutés ; CI Windows/Linux et essai Discord réel à constater après le push. REC-006 reste `À valider` ; aucune mesure réelle ni acceptation du PCM anticipée.


## 2026-11-21 — Retrait de la commande d'oubli global et du blocage Discord (develop)

- **Décision produit :** suppression complète de `!jade-memoire oublier` et du mécanisme de blocage de réinscription Discord. Les comptes Discord vérifiés continuent à s'inscrire automatiquement ; l'activation Twitch, la déliaison, les historiques L1, souvenirs L2/L3 et les commandes de suppression ciblée des Core sont préservés.
- **Base :** SQLite passe du schéma v4 au v5. L'ouverture d'une base existante supprime exclusivement la table obsolète `memory_auto_enrollment_blocks` ; elle ne supprime aucun souvenir, identité, lien ou historique. La migration v4->v5 ne recalcule pas les dates d'expiration des souvenirs ordinaires. Les anciennes archives v1-v4 restent importables, le v5 est exportable.
- **Code et tests :** retrait des commandes et fonctions d'oubli global dans `memory_service.py` et `memory_store.py`, mise en cohérence du sélecteur Discord, de `memory_transfer.py` et des tests mémoire ; ajout de contrôles migration v4, commande retirée et suppression ciblée.
- **Effet opérationnel :** un utilisateur auparavant bloqué par la table legacy pourra de nouveau être inscrit automatiquement sur Discord après migration ; aucune donnée de mémoire privée n'est transférée à GitHub. Le retrait du libre-service d'effacement global implique de définir séparément une procédure humaine pour traiter les demandes légales de suppression des données.
- **Vérifications :** contrôle statique des extraits modifiés ; la CI Linux/Windows et la recette sur l'instance personnelle doivent être observées sur le SHA d'intégration. Aucun test physique ni appel API facturé revendiqué.


Ce document est **la seule pièce documentaire systématiquement exigée en CI** pour les changements techniques. Les guides, atlas et passations sont révisés uniquement quand le comportement ou les procédures qu'ils décrivent changent. Une entrée indique les faits vérifiés ; un ancien journal ne remplace pas le code.

## 2026-11-21 — DEV-012 : action volontaire de mémoire L2/L3 dans le dialogue (develop)

- **Produit / architecture :** Jade conversationnelle connaît l'action native et facultative OpenAI `jade_save_memory` (niveau 2 ordinaire 365 jours, niveau 3 Core sans purge). Le modèle décide s'il l'appelle ; la couche `Dialogue` et le service `OpenAIServices` gèrent les appels d'outils en texte comme en streaming vocal, puis une réponse finale. Aucune requête API supplémentaire quand le modèle n'utilise pas l'outil ; une requête additionnelle de continuation lorsqu'il l'appelle.
- **Confidentialité et preuve :** `MemoryService.prepare_memory_action` épingle l'identité consentante avant génération, vérifie la citation littérale, les longueurs, les secrets et la portée imposée par le transport. La base SQLite existante écrit réellement via `put`/`put_self_core` et filtre les doublons. Une demande explicite humaine demeure exclusivement ordinaire via DEV-011 ; la création de Core autobiographique ne concerne que le profil propriétaire vérifié.
- **Retour d'exécution :** le LLM reçoit le statut réel de l'outil avant sa réponse finale (`enregistré`, `déjà présent`, `refusé`, `échec`). Une action tentée n'est pas reprise par la curation asynchrone sur le même tour ; la curation différée d'origine continue indépendamment sans réinjection de résultats, conformément à l'assouplissement accepté par le propriétaire le 21/11.
- **Code et tests :** `memory_actions.py`, `memory_service.py`, `openai_services.py`, `dialogue.py`, `orchestrator.py`, tests `test_jade_voluntary_memory_tools.py` et `test_jade_openai_memory_tools.py`. Documentation DEV-012 et état fonctionnel adaptés. Aucun changement du schéma SQLite ni activation de connecteur.
- **Correctif révélé par CI initiale :** un `AsyncMock` de dialogue fabrique des méthodes à la demande, y compris `complete_with_tools`, même si le backend simulé n'offre pas cette capacité. Désormais la détection vérifie la méthode définie par le type réel, sans appel à un attribut factice ; les tests historiques de mémoire et d'export de démo retrouvent leur backend habituel.
- **Limites et vérifications :** tests automatiques sans appels facturés et CI Linux/Windows à contrôler sur le SHA d'intégration ; pas de preuve sur le PC réel, Discord, Android, TTS ou factures. Tester le temps de continuation si Jade décide d'utiliser l'outil ; un appel d'outil pendant une réponse vocale peut retarder le premier mot.

## 2026-11-21 — Revue transversale de mémoire, initiatives, budget et MP Discord (PR #35)

- **Architecture et produit :** audit de la PR #34 sous les angles PO, coûts API, Python/SQLite, confidentialité, Discord et audio mobile. Initiatives toujours actives par défaut, sans quota numérique ni polling LLM de veille. Une discussion entre tiers n'efface plus l'état « Jade ignorée » ; il faut une adresse directe ou un bref acquiescement dans les deux minutes.
- **Confidentialité :** suppression du rappel de souvenirs individuels dans les prompts à destination des salons Discord publics, vocaux ou Twitch ; base de mémoire conservée et rappels privés autorisés en DM vérifié ou sur les canaux du propriétaire. Une sortie `core_self` de curation hors identité propriétaire est rejetée, jamais convertie en souvenir d'un tiers.
- **Personnalité et coûts :** les préférences d'un tiers ne deviennent plus des traits de Jade ; repères limités aux souvenirs dont Jade est explicitement le sujet et à son autobiographie autorisée. La curation groupée ignore davantage de formules de politesse et répétitions locales avant appel payant. Les compteurs financiers restent des réservations estimatives, non une facture garantie.
- **Discord MP, DEV-019 P0 :** le canal DM du message entrant, vérifié, est conservé dans un cache borné comme destination de secours si `get_channel` échoue. Une réponse non effectivement envoyée provoque un échec de livraison et n'est plus mémorisée comme conversation remise. Les MP ne sont plus affichés dans le terminal général. Le cycle de dépendances REC-002/REC-005/DEV-019 est retiré des prérequis, mais ces recettes demeurent liées.
- **QA et limites :** SHA final `b1a80899` : [rebuild Linux + Windows](https://github.com/goldaj/jade-vtuber/actions/runs/44942772613), [tests économiques](https://github.com/goldaj/jade-vtuber/actions/runs/44942772623) et [scan secrets](https://github.com/goldaj/jade-vtuber/actions/runs/44942772625) **tous réussis**, PR #35 fusionnée en `49f2e686` sur `develop`. Vrai Discord/Android/Tailscale et attribution réelle des factures restent à recetter ; `main` inchangée.
- **Données privées et anti-boucle :** les traces de diagnostic masquent désormais les textes/réponses/identifiants des MP Discord, requêtes mobiles, microphone et API privée, en laissant les temps et destinations techniques exploitables ; les messages émis par d'autres bots Discord sont rejetés en entrée avant routage LLM.
- **Modules :** `initiatives.py`, `discord_text.py`, `discord_voice.py`, `memory_batch.py`, `memory_service.py`, `personality_evolution.py`, `main.py`, tests et documents métier/architecture.

## 2026-11-21 — Compatibilité Windows et concurrence du backlog pour la PR #34

- Gestion du fuseau horaire des budgets et des événements : tests CI Windows installent `tzdata` pour des transitions heure été/hiver déterministes ; fallback vers la zone locale du PC Windows si les données IANA sont absentes, sans bloquer le lancement de Jade.
- Les six cartes ECO passent à **DEV-013…DEV-018** ; la **DEV-012** P1 reçue indépendamment sur `develop` (écritures mémoire L2/L3 conscientes) est préservée, sans modification de son périmètre ni de son statut.
- Vérifications : Linux déjà vert pour la PR ; Windows à recontrôler sur le SHA final ; aucune recette matérielle inventée.

## 2026-11-21 — Six évolutions économiques : mémoire, sociabilité, initiatives, voix et mobile (PR #34)

- **Produit :** historique SQLite intégral 24 h **conservé**, avec sélection lexicale locale plafonnée pour le prompt ; L1 7 j, L2 ordinaire 365 j, Core sans expiration inchangés. Curation par lots de 3 événements au plus, délai court et validation autonome des Core. Personnalité enrichie uniquement des souvenirs autorisés, sans nouvel appel IA.
- **Sociabilité :** sélection locale prioritaire ; second avis LLM facultatif uniquement sur questions ambiguës de groupe et seulement avec budget USD de classification configuré. Aucun polling du modèle en période sans intervention humaine.
- **Initiatives :** déclencheur de première version = arrivée d'un humain dans le vocal Discord de Jade, qui peut émettre un salut **vocal** via le TTS existant si le membre est toujours présent, ou écrit en repli, **sans préalable verbal**. Le tour événementiel ne crée aucune mémoire attribuée au nouvel arrivant. **Si personne ne répond, aucune relance autonome dans ce salon** ; un message humain réel ou la réouverture d'un salon précédemment vidé réarme la possibilité. Pas de nombre maximum journalier. Initiatives **actives par défaut**, budgets financiers facultatifs ; `0` pour les deux budgets initiatives signifie non plafonné et n'empêche pas le salut. Aucune session LLM de veille en silence.
- **Mobile :** WebSocket propriétaire sous Tailscale Serve, entrée PCM16 découpée pendant l'enregistrement, STT OpenAI existant après fin de phrase, réponse texte et TTS progressifs, annulation, VAD de silence local et maintien du repli historique WAV. Aucune API conversationnelle Realtime supplémentaire. Copie autorisée de `duplex-client.js` dans l'aperçu privé de publication.
- **Contrôles :** `CostGuard` stocke dans le SQLite privé uniquement des hashes d'événements et réservations de dollars **estimées**, pas une facture certifiée. Rollback par flags (`JADE_INITIATIVES_ENABLED`, `JADE_SOCIAL_HYBRID_ENABLED`, `JADE_MEMORY_BATCH_ENABLED`, `JADE_SELECTIVE_CONTEXT_ENABLED`). Les limites USD se règlent par variables dédiées et n'excluent pas des dépassements d'estimation ; prévoir un plafond fournisseur si besoin de limite financière stricte.
- **Tests et preuves :** `test_jade_economy_memory.py`, `test_jade_economy_social.py`, `test_jade_mobile_duplex.py`, tests historiques, `tests/mobile_stream_client_test.js`, compilation Python et JavaScript, vérification des secrets via GitHub Actions. Une passe CI antérieure (PR #34, SHA `2f177387`) a réussi hors ligne ; **la validation finale doit porter sur le SHA d'intégration**, et aucune recette physique PC, Android ou Discord/Tailscale n'est déclarée ici.
- **Fichiers et design :** `context_selection.py`, `memory_batch.py`, `memory_service.py`, `personality_evolution.py`, `social_intelligence.py`, `initiatives.py`, `cost_guard.py`, `dialogue.py`, `discord_text.py`, `discord_voice.py`, `main.py`, `config.py`, `mobile_duplex.py`, `mobile_gateway.py`, scripts PWA, workflow CI et doc d'architecture. **Pas de secrets, de mémoire personnelle ni de modifications sur `main`.**

## 2026-11-21 — Souvenirs transversaux privés pour les comptes liés (develop)

- **Produit :** dans la PWA, le micro PC et les MP Discord, Jade retrouve les souvenirs condensés des autres portées d'un même profil ayant au moins deux identités authentifiées liées. Maximum huit souvenirs dans le contexte dont quatre d'autres portées ; la mémoire locale de salon reste prioritaire.
- **Garde-fou léger :** aucun souvenir d'une autre portée n'est chargé dans les salons publics Discord/vocaux ou Twitch. L'historique complet de niveau 1 reste par salon ; seuls les résumés de niveau 2 et les Core relationnelles stockées dans `memories` circulent en privé. L'autobiographie `jade_self_core` reste propriétaire.
- **Technique :** nouvelle lecture SQL `MemoryStore.recall_linked` appelée conditionnellement par `MemoryService.context_for`, sans migration SQLite, réécriture des enregistrements ni appels IA supplémentaires. Conservation 7j/365j/Core, code de liaison 5 minutes, autonomie Core, effacement et déliaison inchangés.
- **Fichiers et QA :** `memory_store.py`, `memory_service.py`, texte de la PWA, tests `test_jade_cross_channel_memory.py`, guides/état de develop et passation. Un test historique (`test_jade_explicit_memory_request.py`) attendait encore une activation manuelle en MP Discord et a été remis en phase avec la décision du 21/11. La CI Linux a ensuite réussi ; le passage Windows a identifié un verrou temporaire de SQLite dans le nouveau test d'expiration, corrigé par fermeture explicite via `contextlib.closing`. Vérifier la CI finale sur ce commit et conserver la recette PC/Discord/Android au propriétaire.

## 2026-11-21 — Mémoire automatique en MP Discord et clarification de la liaison mobile (develop)

- **Produit :** inscription mémoire automatique pour un compte Discord vérifié dès un tour traité en MP, comme en serveur et en vocal ; aucun pseudonyme ne vaut identification et Twitch reste sur activation explicite. L'opt-out durable Discord via `!jade-memoire oublier` et le retour volontaire via `!jade-memoire activer` restent prioritaires.
- **Mobile :** instructions en trois étapes distinguant précisément les commandes à exécuter sur Discord ou Twitch, la saisie de l'ID sur la PWA et la confirmation de retour sur le même compte. Le libellé précise que **seul le code à usage unique expire après cinq minutes**, tandis que la liaison confirmée reste sans limite de durée. Aucun changement du TTL, des règles de vérification des comptes ou de l'isolation par salon.
- **Sources :** `memory_service.py`, PWA `index.html`/`app.js`/`styles.css`, tests d'inscription Discord/MP et liaison HTTP, consignes de projet, `BRANCH_STATE.md`, guides utilisateur/technique et passation.
- **Contrôle :** régressions ajoutées pour MP Discord par défaut, effacement empêchant la réinscription en MP et en serveur, confirmation depuis un MP sans activation manuelle et isolation des historiques. Exécution Python locale, CI GitHub et recette PC/Android à vérifier ; ne pas les déclarer acquises avant leurs résultats.
- **Vigilance :** informer les correspondants Discord, notamment en MP, du stockage et de la conservation ; les règles de confidentialité et la désactivation explicite ne changent pas.

## 2026-11-20 — Politique de conservation Jade : 7j / 365j / Core sans purge (feat/memory-retention-7d-365d-24h-20261120)

- **Stockage :** migration SQLite v3→v4, niveau 1 `conversation_turns` purgé après 7 jours, souvenirs ordinaires `memories.kind=ordinary` expirant après 365 jours depuis `created_at`, même pour les anciennes lignes v3. Core Memories relationnelles et autobiographiques jamais purgées par la politique temporelle ; correction/effacement explicite préservé.
- **Reprise :** récupération de tous les tours datés des 24 dernières heures, pour la même identité et le même salon ; suppression des limites numériques 24 échanges / 48 messages sur les sessions réhydratées. Le modèle peut atteindre sa fenêtre de contexte et augmenter la consommation de tokens, mais Jade ne tronque plus arbitrairement en nombre de messages.
- **Exploitation :** nettoyage immédiat à l'ouverture de la base et périodique toutes les heures en mode réel, avec arrêt propre de la tâche asynchrone ; la démo hors ligne reste non persistante.
- **Qualité :** tests de purge 7 jours, expiration 365 jours, non-expiration Core, compatibilité de sauvegarde v4, récupération de plus de 100 tours, isolation, réhydratation dans le runtime ; résultats CI à valider au SHA de la PR.
- **Attention migration :** sauvegarder le fichier SQLite privé avant redémarrage ; cette purge supprime effectivement les anciens tours, sans garantie d'effacement physique des copies de sauvegarde.

## 2026-11-20 — DEV-011 révisée : souvenirs ordinaires sur demande, Core Memories autonomes (fix/dev-011-ordinary-only-autonomous-core-20261120)

- **Décision du propriétaire (postérieure à la PR #29) :** aucune personne, y compris Goldaj, ne peut imposer de Core Memory profonde. Le développement de la PR #29 permettant à Goldaj de créer directement `core_self`/`core_relationship` est **remplacé** par ce correctif ; les anciennes notes de la PR sont historiques, pas le comportement attendu.
- **Code :** nouveau `explicit_memory_intent.py` (français oral/écrit), retrait de `owner_core_intent.py` et de `MemoryStore.put_owner_core`, interception par `memory_service.py` sans appel LLM ni curation, écriture transactionnelle `MemoryStore.put_requested_ordinary` (`kind=ordinary`, TTL 90 jours, identité/salon et doublons vérifiés). Même une demande « Core Memories » est enregistrée **uniquement en ordinaire**, avec réponse explicite.
- **Autonomie :** seule la curation de Jade peut ensuite choisir des Core Memories indépendamment des instructions de l'utilisateur ; le traitement d'une demande explicite ne déclenche jamais cette curation. Les commandes privées de lecture/effacement Core existantes sont maintenues pour la protection des données, sans droit d'écriture forcée.
- **Vérifications :** tests ciblés de grammaire STT, refus des faux ordres, unicité, expiration, oubli, écriture SQL, cloisonnement, refus des secrets, runtime sans LLM et curation Core autonome ; résultats CI Linux/Windows consignés dans la passation. Aucune recette sur le PC réel.

## 2026-11-20 — DEV-011 Core Memories explicites par Goldaj (feat/dev-011-explicit-owner-core-memories-20261120)

- **Code :** `owner_core_intent.py` (demande naturelle explicite), `memory_service.py` (interception prioritaire, confirmation réelle), `memory_store.py` (transaction Core propriétaire, catégorisation, refus des comptes non liés, déduplication et effacement des souvenirs autobiographiques de comptes liés, y compris par commande propriétaire), ainsi que commandes privées `lister-core`/`supprimer-core` pour les Core relationnelles.
- **Comportement :** instruction texte ou voix de Goldaj authentifié ; écritures `core_self` et `core_relationship` pérennes sans attente du LLM ; réponses ne divulguant pas le contenu sur les salons publics. Refus des identités non reconnues, des textes vides ou trop longs et des secrets courants.
- **Vérifications :** tests unitaires de parsing, identité, liaison, oubli, suppression, redémarrage, isolation, doublons, SQL en échec et runtime sans appel LLM ; CI GitHub Actions Linux et Windows réussie (run `44816114240`), contrôle des secrets réussi (run `44816114280`). Pas de recette physique sur le PC/Discord propriétaire depuis cet environnement.
- **Risques :** l'interprétation des variantes non explicitement reconnues retombe sur le dialogue usuel ; ne pas confondre une réponse de langage avec une confirmation SQLite. La création d'une Core Memory par une instruction du propriétaire est volontaire, non une preuve indépendante des faits rapportés.

## 2026-11-20 — Mémoire persistante active et inscription Discord sans commande (branche feat/auto-memory-discord-20261120-v2)

- **Configuration / runtime :** conserver les nouveaux défauts `JADE_MEMORY_ENABLED=1` et `JADE_MEMORY_CURATOR_ENABLED=1` apportés sur `develop`, ajouter un chemin SQLite privé et absolu par défaut (`D:\\Jade\\private\\jade-memory.sqlite3` si D: existe sous Windows ; `~/.jade/jade-memory.sqlite3` ailleurs), ne pas créer de base pendant la démo hors ligne. Les variables privées explicitement à `0` continuent de primer.
- **Identités / conservation :** inscrire automatiquement un utilisateur identifié lors d’une interaction effectivement traitée sur un serveur Discord (texte ou voix). Garder une activation explicite pour les messages privés Discord et Twitch. Ne pas fusionner les profils ni lever les restrictions de salon.
- **Droit d’effacement :** `!jade-memoire oublier` supprime les données du compte et interdit les réinscriptions automatiques Discord, même après redémarrage ; réactivation volontaire via `!jade-memoire activer`. Nouvelle table additive `memory_auto_enrollment_blocks` conservant uniquement les identifiants requis au refus, sans changer le numéro de schéma SQLite v3.
- **Vérifications :** tests de régression ajoutés pour les défauts, l’enregistrement, l’isolation, les MP, Twitch, le refus persistant et la compatibilité v3. Exécution CI à contrôler ; aucune validation sur le PC réel revendiquée.
- **Risques / exploitation :** informer clairement les membres Discord avant leur participation, garder le fichier SQLite privé et réutiliser le chemin d’une éventuelle base existante ; la curation active ajoute potentiellement des appels API facturés.

## 2026-11-16 — Réorganisation du dépôt (branche chore/develop-repository-cleanup-20261116)

- Démonstrations : garder `demo/express/` ; retirer `demo/reelle/` et `demo/windows/` et leurs tests spécifiques. **Le renderer r20 auparavant dépendant de `demo/reelle/avatar.py` est déplacé vers `src/jade_runtime/avatar_renderer.py`**, avec son appel mis à jour. Les tests du protocole avatar et du TTS de production sont conservés sous des noms `test_jade_*`.
- Documentation : séparer `docs/handbook/`, `docs/architecture/`, `docs/ameliorations/`, `docs/operations/` et `docs/history/`; reclasser les fichiers historiques sans les jeter, réparer leurs liens et définir les lieux de passation inter-agents.
- Hygiène : supprimer du suivi Git les huit fichiers `.idea/`, les ignorer à l'avenir et retirer trois anciennes branches des triggers `jade-rebuild.yml`.
- Contrat documentaire : remplacer l'obligation de rééditer neuf guides à chaque changement par l'unique entrée changelog technique, avec vérification des liens locaux des guides actifs et actualisation ciblée des documents affectés.
- Transparence : expliciter que `goldaj/jade-vtuber` est déjà public et que les contrôles de provenance, droits et secrets ne sont pas automatiquement acquis.
- Modélisation : inspection des 221 fichiers Git de `jade-modeling/` : aucun SHA de blob strictement dupliqué ; aucun art source, checkpoint ni outil de rigging supprimé sans preuve d'inutilité.
- **Validation** : état des modifications constaté dans GitHub sur cette branche ; exécution complète des tests, du rendu Windows et contrôle des objets LFS matériels à confirmer via CI/poste local.

## Format des entrées futures

`YYYY-MM-DD — <mission> (<branche>, <PR/commit>)` : changement observable, références code, documentation impactée, contrôles réellement effectués, limitations et suivi. Ne pas recopier les mêmes lignes dans tous les manuels.


## 2026-11-16 — Discord PCM, liaison mémoire et PWA (PR #23, branche fix/discord-pcm-memory-mobile-20261116)

- **Code :** supprimer le verrou erroné entre `ffplay` (micro local) et streaming PCM Discord ; continuer à autoriser le mode phrases facultatif seulement pour Discord vocal autorisé.
- **Mémoire :** conserver les tours SQLite complets lors de `complete_link` et d'un `unlink` non ambigu, en regroupant `discord`/`discord_voice` et `microphone`/`mobile` ; codes à cible vérifiée valables 5 min, invalidation du code précédent, masquage dans les logs **et le contexte Discord** ; commande d'identification technique avant confirmation.
- **Mobile :** PWA Goldaj uniquement, `POST /api/link` avec la double authentification déjà existante, formulaire et copie de commande. Le SDK Live2D Web reste une dépendance du PC, aucun bundle propriétaire ajouté.
- **Tests / impacts :** régressions PCM all-channels, liaison/historique et API propriétaire, mises à jour du guide utilisateur, technique, état de branche et fiche de passation. Les résultats CI, les essais matériels, coûts et latence ne sont pas présumés. Aucun déploiement matériel effectué ; statut de fusion de la PR #23 à consulter sur GitHub.
- **Revue sécurité finale :** `oublier` via Discord/Twitch ne peut plus effacer le profil entier de Goldaj ; il ne supprime que les données de l'identité demanderesse. Commande `delier` conservant les données ; isolation des anciens historiques sous réserve d'identités non ambiguës ; masquage des codes temporaires y compris avant arbitrage IA. Tests spécifiques ajoutés.
- **Limites :** fallback WAV et ancien broadcast non refondus ; profils multi-comptes d'une même plateforme avec vieux tours non attribuables nécessitent une revue manuelle pour la déliaison ; Live2D mobile réel reste à installer/recetter.

- **Revue croisée complémentaire (branche de PR #23) :** lecture du dernier `develop`, maintien des nouvelles règles documentaires et tests de régression d'identités et de confidentialité. La suite complète et le scan de secrets doivent être vérifiés au SHA final de la PR ; recette réelle PC/Android/Discord toujours ouverte.

## 2026-11-18 — Contrôles backlog et simplification de la reprise des agents (`develop`)

- **Code de contrôle documentaire :** `scripts/check_docs.py` inclut désormais `docs/backlog/` dans le contrôle des liens Markdown locaux et impose la présence/non-vacuité de ses six documents canoniques (index, DoD et quatre vues) dans la CI existante. Aucune nouvelle CI ni obligation documentaire générale ajoutée.
- **Process :** un commit par lot cohérent quand possible (pas par fichier), limite souple de trois cartes simultanées, reprise prioritaire en tête de l'index, formulaire de recette court réutilisable dans une passation existante ; DoD Codex **OU** propriétaire inchangée.
- **Git :** audit distant de 23 branches de travail (14 pointes ancêtres, 8 divergentes, 1 à recontrôler), sans suppression, force push, changement de visibilité ou modification de `main`. Les contrôles matériels et réglages de protection restent explicitement à réaliser dans la prochaine session adaptée.
- **Fichiers :** `scripts/check_docs.py`, `docs/operations/CHANGELOG.md`, `docs/backlog/README.md`, `docs/backlog/02-RECETTE.md`, `docs/handbook/BRANCH_MAINTENANCE.md`, `AGENTS.md`, `docs/operations/AGENT_COORDINATION.md`, `README.md`.
- **Validation à observer après push :** workflows Windows/Ubuntu hors ligne et secret-scan sur le nouveau SHA. Les validations réelles PC/Android/Discord/Twitch/Cubism, l'administration des branches et la protection de `main` n'ont pas été réalisées depuis ce chat.

## 2026-11-18 — Confidentialité OBS et intégrité backlog (DEV-004, P0)

- **Correctif :** `src/jade_runtime/output.py` masque les sous-titres OBS des DM Discord et des sources privées pendant la lecture WAV, avec garde défensive équivalente dans le chemin PCM. Les sous-titres des sources publiques restent disponibles ; les réponses mobiles sont normalement servies par leur passerelle dédiée.
- **Tests :** `tests/test_jade_discord_dm_voice_privacy.py` observe le fichier de sous-titres pendant la lecture pour DM, microphone, HTTP, mobile, Discord public et Twitch public. Le test préexistant couvre la non-facturation TTS en l'absence de destination autorisée.
- **CI :** `scripts/check_docs.py` contrôle IDs uniques, statuts, priorités, dépendances manquantes/cycliques, rangs et compte des sections du backlog ; `tests/test_docs_backlog_contract.py` couvre la vérification du référentiel et une dépendance inconnue.
- **Produit :** DEV-004 créée en P0, non Done tant que tests CI et validation Codex/propriétaire ne sont pas documentés ; REC-005 reste ouverte pour la recette réelle OBS et du mixage audio. Total : 58 tâches opérationnelles.
- **Limites :** aucun essai réel sur Discord, OBS, le PC ou l'audio du propriétaire ; la refonte du routage reste hors périmètre. Vérifier les workflows au SHA final.

## 2026-11-19 — Cinq quick wins routage, voix et latence (DEV-003/005–008)

- **DEV-005** : `main.py` supprime le TTS pour les réponses écrites Discord, Twitch et HTTP, et `turn_logging.py` aligne les destinations ; voix console explicitement demandée et micro local préservés.
- **DEV-003** : chemin WAV `discord_voice` limité à la session Discord autorisée, jamais au lecteur local ; révocation annule la lecture. REC-005/007 physiques toujours ouvertes, aucune fuite matérielle alléguée.
- **DEV-006** : hotkey VTS exécuté par tâche asynchrone suivie, annulée au shutdown ; aucune attente avant la voix et aucun hotkey pour les écrits.
- **DEV-007** : synthèse Realtime bufferisée utilise le même pool WebSocket que le PCM progressif ; le retry sans création de réponse et le lock existants sont préservés.
- **DEV-008** : `jade.latency` mesure les jalons file, mémoire, LLM, diffusion, fin/échec de chaque canal sans texte ni identités ; coût réel, STT, premier son et p95 de production restent REC-010.
- **Contrôles** : régressions ajoutées/actualisées, CI Ubuntu/Windows et scan secrets à relever sur PR, aucun appel fournisseur payé, PC/Android/Discord/OBS/VTS non testés matériellement.
- **Livraison** : branche `feat/jade-quickwins-routing-voice-metrics-20261119` depuis `develop` `fba75d4`, sans modification de `main`.

- **Complément DEV-008 (revue Tech Lead)** : option `JADE_LATENCY_LOG=1` lue de la configuration privée, exposition stderr seulement si activée, et correction des modalités micro/Discord vocal dans les mesures. Documentation TECHNICAL et exemple d'environnement mis à jour.

- **Revue sécurité complémentaire DEV-003** : le vocal Discord (fallback WAV et PCM) ne doit plus écrire son texte sur le fichier de sous-titres OBS partagé, qui pourrait appartenir à une autre audience ; test d'observation pendant lecture WAV et absence de son local.

- **Réparation de la régression QA DEV-003** : test historique `test_one_player_failure_cancels_and_awaits_other` devenu caduc après suppression du double lecteur. Le remplaçant vérifie une panne de diffusion Discord sans lecture locale et borne explicitement la durée (ancien test bloqué jusqu'au timeout CI, identifié dans les logs Windows du run 44477086397).

- **QA du lot au SHA c79976c (PR #26)** : [CI offline Ubuntu/Windows SUCCESS](https://github.com/goldaj/jade-vtuber/actions/runs/44478307734), [scan de secrets SUCCESS](https://github.com/goldaj/jade-vtuber/actions/runs/44478307610), revue des critères DEV-003/005–008 consignée dans la passation. Statut **À valider**, validation formelle Codex ou propriétaire non reçue ; tests physiques REC-005/007/010 à effectuer.

## 2026-11-20 — Avatar r20 dans la PWA

- Charge le module de compatibilité PixiJS sous la politique de scripts existante et raccorde les ordres de rendu de Cubism Core 6 à l'adaptateur 0.4.0.
- 37 tests ciblés réussis. À fenêtre mobile émulée, le modèle r20 s'affiche et bouge au repos dans Chromium. Le test Android passe par REC-019.
- [Preuves et déploiement](handoffs/2026-11-20-codex-avatar-mobile-r20.md).

## 2026-11-20 — Chambre mobile, personnalité et reconnexion Discord

- La chambre printanière approuvée remplace l'ancien décor CSS. Le WebP conserve l'illustration validée, avec trois mouvements localisés et une pause hors écran ou en mode mouvement réduit. [Passation chambre](handoffs/2026-11-20-codex-chambre-mobile.md).
- Le prompt réserve « papa » aux moments exceptionnels de tendresse et évite sa répétition. L'accueil mobile dit « Je suis là. ».
- Jade retente une connexion après une coupure propre au vocal, avec annulation à l'arrêt ou en cas de perte de la connexion Discord principale. [Passation Discord](handoffs/2026-11-20-codex-reconnexion-vocale.md).

## 2026-11-20 — Plan rapproché de Jade dans la PWA

- Cadrage approuvé par le propriétaire. Le modèle Web r20 est affiché à 150 % de son échelle précédente et décalé de 16 % de la hauteur de la scène vers le bas. La composition montre surtout le visage et le buste, avec les extrémités du modèle temporaire hors cadre.
- [Passation et validation](handoffs/2026-11-20-codex-chambre-mobile.md#cadrage-du-modèle-r20).

## 2026-11-20 — Mouvements et cadrage de la chambre

- La position de l'avatar est décalée de 8 % de la largeur de la scène vers la droite pour dégager la tasse sous le plan rapproché.
- Le rideau se balance davantage et son ourlet dispose de plus de marge. Les ombres peintes près du chevet et les reflets sur le parquet bougent plus sensiblement. Les effets suivent la préférence de mouvement réduit.
- [Passation](handoffs/2026-11-20-codex-chambre-mobile.md#ajustements-après-essai-mobile).

## 2026-11-20 — Fiabilité de l'export et de la validation locale

- L'export de prévisualisation inclut le script et le décor WebP de la PWA. Le binaire approuvé est vérifié avant la création de l'export.
- La simulation microphone emploie une durée PCM adaptée au filtre audio. [Passation](handoffs/2026-11-20-codex-audit-ops.md).

## 2026-11-20 — Dépenses OpenAI et voix mobile progressive (`codex/backlog-prioritaire-20261120`)

- La PWA privée présente les coûts API du jour et du mois UTC par devise, via `billing.py` et la route authentifiée `/api/billing`. La clé administrateur est facultative et reste côté PC ; les valeurs périmées sont identifiées et les périodes échues masquées. Le solde prépayé et l'alerte associée restent indisponibles ; voir [configuration](reference/OPENAI-COSTS.md).
- Le mobile reçoit le texte puis l'audio PCM au fil de la synthèse, avec repli WAV selon le modèle ou le navigateur, sans deuxième synthèse après erreur. La fermeture de la page interrompt le travail ; le pitch démarre en parallèle du premier fragment PCM. Les endpoints existants restent compatibles.
- Risques et limites : aucune mesure de latence réelle ni recette Android/Discord ou connexion à l'API d'administration ; capture mobile et transcription restent tamponnées, et le dialogue n'est pas duplex. Aucune mise en service sur `develop`.
- Contrôles et reprise : voir [passation du lot](handoffs/2026-11-20-codex-couts-voix-mobile.md).

## 2026-11-20 — Retours Discord et préparation des tests PyCharm

- Discord : fin de parole à 500 ms avec seuil d'énergie relatif borné et mémoire temporaire du bruit, à régler après recette réelle ; participation spontanée 20 % en groupe pour voix et texte Discord, Twitch conservé à 30 %. La parole reçue pendant une réponse n'interrompt plus Jade et n'est pas transcrite pour rechercher un ordre d'arrêt.
- Résilience : reconnexion vocale à délai progressif plafonné à 30 s tant que le Gateway est actif, au lieu d'abandonner après six essais. Deux arrêts ont été signalés ; faute de logs historiques, la cause du crash complet reste indéterminée et une nouvelle recette est nécessaire (REC-023).
- Tests sur ce poste : profil Discord/mobile PyCharm avec configuration privée chargée localement et instance unique ; la production reste lancée hors PyCharm. Voir [guide](reference/PYCHARM-LOCAL.md).
- Vérifications et limites dans [la passation](handoffs/2026-11-20-codex-retours-discord.md).

- Ajustement de personnalité demandé : `prompt_chat.txt` autorise un humour plus cru et des insultes non édulcorées lorsque le contexte s'y prête, sans vulgarité systématique ; le profil privé actif ne surcharge pas ce prompt. Une visionneuse de diagnostics permet aussi le lancement autonome demandé pour cette session.
- L'export de prévisualisation emporte le lanceur et ses configurations de test ; les tableaux documentaires conservent leurs informations sans être pris à tort pour des cartes du backlog.
