# Jade r21 dans la PWA

26 novembre 2026 · Codex Sol · base `53462f9` sur `develop` · volet mobile de [DEV-001](../../backlog/01-DEVELOPPEMENT.md).

## Fonctionnement

- Le catalogue choisit la livraison r21 v45.1 comme défaut. Le serveur lit les assets matérialisés par Git LFS dans la livraison et expose un manifeste Web avec Blink, WinkL, WinkR et Surprised. Le réglage privé `JADE_MOBILE_SECOND_MODEL_DIR` permet de fournir un autre paquet r21 portable.
- Jade r21 se tient debout dans les deux décors. Jade classique reste assise dans la chambre et debout dans la cuisine. Le choix dans Profil vaut pour le salon ouvert. Une relance reprend le r21 et un échec de chargement déclenche le repli classique.
- Une bascule arrête le micro, ferme le duplex ou annule la requête HTTP, arrête et vide l’audio, puis décharge le modèle et ses textures. Les ressources du nouveau modèle commencent à être chargées après libération confirmée. La conversation reprend sur une action manuelle.
- Les sept intentions déclenchent chacune deux vraies motions A/B. `Neutral` dispose de deux gestes et `Idle` boucle entre les réactions. L’enveloppe audio pilote l’ouverture de la bouche. Les petites expressions Web reprennent les paupières du r21 et la surprise ne commande ni les oreilles ni l’ouverture de bouche.
- Le r21 reprend le cadrage du classique en alignant approximativement l’emplacement et la taille du visage dans les deux pièces. Le corps debout suit ce cadrage et peut sortir partiellement du cadre. Dans une chambre très large, le r21 reprend la caméra des mini-scènes pour garder le visage visible.

## Recette

Le banc local utilise Edge/Chromium, WebGL et le SDK installé. Il passe par le gateway Jade et le formulaire de connexion de recette avec la livraison v45.1 réelle. Le SDK a déclenché les quatorze gestes A/B et repris l’Idle bouclé après le dernier geste. La bouche rendue est restée fermée sans audio et a suivi l’enveloppe pendant une lecture PCM de test. Une bascule pendant cette lecture a arrêté les sources Web Audio et annulé le flux serveur sans nouveau tampon audio après le changement. Le comptage a confirmé un canevas et le cycle de libération `1 → 0 → 1` dans les deux sens. Une erreur HTTP 503 injectée sur le troisième atlas a déclenché le nettoyage du r21 partiellement chargé et le repli r20. Les réponses étaient synthétiques.

La première revue Codex du 26 novembre avait cadré les pieds sur le tapis de la chambre et le parquet de la cuisine. Le propriétaire a ensuite demandé de reprendre la taille et l’emplacement de la tête du r20. Avec les deux vrais modèles dans Chromium à 393 × 873 et 873 × 393, le centre et l’écartement des yeux au neutre coïncident dans les vues Accueil et Chat des deux pièces. L’Accueil chambre très large reprend le repère du Chat, car le zoom Accueil du classique y place les yeux hors cadre. Les suites ciblées du cycle du modèle, du cadrage et du contrat de chambre passent.

- Les 13 suites Node couvrent le chargement exclusif, les gestes, les anciens rappels, l’arrêt des sources audio, du micro et du duplex, ainsi que les événements tardifs. 45 tests Python mobiles sont passés et un scénario de lien symbolique a été ignoré sur Windows. Le contrat du gateway est exercé avec de petits paquets et une requête JSON interrompue en cours de génération.

### Recette sur l’appareil

- Aucun appareil autorisé n’était visible via ADB. La recette physique et les mesures de performance restent à faire.
- Valider sur le Redmi le démarrage r21, les deux décors et les bascules depuis Profil pendant une capture ou une réponse parlée. Les deux directions doivent couper la conversation, libérer le modèle sortant et rendre le micro disponible pour une reprise manuelle.
- Contrôler le cadrage en portrait, en paysage et dans les mini-scènes. Mesurer le premier chargement et la fluidité des gestes pendant la parole sur l’appareil. Les trois atlas de 4096² du r21 représentent 192 Mio décodés en RGBA8 avant mipmaps.
- Le raccordement Windows et la recette intégrée [ART-012](../../backlog/04-PRODUCTION-2D.md) restent ouverts.

## Échanges accessibles

- **Utilisateur, extrait** « on voudra dans un premier temps Jade debout dans la chambre (et dans la cuisine) pour faire simple. »
- **Assistant, résumé** Proposition initiale d’un r20 par défaut pendant une première phase, avec maintien du micro et de l’audio lors des bascules.
- **Utilisateur, extrait** « on veut le nouveau modele par défaut, et utiliser un menu dans Profil pour garder l'ancien modele actuel (celui assis) pour pouvoir switcher quand on veut de l'un à l'autre. »
- **Assistant, résumé** Le r21 devient le défaut dès la première livraison. Le r20 reste sélectionnable dans Profil. La conservation de l’audio est encore proposée à ce stade.
- **Utilisateur, extrait** « Ca coupe tout, point barre. » Puis « On ne chargera jamais les deux modeles en même temps ».
- **Assistant, résumé** La consigne devient une coupure immédiate de la conversation et une libération complète du modèle sortant avant le chargement suivant.
- **Utilisateur, extrait** « tu peux réaliser les développements de cette tâche dans develop ».
- **Utilisateur, extrait** « tu remets la tête du nouveau modele environ au même endroit que l'ancien, a peu pres à la meme taille, et le reste va suivre. On est dans de l'à peu près ici ».

Extraits et synthèses du chat actif du 26 novembre, avec heures individuelles indisponibles. Les messages intermédiaires et les données privées sont exclus.
