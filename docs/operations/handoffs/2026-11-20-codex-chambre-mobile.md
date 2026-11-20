# La chambre de Jade dans la PWA — 20 novembre 2026

Le propriétaire demande un décor de chambre lo-fi illustré, avec des animations locales discrètes. Le décor habille le plan derrière Jade dans la PWA. La conversation, les commandes et le rendu de l'avatar restent des composants existants.

## Direction illustrée

Chambre de nuit pluvieuse, bois chaud, murs lilas assourdis et lumière ambrée. Un lit un peu défait et une breloque étoilée évoquent une Jade chaleureuse et espiègle. Deux petits livres de poche sans inscription sont un clin d'œil à la lecture. Le milieu de l'image est dégagé pour la silhouette r20. L'illustration fixe a été générée avec le moteur intégré de génération d'images.

## Validations du propriétaire

1. Valider le décor fixe présenté dans le chat. Sur le poste, la version de travail et le prompt sont sur D: sous le dossier temporaire jade-chambre-lofi-20261120.
2. Après accord, montrer une boucle de revue sur l'illustration validée. Essayer la pluie dans les carreaux, la vapeur au-dessus de la tasse et de légers reflets près de la lampe. Conserver le cadrage de la chambre, et tenir compte des recadrages téléphone et bureau.
3. Après accord sur ces mouvements, préparer l'intégration sur une branche de travail et tester l'aperçu au format mobile avec r20. Le push sur develop est conditionné à la validation finale explicite du propriétaire.

## Version livrée

La deuxième image, validée par le propriétaire, montre une chambre printanière ensoleillée dans le style du maître graphique r21. Les deux livres et la breloque étoilée sont conservés. Le WebP de 214 Ko est servi par la même liste de ressources locales que le reste de la PWA. Le rideau, la vapeur et les reflets reprennent les mouvements de l'aperçu. Les animations s'arrêtent en arrière-plan, hors de la zone visible ou si le système demande de réduire les mouvements. L'avatar Live2D utilise son propre canvas.

Le propriétaire a demandé le déploiement direct sur develop et sur son instance, en acceptant de passer l'étape de revue de l'aperçu à distance. [Décision](../../history/conversations/2026-11-20-reprise-develop.md#déploiement-de-la-chambre-printanière).
