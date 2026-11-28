# Chargement du r21 dans la PWA

Le propriétaire constate que seul le r20 s’affiche sur le téléphone. Sur `develop@d3bb08f`, le paquet embarqué contient 33 ressources valides. Le catalogue, le manifeste, le MOC et les trois textures répondent en HTTP 200 sur le service privé. Les six dérivés retirés lors du nettoyage sont absents des références du manifeste actif.

Une ouverture de la PWA réelle depuis Edge affiche le r21. Elle rencontre toutefois neuf erreurs HTTP 502 sur les fichiers de mouvement. Le préchargement simultané des 18 gestes peut saturer le gateway, qui accepte dix connexions. Une connexion lente laisse ces requêtes ouvertes plus longtemps. La cause exacte du basculement sur le téléphone reste à confirmer.

Le correctif sérialise les requêtes de préchargement et les arrête au changement de modèle. Le chargement du catalogue et du manifeste r21 peut reprendre après une erreur transitoire, avec une seconde tentative bornée. Les refus définitifs conservent le diagnostic de chargement. Les tests couvrent l’arrêt du préchargement sur un modèle libéré, une réponse HTTP 502 suivie d’un succès et la persistance du choix visuel.

## Échanges accessibles

- **Propriétaire**, synthèse. Seul le r20 se charge dans l’application mobile. La connexion est faible et la cause du problème est inconnue.
- **Assistant**, synthèse. Vérifie le service privé et reproduit les échecs de chargement des mouvements. Échelonne les requêtes et ajoute une reprise sur erreur transitoire.

Les heures individuelles du chat sont indisponibles.
