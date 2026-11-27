# Mission : Salon portrait statique

- Agent : ChatGPT. Demande directe du propriétaire, sans changement de statut de backlog.
- Branche : develop ; base `1a0a1ffece2d70872bf5c076615657cbb0971c73`. Intégration uniquement par avance rapide avec vérification de la tête distante.
- Périmètre : troisième décor Salon, choisi par le propriétaire le 27/11, AVIF portrait 941 × 1672 (232741 octets). Cuisine et chambre conservées. Pas d'animation de décor au salon ; le pouf vert est peint dans l'image, le modèle reste debout.
- Chemins : `mobile_web/room-living-portrait.avif`, `salon.html`, `room-motion.js`, `preferences.js`, `jade-theme.css`, `avatar.js`, `mobile_gateway.py`, tests et documentation.
- Vérification observée : décodage AVIF local, dimensions et identité du SHA Git du blob transféré. Tests de sélection et régressions étendus ; CI et validation physique restent à confirmer.
- À recetter : choix Chambre/Cuisine/Salon, Accueil et plein écran, mini-scènes, relance avec le salon sélectionné et changement rapide de décor sur Redmi. Aucun changement de main.
