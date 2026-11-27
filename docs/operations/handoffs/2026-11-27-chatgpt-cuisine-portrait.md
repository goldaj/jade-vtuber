# Mission : Cuisine portrait statique

- Agent : ChatGPT. Demande directe du propriétaire, aucun changement de statut de backlog.
- Branche : develop ; base `2783a9201bfc6a657b8375b93b53c936293c5899`. Préparation depuis la tête distante, intégration fast-forward uniquement avec vérification de la tête.
- Périmètre : remplacer la cuisine par l'image choisie le 27/11, AVIF portrait 941 × 1672 (146261 octets), sans calque animé ni repli vers l'ancien décor. La chambre et ses animations restent intactes. Jade classique reste debout en cuisine ; le r21 reprend le cadrage de la chambre.
- Chemins : `mobile_web/room-kitchen-portrait.avif`, `salon.html`, `styles.css`, `jade-theme.css`, `room-motion.js`, `avatar.js`, `app.js`, `mobile_gateway.py`, tests et documentation.
- Vérification observée : décodage AVIF local, dimensions, SHA Git identique à l'objet binaire transféré. Tests de sélection et contrat adaptés ; tests complets et validation Android non exécutés dans cette session.
- À recetter : affichage sur Redmi, proportions et placement du modèle en Accueil/plein écran, mini-scènes, bascule et choix restauré, non-régression de la chambre. Ne pas conclure à une validation matérielle sur la seule CI.
- Historique Git conservé, ancien décor supprimé de l'arborescence active.
