# Passation · Connexion mobile sur splash Jade · 22/11/2026

## Besoin et décision
Le propriétaire demande que le splash déjà validé reste visible **sans flou** derrière la saisie du jeton, avec une carte moins haute et légèrement abaissée pour voir davantage Jade.

## Livraison sur develop
- `mobile_web/index.html` : formulaire limité au pictogramme SVG existant, titre « Espace privé de Jade », étiquette « Jeton d'accès », champ secret et bouton « Entrer dans le salon ». Instructions et note de bas de carte retirées, attributs de sécurité du champ préservés.
- `mobile_web/jade-theme.css` : image `splash-jade.png` directement utilisée en arrière-plan du verrouillage, sans `backdrop-filter` et sans voile sombre. Carte réduite à 336 px max et légèrement décalée vers le bas ; règle pour petites hauteurs et clavier, rendu desktop `contain`.
- `tests/test_jade_botanical_ui.py` : contrat du contenu minimal et du fond net. Le début de chargement natif Android et la couche web de transition `splash.js` restent inchangés.
- `docs/handbook/BRANCH_STATE.md`, `docs/backlog/02-RECETTE.md`, `docs/operations/CHANGELOG.md` : état, recette REC-040 et traçabilité.

## Vérification et limites
- Contrôles statiques des fragments HTML/CSS effectués avant publication.
- À recetter sur Redmi : premier chargement, présence continue du fond lorsque le jeton est requis, clavier affiché, orientation, connexion valide, jeton expiré/401 et réouverture du formulaire sans disparition de l'image.
- Le token n'est pas persisté ; la sécurité de Tailscale et des endpoints est inchangée. Aucune connexion réelle au PC ni exécution de test Android depuis l'environnement GitHub.
- Le splash natif de Chrome/Android (icône de manifeste) ne peut pas être remplacé par cette image HTML.
- Une fois les contrôles CI et la recette physique réalisés, la carte REC-040 pourra être validée ; ne pas l'anticiper.
