# DEV-010 — Décor printanier mobile vivant (revue de conception)

**Date :** 22 novembre 2026 · **Branche de travail :** `feature/dev-010-living-room-20261122` · **Portée :** PWA privée, sans modification de l'avatar Live2D ni des API.

## Comité de revue, personas simulés

Les cinq personas suivants sont des **grilles d'expertise simulées**, pas des intervenants humains ayant audité le projet de manière indépendante.

1. **Mina L., directrice technique 2D / compositing (12 ans, jeux 2D et animation de décors).** Mandat : séparer tissu mobile et menuiserie fixe, traiter le fond dévoilé, maintenir la palette et éviter les pixels de fenêtre déplacés. Critère bloquant : aucun `drawImage` d'un rectangle contenant des montants fixes.
2. **Thomas R., ingénieur senior rendu web mobile (10 ans, Canvas/CSS/GPU Android).** Mandat : coût batterie, mémoire décodée, repaint, navigateur mobile, recadrage 4:3 et absence de dépendances serveur. Critère bloquant : animations hors écran ou en arrière-plan actives ; ressources non autorisées par le serveur.
3. **Sora K., motion designer d'environnements anime (9 ans, animation procédurale).** Mandat : rendre perceptibles trois familles de mouvements, une seule météo cohérente (vent commun pour tissu et feuillage), fumée autonome, variations de période pour éviter l'effet mécanique. Critère bloquant : amplitude augmentée par simple déplacement de la photo entière.
4. **Camille B., QA automatisation et accessibilité (11 ans, applications web et PWA).** Mandat : repli si asset indisponible, mouvement réduit, changement d'onglet, création/destruction des rafraîchissements, tests de géométrie, de budget et absence de régression. Critère bloquant : constater une validation Android physique sans l'avoir exécutée.
5. **Idriss M., ingénieur sécurité et exploitation (8 ans, services privés).** Mandat : aucun CDN, aucun nouvel endpoint de données, assets servis par allowlist existante, état Git reproductible, tests avant intégration. Critère bloquant : accès réseau tiers ou secrets dans les traces.

## Décisions

- **Dessin.** Pré-calculer hors du navigateur un décor sans tissu et le calque du tissu translucide, à partir de `room-spring.webp`. Les ombres nouvelles sont des silhouettes SVG à flou doux, indépendantes des pixels peints du mur. Les montants et le reste de l'illustration sont sur le plan immobile. Garder le fond d'origine comme repli si un calque manque. La première extraction par inpainting et morceaux de mur a été rejetée lors de la revue visuelle pour bavures et artéfacts chromatiques ; les fichiers provisoires ont été supprimés. Les masques et paramètres sont versionnés dans `scripts/build_room_layers.py`.
- **Animation.** Un vent synthétique quasi périodique (somme de trois sinusoïdes) module rideau et ombres ; mouvement du rideau autour d'une charnière haute (pas de translation d'un rectangle de menuiserie). Fumée CSS en plusieurs volutes indépendantes, deux à trois fois plus hautes qu'avant ; reflets légers.
- **Budget d'animation.** Rythme de calcul plafonné à **30 mises à jour/s**, avec `requestAnimationFrame` interrompu quand le panneau est hors champ, quand la page est masquée et si `prefers-reduced-motion` est activé ; exclusivement `transform` et `opacity` sur les calques mobiles. 30 calculs/s au lieu du maximum habituel de 60 : **-50 % de mises à jour JS théoriques** lorsque l'écran est à 60 Hz. Ce n'est pas une mesure du temps GPU.
- **Bornes géométriques.** Rideau pivotant à environ ±7 degrés avec cisaillement ±4 degrés, translation horizontale relative d'environ ±3 % du tissu ; ombres glissant jusqu'à ±9 % et tournant ±3 degrés. Valeurs à ajuster après inspection réelle. Pas de déplacement du fond.
- **Réseau / mémoire.** Original : **213 846 octets**. Deux WebP supplémentaires : **247 534 + 49 110 = 296 644 octets** en plus de l'original toujours disponible en repli, soit **510 490 octets** pour les trois ressources si elles sont toutes transférées ; au plus environ 5,2 Mo supplémentaires de textures RGBA décodées (décor 1448×1086 et textile 262×296), avant surcoûts navigateur. La base originale sert de fallback et n'est pas remplacée. Aucun appel externe ou coût LLM.
- **Accessibilité.** Mouvement réduit : illustration d'origine immobile et pas de fumée ; repli : image originale si défaillance d'un asset, sans animation partielle incohérente.
- **Sécurité et livraison.** Feature branch, tests de génération et tests JS sans appels payants, CI d'abord, `develop` ensuite. Les assets construits restent éditables via le script, sans générateur à l'exécution sur Android.

## Recette et risques résiduels

1. Vérifier dimensions, alpha, fichiers générés et tolérance des pixels hors des zones explicitement modifiées. Inspecter visuellement l'absence de halos autour du rideau et des ombres ; une reconstruction géométrique du morceau masqué de la fenêtre reste une approximation artistique à affiner lors d'une éventuelle reprise dédiée.
2. Tester le cycle de vie `visibilitychange`, `IntersectionObserver`, `prefers-reduced-motion`, l'échec de chargement et les bornes du mouvement en JavaScript.
3. Tester syntaxe JS, tests Python de fabrication, tests existants mobiles et CI Linux/Windows. Pas de modification du transport audio, de l'identité ni des souvenirs.
4. Sur mobile Android réel, l'observation visuelle du rendu, des FPS et de la batterie reste une **recette utilisateur à effectuer** avant de marquer DEV-010 `Done` ; le ticket peut être `À valider` après le push.

**Risques résiduels :** les pixels réellement cachés par le rideau n'existent pas dans la source. La géométrie fixe est préservée et les aplats sont reconstruits avec des pixels voisins, mais le fond découvert peut encore présenter des répétitions de branches ou des raccords visibles lors des rafales. Une retouche artistique manuelle des deux masters reste préférable à une nouvelle extrapolation automatique. **Ce point n'est pas déclaré parfaitement résolu par les tests unitaires.** Les chiffres de coût sont des estimations/limites, pas des benchmarks matériels.
