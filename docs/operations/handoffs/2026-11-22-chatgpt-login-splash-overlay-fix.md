# Passation · Correctif popup de connexion masquée par le splash · 22/11/2026

## Constat / demande
Sur Redmi, le propriétaire a envoyé une capture où le splash Jade occupe tout l'écran et où le formulaire pourtant attendu en position très basse n'est pas visible. Cela bloque la recette `REC-040`, qui reste **À valider**.

## Diagnostic fondé sur develop
- `index.html` contient toujours `#auth-modal` et son formulaire compact.
- `styles.css` place ce dialogue à `z-index:40`; `jade-theme.css` place le splash HTML `.jade-launch-splash` à `z-index:99999`, ce qui le masque.
- `splash.js` attendait l'événement `window.load` avant d'effacer le splash, ce qui dépend du chargement d'autres ressources.
- La superposition et l'attente expliquent le symptôme sans toucher à l'image de Jade ni aux positions validées.

## Implémentation
- `mobile_web/jade-theme.css` : `#auth-modal` via `.auth-layer` désormais au-dessus du splash temporaire (`z-index:100000`), tout en conservant exactement le fond net et le décalage de la carte en portrait.
- `mobile_web/splash.js` : disparition immédiate du splash depuis le script `defer`, dès que le DOM est analysé. Aucun déclenchement conditionné au chargement complet des images / SDK.
- `tests/test_jade_botanical_ui.py` : contrat de non-régression sur ces deux conditions.
- `docs/backlog/02-RECETTE.md` et `docs/operations/CHANGELOG.md` : anomalie et suivi documentés.

## Contrôles et limites
Revue statique des fichiers modifiés ; tests d'intégration Android non exécutables depuis le seul connecteur GitHub. `REC-040` reste **À valider** sur téléphone (affichage de la carte dès le chargement, position basse sans dépassement, clavier, orientation, jeton valide/expiré). Pas de modification du backend, du jeton, des fonds de chambre/cuisine, ni de la branche main. Redémarrage du service Jade après mise à jour du code pour servir ces nouveaux assets.
