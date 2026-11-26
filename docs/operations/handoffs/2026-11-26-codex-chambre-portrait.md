# Chambre portrait de la PWA

## Mission du 26 novembre 2026

Le propriétaire a signalé que l’ancienne chambre horizontale réapparaissait derrière Jade et a demandé que le décor actuel soit le seul utilisé. Ce compte rendu résume le message accessible. Son heure individuelle n’est pas consignée.

Branche `develop` à partir de `d59a4ce`. La [recette REC-040](../../backlog/02-RECETTE.md) reste à valider sur Android pour les parcours qui l’exigent.

## Diagnostic et correction

Le salon initialisait l’image horizontale. Le passage au portrait dépendait ensuite d’une notification de disponibilité Live2D et, pour le r20, du chargement du corps assis. Une erreur ou un chargement long prolongeait l’affichage de l’ancienne chambre.

Le portrait vertical est désormais déclaré dans `salon.html` et son image partage le cadrage du canvas d’animation dans `jade-theme.css`. Le chargement du corps assis et celui du r21 ont leur propre cycle. La cuisine charge son image avant le changement visible et conserve ses effets.

Les trois WebP historiques, le script qui générait leurs calques, ses dépendances, ses routes mobiles et ses tests dédiés sont retirés du dépôt courant. Le commit de départ conserve ces fichiers pour retrouver l’historique. Le générateur de prévisualisation privée vérifie désormais l’empreinte du portrait vertical.

## Validation

Les suites Node ciblées couvrent le décor portrait, les bascules de pièce et leurs courses de chargement, le cadrage et le cycle distinct des modèles. La passerelle mobile confirme les routes AVIF et le refus des anciens chemins.

Une passe Chromium au format mobile 393 × 873 a contrôlé le fond portrait pendant un chargement Live2D bloqué, avec les modèles r21 debout et r20 assis, puis le passage à la cuisine et le retour en chambre. Aucun chargement des trois anciens WebP ni erreur JavaScript n’a été observé. La recette a utilisé un navigateur mobile émulé.
