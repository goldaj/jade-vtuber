# Passation ChatGPT · Refonte visuelle PWA Jade · 22 novembre 2026

## Décision propriétaire
Utiliser le dernier visuel de référence approuvé : la chambre et le personnage Jade Live2D occupent une place centrale sur l'Accueil ; la DA est botanique sauge, vert profond, ivoire et jaune doux. Icône sélectionnée : deux fleurs blanches et centres jaunes sur un carré sauge à bord doré. Aucun déploiement sur main.

## Intégration
Sources : src/jade_runtime/mobile_web/index.html, jade-theme.css, app.js, manifest.webmanifest et icônes, avec les routes statiques dans mobile_gateway.py. On conserve room-spring.webp, room-motion.js, avatar.js, sw.js, le modèle r20 et les éléments DOM du gateway. La navigation entre vues est une opération CSS et non le démontage du canvas pour éviter les rechargements Live2D. Le tableau de bord ne fait qu'afficher la vraie liste des rappels retournée par l'API propriétaire.

## Contrôle
CI et tests d'intégrité après push. Vérifier sur téléphone : rendu du modèle dans la chambre à l'accueil, passage Chat/Accueil, visibilité des panneaux sur petit écran, permission Push, ouverture du rappel depuis notification, installation PWA/actualisation d'icône. La conformité de pixel à pixel du visuel conceptuel n'est pas prouvée sans test physique ; les calques graphiques du décor original sont volontairement conservés.

## Limites
L'icône source est extraite de l'image approuvée, adaptée aux tailles Android et soumise au recadrage des lanceurs. L'onglet Activités contient des raccourcis, pas un nouveau service de mesure du bien-être. Les données et secrets privés ne changent pas.
