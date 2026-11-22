# Passation ChatGPT · Splash mobile Jade · 22/11/2026

## Demande et choix
Le propriétaire a déposé sur develop l'image finale splash-jade.png pour remplacer le ressenti de démarrage « grosse icône floue ». Il demande aussi si une icône 4K résoudrait directement le splash Android.

## Intégration sur develop
- `mobile_web/index.html` affiche l'image validée avant l'accueil, preload élevé, sans jeton.
- `mobile_web/jade-theme.css` utilise toute la fenêtre et préserve le ratio, avec transition courte.
- `mobile_web/splash.js` enlève la couche au chargement complet, avec un fallback quand transitionend n'est pas émis.
- `mobile_gateway.py` autorise les deux fichiers statiques, maintient les protections Tailscale et les permissions.
- `manifest.webmanifest` déclare l'icône SVG adaptable comme alternative aux icônes 192/512 PNG.
- `tools/jade_publication_export.py` inclut ces fichiers dans la preview privée, vérifie signature/dimensions du PNG.
- `tests/test_jade_botanical_ui.py` étend le contrat de tests de l'interface.

## Limite à maintenir explicitement
Android/Chrome présente d'abord un splash système basé sur l'icône du manifeste, puis le WebView/PWA peut afficher l'image. Une PWA ne peut pas forcer Android à utiliser l'image verticale comme son splash natif. Les PNG 192/512 présents proviennent d'un original de 96 pixels : leur rééchantillonnage 4K serait cosmétique, pas une amélioration native. Le SVG est proposé à titre de ressource vectorielle pour les navigateurs compatibles, sans garantir que Chrome utilisera cette entrée. Une source haute résolution fidèle à l'icône choisie est nécessaire pour un vrai PNG Android net si le problème persiste.

## Contrôles
CI à vérifier, ainsi que le fonctionnement physique du Redmi Note 13, le deep link des rappels et les étapes de mise à jour/réinstallation PWA. Pas de changement sur main.
