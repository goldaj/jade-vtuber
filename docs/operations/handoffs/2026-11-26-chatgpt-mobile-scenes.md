# PWA : mini-scènes et double appui — 26 novembre 2026

- **Demande :** changement direct du propriétaire, réalisé sur une branche issue de `develop`, base `e0ef2b7fdd2665dd2fad0969edb65df4c002bbc8`. Intégration directe sur `develop` demandée ; aucune modification de `main`.
- **Réalisation :** agent principal pour le cadrage et la documentation ; sous-agent dédié aux gestes et tests comportementaux ; préparation de la suite hors ligne séparée ; revue PO/QA indépendante avec le modèle réel.
- **Périmètre :** interface PWA, trois fichiers produit `app.js`, `avatar.js`, `jade-theme.css`. Aucun changement d’asset, de microphone, de fournisseur, de mémoire ni de connecteur.

## Critères et décisions

| Critère demandé | Réalisation et preuve |
| --- | --- |
| Choisir le décor uniquement sur l’Accueil | Le sélecteur est retiré de l’affichage et du parcours clavier dans Chat, Rappels et Profil, ainsi qu’en plein écran. La pièce choisie demeure commune aux onglets. |
| Voir le sommet de tête et le visage dans les mini-scènes | Chambre : caméra appliquée au repère commun corps/tête, avec marge haute de 12 px et plafond de taille sur les scènes courtes. Cuisine et repli debout : modèle entier ancré sous le bord supérieur. Le bas peut être recadré. |
| Double geste pour entrer/sortir du plein écran | Même fonction pour bouton, souris, tactile et stylet ; conservation de l’onglet, de la pièce, de l’instance Live2D et de l’unique microphone. Plein écran natif et repli CSS couverts. |
| Éviter les bascules involontaires | Boutons/liens/champs exclus, y compris leurs enfants ; déplacements, appuis longs/éloignés, annulations, défilement et contacts multiples rejetés. Le `dblclick` synthétique après le tactile est ignoré. |
| Préserver le raccord assis et le décor animé | Alignement propriétaire de la tête et du corps inchangé. Les deux couches de fond suivent la même transformation, couvrant la largeur même si le personnage est réduit. |

La caméra assise utilise le plan existant 941 × 1672. Mesures sur le **vrai moc3 r20** avec Cubism Core 6.0.1 : sur 486 combinaisons d’angles, de souffle et de mèche, sommet de tête au-dessus de `0,211072 × hauteur du plan`, menton sous `0,433575 × hauteur du plan`. L’ancrage à 21 % et une réserve de 24 % du plan pour le visage gardent de la marge sans changer l’assemblage du personnage.

## Vérifications effectuées

- `mobile_scene_gestures_test.js` exécute l’application avec un DOM simulé : quatre onglets, souris/tactile, plein écran natif/refusé/absent, retour navigateur, transitions concurrentes, contrôles et gestes négatifs, placement et état du microphone.
- `mobile_scene_framing_test.js` exécute `avatar.js` avec des dimensions PIXI liées à l’échelle : six ratios, haut visible, proportions, redimensionnements répétés sans dérive, restauration Accueil/plein écran et repère assis conservé. Les deux tests sont raccordés aux workflows Linux/Windows.
- **56 rendus Chromium avec WebGL et le modèle réel**, servis par un banc local sans runtime Jade ni authentification : formats 320×568, 360×640, 393×873, 412×915, 800×393, 873×393 et 1280×800, deux décors et quatre onglets. Les 42 mini-scènes passent le contrôle des bornes réelles de la tête et du visage, avec au moins 12,70 px de marge haute et 22,44 px sous le menton. Le contrôle paysage a révélé puis permis de corriger un raccord du fond ; à 800×393, la tête conserve environ 16 px de marge haute et le menton environ 23 px de marge basse.
- **32 parcours navigateur réussis** : souris et double appui tactile, API native et repli CSS, deux pièces, quatre onglets. Retour au menu et à ses dimensions, même modèle et même micro ; aucune erreur JavaScript ni requête `/api/`.
- **Passe complète hors ligne réussie** : 737 tests Python en 30,503 s, sans test ignoré dans la suite principale ; les 10 scripts de tests JavaScript et les contrôles de syntaxe passent. Preflight sur 262 fichiers, compilation Python et contrat documentaire réussis. L’export autonome exécute aussi sa propre suite avec succès.

## Remise en cohérence de la CI existante

Le test UI attendait un ancien appel inline de placement du micro et le mock du test de streaming ne disposait pas de `classList.contains`. Ils sont mis à jour pour exercer le comportement réel. Les cellules « Dépend de » de DEV-039/040/041 contenaient de la prose interprétée comme des identifiants ; les IDs sont maintenant séparés, les nuances conservées dans les critères. Les cartes ne changent ni de statut ni de périmètre.

La suite complète a aussi détecté l’absence préexistante de `portrait-bedroom-motion.js` dans l’export autonome. `tools/jade_publication_export.py` ajoute uniquement ce script à sa liste explicite, et `test_jade_publication_export.py` contrôle désormais la présence de toutes les routes `WEB_FILES` dans l’aperçu. Aucun SDK, asset LFS supplémentaire ou fichier privé n’est ajouté à l’export.

## Validation distincte et limites

**Revue PO/QA indépendante positive le 26/11/2026** : les trois demandes sont satisfaites sur les 56 rendus et les 32 parcours exécutés ; aucun défaut bloquant restant observé. Cette passe est distincte de l’implémentation et repose sur la géométrie du vrai modèle et les captures. Les essais navigateur sont réalisés en émulation mobile et sur écran large ; **aucun essai sur le Redmi physique, microphone réel ou session facturée n’est déclaré**. Les bibliothèques de rendu utilisées par le banc de test restent hors Git. Le profil de scène concerne le r20 actuellement servi par la PWA ; une future intégration du r21 devra vérifier son cadrage.

Sources fonctionnelles mises à jour : [état de develop](../../handbook/BRANCH_STATE.md#mini-scènes-et-double-appui-26112026), [guide technique](../../handbook/TECHNICAL.md#6-connecteurs-texte-http-et-pwa), [journal technique](../CHANGELOG.md).
