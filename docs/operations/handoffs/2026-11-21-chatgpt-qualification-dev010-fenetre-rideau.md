# DEV-010 — Qualification : fenêtre fixe et rideau en calques graphiques séparés

- **Date / autorité :** 21 novembre 2026, propriétaire de Jade.
- **Décision explicite :** le propriétaire a choisi « la seconde solution » : **reconstruction graphique propre**, pas correction ciblée du masque ; puis a demandé la modification directe de la backlog GitHub.
- **Carte :** DEV-010, P2, jalon B ; **À qualifier → À faire**.
- **Branche :** `develop` ; SHA observé avant modification : `48a674f6c33b903f0a933012d7b02a8bed597bbc`.
- **Périmètre :** **documentation et qualification fonctionnelle uniquement**, pas de changement de code, d'asset, de rendu ni de déploiement.

## Constat existant et hypothèse technique

Le propriétaire a constaté que le cadre de la fenêtre se déforme lorsque le rideau est animé sur l'application Android.

Dans `src/jade_runtime/mobile_web/index.html`, la scène `.room-art` comprend l'image fixe `room-spring.webp` (1448×1086) et un canvas `.room-curtain` (272×368). Dans `src/jade_runtime/mobile_web/room-motion.js`, `paint()` déforme horizontalement, par bandes de 5 pixels, une région source `x=906, y=46, w=272, h=368` via `context.drawImage()`. Cette région est extraite de l'image composite, sans masque sémantique du rideau, et peut donc embarquer des parties rigides de la fenêtre. Le CSS masque les bords, mais n'isole pas la matière.

**Hypothèse forte et localisée, pas preuve de reproduction :** la déformation de pixels rigides est liée à la déformation indistincte du patch extrait. Aucun enregistrement Android ou diagnostic en mouvement réel n'a été observé dans cette intervention ; la reproduction et la validation visuelle restent à réaliser.

## Solution retenue

1. **Composition artistique** : reconstruire le rideau en calque autonome avec transparence, nettoyant la zone laissée derrière lui ; placer les montants, le cadre et la poignée de fenêtre sur un calque fixe, avec ordre de superposition/occlusions correct.
2. **Sources éditables** : conserver un master en couches séparées adapté à la chaîne graphique ; livrer des ressources optimisées pour la PWA, avec géométrie/ancrages cohérents sur tous les rapports d'aspect.
3. **Animation** : animer uniquement le tissu (déformation/ondulation adaptée au rendu, CSS/canvas selon qualité), sans warper les pixels du fond, des montants ou du cadre. Supprimer/retirer de l'exécution le warping de la zone composite du code existant.
4. **Qualité** : pas de contours doublés, raccords ouverts, trous, déformation du bois ou apparition d'un rideau fantôme aux extrêmes de mouvement. Préserver les effets lumière/ombres/vapeur, les performances et l'avatar Live2D.
5. **Accessibilité et cycle de vie** : comportement correct avec `prefers-reduced-motion`, page cachée et scène hors champ ; cadrages portrait et paysage Android.

## Critères d'acceptation et vérification

- Cadre, montant, poignée et contours **visuellement invariants** tout au long de l'animation.
- Le tissu ondule indépendamment avec une amplitude naturelle et conserve ses ancrages.
- L'arrière-plan derrière le tissu est correctement reconstruit, sans marques d'ancien rideau ni artefacts de composition.
- Aucun défaut de raccord ou de superposition aux positions de repos et extrêmes.
- Responsive sans dérive des couches ; compatible Chrome Android, plusieurs tailles, mouvement réduit et page non visible.
- Tests ciblés de la composition et absence de régression du décor/Live2D, complétés par **recette sur Android réel**.
- Sources graphiques éditables, assets Web optimisés et lien UX-16 préservés.

**Ne pas étendre DEV-010 à la refonte complète UX-16** : cela reste un chantier artistique distinct.

## État d'exécution et validation

- Réalisation : qualification produit acceptée ; **développement non commencé**.
- Preuves : lecture du ticket et des fichiers `room-motion.js`, `styles.css`, `index.html`, de la passation du décor et de UX-16 ; aucun test ni preuve de rendu Android produits ici.
- Vérification documentaire : statut et critères explicités, priorité P2 et jalon B préservés, pas d'autres cartes modifiées.
- **Condition de reprise :** DEV-010 peut être planifiée en développement. À la livraison, requalifier toute cause technique contredite par un essai réel, sans faire passer la simple hypothèse de départ pour une certitude.
- **Condition Done :** implémentation + tests + recette visuelle + intégration `develop` + validation explicite du propriétaire ou Codex, conformément à la Definition of Done.
