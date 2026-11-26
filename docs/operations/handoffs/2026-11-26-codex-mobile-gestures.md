# Gestes tactiles de Jade r21

26 novembre 2026 · DEV-042 → REC-041 · base `1e875f5` sur `develop`.

Le propriétaire approuve le bornage et le bouton **Recentrer**, autorise le développement et réserve ces commandes à l’Accueil et au plein écran. Ces décisions sont consignées dans les [échanges du lot mobile](2026-11-26-codex-backlog-mobile.md#échanges-accessibles).

## Fonctionnement

- Pincer et écarter deux doigts sur Jade modifie la taille apparente du r21 autour du centre des doigts. Un appui maintenu saisit Jade avec un retour visuel et une vibration si le client l’autorise. Le relâchement conserve le placement obtenu.
- Une partie saisissable du personnage reste dans le champ. **Recentrer**, en bas à gauche à côté du micro, restaure la taille et la position de référence. Les réglages sont locaux au salon ouvert.
- Les gestes et le bouton appartiennent à l’Accueil et au plein écran. Chat, Rappels et Profil utilisent leur cadrage de base. Le modèle classique conserve ses interactions habituelles.

## Recette

Les cinq suites Node ciblées et les 19 tests du gateway mobile réussissent. Aucun téléphone autorisé n’était connecté en ADB. La recette physique est suivie dans [REC-041](../../backlog/02-RECETTE.md).

Le banc Chromium à 393 × 873 a chargé le vrai r21 avec le SDK WebGL. Les événements tactiles Chromium ont confirmé le pincement aller-retour, l’ancrage au milieu des doigts, l’appui hors de Jade, l’annulation, le déplacement borné, le recentrage exact, le double appui et le micro de recette. Le bouton est en bas à gauche dans les deux vues prévues. Les trois mini-scènes et le r20 n’affichent aucune commande de manipulation. Le passage en cuisine et en paysage a réussi. Le banc remplace la vibration physique par une sonde d’appel de l’API. Il suspend la peinture logicielle après le contrôle du chargement WebGL pour garder des événements tactiles réguliers.

Vérifier sur le Redmi, en chambre et en cuisine, le zoom dans les deux sens, le retour haptique, le déplacement maintenu jusqu’au relâchement, le bornage dans les quatre directions, le recentrage, la rotation, le plein écran au double appui, les mini-scènes, le micro et la bascule vers le r20.
