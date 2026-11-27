# Mission : Triste et Colère, non-régression des neuf intentions sur r21

## Autorisation et périmètre

- **Demande propriétaire du 27 novembre 2026 :** réaliser l'ensemble du lot des deux nouvelles intentions et la non-régression des sept autres sur **r21 exclusivement**. L'ancien r20 demeure dans l'application. La refonte faciale peut attendre si elle exige des API ou applications inaccessibles.
- **Arbitrage complémentaire pendant la réalisation :** supprimer les tests r20 ; ce modèle reste disponible mais ne fait plus l'objet de maintenance ni de recette. Cette décision s'applique aux suites et scripts de recette actuels, au-delà du seul lot des intentions.
- **Agents / rôles :** ChatGPT coordinateur ; sous-agents distincts pour contrat/voix, client mobile et motions. Contre-revues croisées du backend, du frontend, des exports et du banc WebGL après réalisation.
- **Base :** `develop`, `d7655cd4f4bf5c4e0ba1e177c625493ecfee1cd6`. Branche de livraison : `feat/intentions-triste-colere-r21-20261127`. Référence d'intégration : la PR portant cette fiche, à destination de `develop` uniquement.
- **Cartes :** développement DEV-053 transféré vers **REC-053 À valider** ; **ART-014 À valider** après livraison des quatre motions ; **ART-015 P0 reportée/Bloqué** jusqu'à disponibilité de l'atelier natif. DEV-001 conserve le raccordement Windows r21 déjà prévu. Pas de seconde carte DEV active pour la recette du code livré.
- **Modèle effectivement contrôlé :** paquet conservant le nom de dossier `Jade_r21_v45_1`, manifeste mobile pointant sur **r21 v49.1**. SHA-256 du MOC : `033196b5b31c5e12885fb2d70b371354e0f2c3e1965dbc92e55e57d0ece5b875`.

## Résultat fonctionnel

| Intention | Clé | Variantes r21 |
| --- | --- | --- |
| Neutre | `neutral` | A / B existantes |
| Enjouée | `playful` | A / B existantes |
| Enthousiaste | `excited` | A / B existantes |
| Curieuse | `curious` | A / B existantes |
| Tendre | `tender` | A / B existantes |
| Rassurante | `reassuring` | A / B existantes |
| Sérieuse | `serious` | A / B existantes |
| Triste | `sad` | A : regard abaissé puis inclinaison ; B : détour du regard puis retour discret |
| Colère | `angry` | A : appui ferme et accent vers l'avant ; B : rotation puis objection en deux accents |

### Contrat, voix et Live

`intent_engine.py` définit les neuf labels autorisés, leurs directions vocales et les règles de choix. Triste exprime la peine propre de Jade, avec cadence adoucie et fins descendantes ; Colère exprime son indignation, avec articulation plus ferme et accents contrôlés. Les consignes préservent son identité vocale et le volume normal. La tristesse d'un interlocuteur n'impose pas une tristesse à Jade : le réconfort reste rassurant.

Les voies Realtime TTS WAV et PCM utilisent la direction de la réponse sans la conserver au tour neutre suivant. `live_voice.py` complète les consignes des profils Live existants, sans changer la voix configurée. Les délégations gardent `Reply.intent` comme référence. En Live natif, l'heuristique locale analyse le début de la transcription : réconfort explicite prioritaire, puis humeur propre exprimée à la première personne, puis indices antérieurs. Un fragment réduit à « Oh ! » attend la phrase suivante. Aucune classification par nouvel appel fournisseur.

Cette détection native est volontairement conservatrice : une formulation indirecte non reconnue peut rester neutre. Les tests couvrent citations, négations, émotion attribuée à autrui, fragments et événements uniques. Les labels internes ne sont ni affichés ni prononcés. Les voies écrites ne déclenchent pas de synthèse supplémentaire.

### Visage, corps, oreilles et synchronisation

`mobile_web/avatar.js` ajoute uniquement les entrées Triste/Colère dans les tables de motions, de visage, de posture/regard et d'oreilles. Les paramètres et les quatorze motions des sept intentions précédentes sont conservés. `intent-visuals.json` fournit deux textes par intention et des expressions de repli supportées.

Le client garde le mécanisme existant : choix A/B une fois par réponse, visage préparé avant la parole, démarrage du geste à la lecture, aucune relance par fragment PCM, maintien après la dernière lecture puis fondu au repos. La bouche reste pilotée par l'audio et l'ouverture des yeux est multipliée après le clignement. Les callbacks d'une ancienne réponse ne peuvent pas relancer son geste après interruption ou désactivation.

Les nouvelles motions ne fixent ni `ParamMouthOpenY`, ni `ParamMouthForm`, ni l'ouverture des yeux. Elles partagent les mêmes paramètres physiques et n'imposent aucune nouvelle texture ou modification du MOC. Le paquet portable et le manifeste mobile référencent les quatre clips ; une expression `Angry.exp3.json` complète les expressions existantes sans figer la bouche ou les paupières.

### Production et provenance

Les sources `Edition/mobile-intentions/Jade_sad.psd2live-motions.json` et `Jade_angry.psd2live-motions.json` sont éditables et alimentent l'exporteur déterministe `jade-modeling/tools/export_r21_intent_motions.py`. Les exports Cubism `.motion3.json` et leurs empreintes sont inscrits dans `ASSET_MANIFEST.json`. Il s'agit de courbes et de poses sur le rig existant, pas d'une édition native des dessins du visage.

Avant retouche, étude des sources officielles : [animation et clés](https://docs.live2d.com/en/cubism-editor-tutorials/animator/), [expressions et multiplication des paupières](https://docs.live2d.com/en/cubism-editor-manual/facial-expression-system/), [mouvements et fondus](https://docs.live2d.com/en/cubism-sdk-manual/motion/). Application : courbes Bézier bornées, anticipation/retour distincts, paupières et articulation libres, fondus de sortie.

La recherche des capacités disponibles n'a trouvé aucun accès exploitable à Cubism Editor, PSD2Live ou Turboism. **ART-015 n'est pas réalisée** : les neuf visages manga redessinés et leur rig natif restent reportés selon la demande du propriétaire. Ce report n'empêche pas les nouvelles intentions sur les paramètres disponibles.

## Vérifications et preuves

La campagne n'initialise ni modèle ni rendu r20. Les tests spécifiques à ses assets, à son rendu et à son comportement sont supprimés. Les contrats de chargement, d'isolation, de cadrage, de visibilité et de cycle de vie restent exercés sur r21. Le profil `classic` éventuellement présent comme métadonnée imposée par le catalogue n'est jamais chargé par ces bancs. Les tests du **mode vocal classique** sont conservés : ce mode audio est indépendant de la version graphique.

| Niveau | Vérification observée | Limite |
| --- | --- | --- |
| Contrat/voix | Neuf labels, toutes coupures du tag, nettoyage des textes/historiques, directions WAV/PCM, neutralisation entre réponses, Live natif/délégué, priorité émotionnelle et interjections fragmentées | Fournisseurs simulés, aucune écoute de voix réelle |
| Client mobile | Dix-huit choix A/B, conservation des sept poses et jeux d'oreilles antérieurs, blink/lip-sync, pauses PCM, retour au neutre, transitions rapides, interruption, callbacks périmés, motion absente, intention inconnue, OFF et vues | Adaptateur Cubism inerte pour les tests de cycle de vie |
| Assets | Deux manifestes, dix-huit motions, courbes/métadonnées/bornes, paramètres libres, variantes distinctes et export reproductible | Validation structurelle, complétée par le Core réel |
| Core réel | **3 587 poses / 18 motions** échantillonnées à 60 Hz, paramètres dans les bornes du rig réel, sommets finis et retour exact au repos | Contrôle géométrique ; aucun jugement acoustique ou graphique natif |
| WebGL réel local | **18 variantes et 9 combinaisons de pièce/cadrage** ; un seul canvas r21, geste du bon groupe/index, articulation sur Web Audio synthétique, fermeture complète commandée avant la pose, retour au neutre | Chromium local 393 × 873 ; aucune observation physique du Redmi |
| Livraison | Après retrait r20 : 1 019 tests Python du dépôt (12 skips), 1 019 depuis l'export isolé (22 skips), aucun échec ; 26 commandes JavaScript distinctes des gates CI, compilation, préflight de 290 sources, export/réexport, contrat documentaire et non-modification des assets antérieurs | Résultats de CI et commit d'intégration dans la PR |

Preuves conservées dans [le dossier de recette](../evidence/2026-11-27-r21-intentions/README.md) : rapport Core avec empreintes et comparaison des quatorze clips antérieurs, rapport WebGL, planches de captures et commandes reproductibles. Les captures montrent le modèle réellement rendu avec ses textures ; elles ne représentent pas la refonte ART-015.

### Contre-revues distinctes

- Relecture backend par l'agent frontend : détection d'une sensibilité au découpage de transcription, corrigée et couverte par les tests natifs. L'émotion propre au début de phrase prime les indices non rassurants présents plus loin ; le préambule isolé ne verrouille plus neutre.
- Relecture frontend/assets par l'agent backend : valeurs antérieures préservées, fichiers réellement servis par la passerelle r21, limites du rig vérifiées, pas de nouveau blocage détecté.
- Relecture du banc WebGL par l'agent backend : contrôle du groupe de motion ajouté, retour Accueil avant changement de pièce, fermeture des yeux injectée avant la pose applicative, requêtes externes bloquées tracées. Audio et blink synthétiques explicitement distingués d'une conversation fournisseur.
- Relecture export par l'agent frontend : tests d'assets stricts dans le dépôt, skips seulement dans l'export marqué qui exclut entièrement l'atelier. Deux AVIF publics Cuisine/Salon absents de l'allowlist avant cette mission ont été ajoutés ; les tests d'export/smoke/réexport passent. Aucun modèle ou fichier d'atelier ajouté à l'export.

Ces vérifications autorisent la livraison du code ; elles ne valent pas observation des scénarios physiques manquants ni acceptation implicite par le propriétaire. Les cartes de recette restent **À valider**, sans faux `Done`.

### Recentrage des tests après la première CI

La première CI de la [PR #55](https://github.com/goldaj/jade-vtuber/pull/55) a reproduit un oracle de cadrage devenu obsolète avant cette mission : la Cuisine r21 était comparée à l'ancienne caméra du modèle classic. La suite est recentrée sur les repères du plan portrait r21 dans les trois pièces. Les suites de composition hybride et d'isolation de tête r20 sont retirées, ainsi que les scénarios de manifeste/idle/expressions propres à ce modèle. Les scripts VTS d'observation exclusivement r20 sont supprimés ; les sources artistiques et le code applicatif demeurent.

Le job Windows déclarait le bloc JavaScript réussi malgré cette assertion intermédiaire, puis poursuivait les tests Python. Le bloc emploie désormais Bash comme sur Linux, avec arrêt au premier échec. Les contrôles r21, les préférences et le cycle Live restent exécutés dans la CI. Ces corrections ne changent ni le rig, ni le rendu, ni les captures Core/WebGL du lot.

## Suite de recette

1. **REC-053 :** écouter Triste/Colère et les sept intentions sur les chemins vocaux réellement configurés, vérifier le timbre conservé et la distinction d'intonation. Réaliser la même écoute en Live natif/délégué et en Realtime WAV/PCM applicable. Le repli historique Speech API ne reçoit pas cette direction prosodique ; ne pas lui attribuer une parité acoustique non implémentée.
2. **REC-053 / ART-014 :** observer les dix-huit variantes sur Redmi réel, dans Chambre/Cuisine/Salon, Accueil, mini-scènes et plein écran, pendant parole, pauses, interruptions et changements rapides. Conserver les suspensions existantes micro PC/Twitch/OBS.
3. **DEV-001 :** terminer séparément le raccordement r21 au runtime Windows/VTube Studio prévu par cette carte. Le présent lot livre les ressources r21, sans prétendre avoir observé ces applications.
4. **ART-015 :** reprendre la refonte manga des neuf visages lorsque l'atelier natif devient accessible ; ne pas remplacer les dessins à partir d'une simple capture aplatie.

Sources de vérité actualisées : [état du code](../../handbook/BRANCH_STATE.md), [guide technique](../../handbook/TECHNICAL.md), [Live mobile](../../architecture/LIVE_MOBILE.md), [REC-053](../../backlog/02-RECETTE.md), [ART-014/015](../../backlog/04-PRODUCTION-2D.md) et [index du backlog](../../backlog/README.md).
