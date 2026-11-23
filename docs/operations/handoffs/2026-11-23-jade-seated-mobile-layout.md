# Mobile: Jade assise dans une chambre verticale (prototype à calibrer)

## Décision PO
Jade est représentée avec trois couches partageant **un même repère
941×1672** : chambre verticale, silhouette statique (robe/bras/jambes/pouf),
puis tête et cheveux issus du modèle Live2D r20 actuel.
Le modèle actuel n'anime pas les bras ni la jupe. L'unique raccord est donc
effectué autour du cou et des mèches latérales, et non au milieu de la robe.

La cuisine n'est pas modifiée par cette itération. Aucune règle propre au
Redmi Note 13 ou au nombre physique de pixels n'est ajoutée.

## Implémentation
- Le HTML contient `#avatar-frame`, `#portrait-bedroom`,
  `#portrait-seated-body`, puis `#avatar-container`.
- La chambre combine un fond portrait AVIF et une silhouette AVIF avec alpha.
  Crop source de la silhouette : x=120, y=680, largeur=670, hauteur=940
  dans la composition **941×1672**.
- Les CSS de `jade-theme.css` utilisent ce même repère : proportion,
  pourcentages pour le bas du corps et forme de masque de la tête.
  La pièce est mise à l'échelle **en une seule fois** pour fenêtre, plein
  écran et paysage; sur petit écran horizontal, la caméra recadre sans
  étirer les calques.
- `avatar.js` utilise la pose et le zoom de tête propres à la chambre
  hybride : position (.50,.61), multiplicateur d'échelle 1.30.
  La bouche, les expressions, la physique des cheveux et la pause
  du moteur Live2D restent gérées par le modèle d'origine.
- `room-motion.js` désactive les anciens sprites de la chambre,
  conçus pour l'ancienne image 4:3, seulement lorsque le mode
  hybride est actif. Les animations de cuisine sont indépendantes.

## Sécurisation de la mise en route
Le mode hybride n'est activé que lorsque **les deux images sont disponibles
et que Live2D est prêt**. Il retombe automatiquement sur l'ancienne chambre
si une image est absente/corrompue ou si le moteur ne peut pas démarrer.
Aucun asset du salon n'est chargé avant l'authentification du propriétaire.

## Assets à installer dans `src/jade_runtime/mobile_web/`
- `room-bedroom-portrait.avif` : décor vertical, sans Jade (864×1536).
- `jade-seated-body.avif` : corps assis et pouf avec transparence
  (670×940), sans tête animée.

Leur création à partir des deux images approuvées a été réalisée dans le
dossier de travail de ChatGPT. Le connecteur GitHub utilisé ne permet pas
d'envoyer directement leurs fichiers binaires depuis le dossier de travail.
**Deux fichiers AVIF transparents de 1×1 pixel sont provisoirement présents** :
ils satisfont la liste blanche et le packaging, mais sont volontairement
rejetés par le contrôle de dimensions. Le mode hybride ne s'active pas tant
que les deux fichiers définitifs ne sont pas installés au même chemin.
Ne jamais remplacer l'ancienne image de chambre avant validation visuelle.

## Recette indispensable sur appareil
1. En portrait Accueil, vérifier que la couture cou/cheveux n'est pas visible,
   en neutral, smile et lorsque la physique des cheveux oscille.
2. Basculer cuisine puis chambre pour vérifier l'absence de corps fantôme.
3. Contrôler le plein écran, la sortie du plein écran et le mode paysage.
4. Vérifier le micro et les animations de la cuisine.
5. Ajuster les constantes de tête (pose/masque) seulement après
   captures de la vraie sortie WebGL, pas par une résolution figée.

**Statut** : architecture intégrée, ressources graphiques et recette WebGL
sur téléphone encore à terminer. L'alignement parfait n'est pas affirmé.

## Correctif du 23 novembre : corps statique v2 et tête réellement isolée

- Le vrai `jade-seated-body.avif` (670×940, avec alpha) est maintenant commité.
  L'ancien calque comportait des mèches vertes à la base du cou :
  le nouveau ne contient **aucun cheveu ni visage**. Le haut du corps est
  recomposé à partir de l'illustration sans tête ; une petite zone de peau
  au cou se trouve derrière la tête animée. La silhouette a été abaissée.
- Le `clip-path` polygonal qui coupait visiblement le menton est supprimé.
  `head-isolation.js` désactive, par les opacités des *parts* Cubism,
  exclusivement les éléments BODY / ARMS / DRESS du modèle r20.
  Les yeux, le visage, les oreilles, tous les cheveux et leurs mouvements
  restent à l'origine dans le Live2D.
- En changeant de chambre vers cuisine, les opacités originales sont
  restaurées. Si l'API de séparation des parts n'existe pas ou si les IDs
  sont incompatibles, le mode assis ne s'active pas (ancienne chambre).
- Référentiel et camera responsive inchangés, pas de dimensions propres
  à un téléphone. Le rendu exact en portrait, paysage et plein écran
  nécessite encore la recette visuelle sur le vrai appareil.

## Correctif de profondeur Live2D et recentrage (23 novembre, v3)

Après recette sur Redmi Note 13, il était confirmé que l'affichage complet
du Live2D devant l'image statique recouvrait les épaules avec les cheveux
arrière. Un simple `z-index` ne peut pas résoudre ce problème puisque
cheveux avant et cheveux arrière appartiennent au même modèle Live2D.

En mode chambre assise, le moteur Pixi utilise maintenant un **seul** modèle
r20, mis à jour **une seule fois** par frame, mais dessiné deux fois avec un
masque de `drawables.opacities` restauré après chaque passe :

1. passe arrière : seuls les ArtMesh rattachés aux parties `HAIR_BACK*`;
2. sprite AVIF du corps assis, dans le même canevas WebGL ;
3. passe avant : visage, oreilles et `HAIR_FRONT*`, sans corps debout.

La sélection s'appuie sur `drawables.parentPartIndices` et sur les parents
des parts Cubism, et ne s'active pas si ces métadonnées sont indisponibles.
Aucune seconde instance Cubism ni perte des mouvements de cheveux n'est
introduite. Le DOM conserve le fichier AVIF pour le préchargement, mais
ne le peint plus en doublon.

L'ancrage Live2D horizontal en scène passe de `50 %` à `57,5 %` pour
corriger le visage visiblement décentré à gauche sur la recette réelle.
La chambre, le corps, la cuisine et leur géométrie de cadre ne changent pas.

**Reste à valider sur appareil** : après déploiement, confirmer la couture
au cou en mouvement, les mèches arrière occultées par le buste, le retour
cuisine et le plein écran. Aucun test headless ne remplace cette recette.

## Ajustement après captures du 23 novembre (v4)

Les captures montrent un visage trop à gauche du col du corps statique et une jonction horizontale visible. La caméra du modèle r20 est déplacée de x=.575 à x=.655 dans le repère responsive de la scène, sans toucher aux images ni à la cuisine. **Ce changement est une correction de position, pas une validation du raccord graphique.** La jonction du cou reste à retoucher sur l'asset statique et à vérifier en animation sur téléphone ; ne pas déclarer la recette réussie sans nouvelles captures.

## Correction de la régression de profondeur et assise (v5)

Les dernières captures Android montrent Jade **debout** sur un vieux décor 4:3,
avec des bandes vides en portrait : ce n'est pas une couture insuffisante mais
une non-activation du mode hybride. Le contrôleur cherchait par erreur
`parts.parentPartIndices`; le vrai Cubism Web Core fournit
`parts.parentIndices` (les ArtMeshes utilisent `drawables.parentPartIndices`).
Le test précédent reproduisait aussi cette erreur, d'où un faux positif CI.

Correctifs :
- La hiérarchie des parts vient de la bonne propriété API. Les éléments de
  coiffure arrière, de corps et du visage sont séparés en passes WebGL.
- Le corps assis et la chambre portrait sont activés dès que les images et
  l'isolation du corps debout sont prêtes, sans condition liée à Pixi.
- Si le compositeur échoue, le corps assis reste dans le DOM et le corps
  debout reste isolé dans Cubism ; la profondeur des cheveux est dégradée
  mais la posture assise n'est jamais supprimée.
- La chambre devient le conteneur de mesure `cqw/cqh`, évitant les unités
  prises par erreur dans le viewport.
- `jade-seated-ready` invoque la vraie fonction `sync` du moteur de décor ;
  les anciens éléments 4:3 ne sont plus superposés à la chambre portrait.
- La position x de la tête est recalibrée à .565 du repère de la scène,
  avec le même référentiel pour le corps et les deux passes Live2D.

Ces correctifs vérifient la structure et les contrats hors WebGL. La couture
réelle cou/épaules et les oscillations des mèches doivent être observées sur
le Redmi après déploiement ; aucune CI ne prouve la qualité du dessin.

## Correctif du cou et du mode de secours (23 novembre, v6)

Après cinq captures Redmi de la chambre assise, la zone vert foncé entre le
menton animé et le col statique apparaît sans cou humain visible. Le modèle
r20 ne fournit pas de partie de cou explicitement isolée : réactiver
`PartJAD_BODY_SKIN` exposerait potentiellement d'autres éléments du corps
debout. Conserver donc l'AVIF validé et l'isolation des parties du r20.

Le cou est un petit dessin vectoriel fixe, aux contours adoucis, assorti à
la peau du visage, **dans le même repère 941×1672 que le corps assis**.
En mode compositeur Pixi il est dessiné entre le sprite du corps statique
et la passe de la tête animée (l'ordre est cheveux arrière → corps assis →
cou → visage/cheveux avant). Sur un navigateur sans compositeur, la même
silhouette est rendue comme calque CSS juste au-dessus du corps AVIF,
toujours sous le canvas Live2D. Aucune seconde instance du modèle n'est
créée et aucune animation de cheveux n'est modifiée.

Une régression découverte pendant la correction est supprimée :
`isSeated()` ne dépend plus de la disponibilité du compositeur. Si
le mode dégradé est choisi, la pose assise et l'isolation du corps debout
restent actives ; seule la profondeur parfaite des cheveux est dégradée.

La position calibrée de la tête, les deux AVIF, l'alignement responsive
et la cuisine sont inchangés. Le rendu final de la couture et son maintien
en expression/mouvement nécessitent **encore une validation sur téléphone**
après déploiement ; les tests automatiques ne prouvent pas la qualité
visuelle du cou.


## Correction définitive du cou dans l’AVIF (23 novembre, v7)

Le corps assis validé est toujours `src/jade_runtime/mobile_web/jade-seated-body.avif`
au format **AVIF RGBA 670×940**. À partir des pixels du corps de
`develop`, la retouche ne concerne que la zone supérieure du col
(les 110 premières lignes) et remplace le fragment de peau détaché par
un cou et des clavicules continus. Les autres pixels du corps et du pouf
restent inchangés *avant réencodage AVIF*. Aucun cheveu n’est intégré à
l’asset statique.

La tentative antérieure de faux cou dessiné dans PixiJS et en CSS est
**retirée** des sources. L’AVIF contient maintenant toute la peau du
raccord ; les passes WebGL restent cheveux arrière → image assise →
visage et cheveux avant. Les composantes Live2D et la cuisine ne changent pas.

L’asset est au bon chemin et la correction est incluse dans la PR #45.
Le visuel et le chevauchement pendant les animations doivent encore être
confirmés en recette sur le téléphone. Les tests automatiques ne permettent
pas de prouver une jonction esthétique en mouvement.
