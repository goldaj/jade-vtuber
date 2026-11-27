# Volume du visage de Jade sur mobile

La PWA utilise désormais la v49.1 validée sur téléphone. Cette fiche conserve la planche, la source Cubism v45.5 et les essais de rotation antérieurs pour reprendre le travail de dessin. Les exports intermédiaires v47.2 et v48 gardent leurs chemins historiques. [Version mobile validée](../CHANGELOG.md#2026-11-26--jade-mobile-v491-validée-sur-téléphone)

## Références et diagnostic

Le propriétaire a fourni quatre captures de l’application et validé deux portraits dessinés de Jade enjouée, tournée à gauche et à droite. Ces portraits guident la perspective. La Jade de `develop` fixe les proportions du personnage, notamment la petite taille de son nez. Huohuo sert de repère pour la façon dont le mouvement se lit à la taille d’un téléphone.

Le MOC3 servi sur le poste correspondait au fichier v45.4 de `develop` (`3777683ed76e`). À la rotation maximale, l’iris proche gagnait entre 24 et 33 % de largeur suivant le côté. Les contrôles de la vue frontale et des poses finales de bouche ne révélaient pas ce défaut. À mi-clignement, la paupière supérieure avait déjà masqué la pupille alors que la partie très claire du bas de l’iris restait apparente.

Les essais ont conservé les quatorze motions et la course horizontale du modèle. La production a porté sur la construction du visage, de la frange et de l’arrière du crâne, ainsi que sur la rencontre des deux paupières. La recette mobile compare les poses avant et après sur les mêmes entrées.

Le premier essai où les yeux gardaient leurs proportions présentait encore une cassure nette de la joue sous la longue mèche. Une fois celle-ci passée derrière la peau, le menton restait en retrait pendant que la bouche tournait. Les dessins gauche et droit approuvés par le propriétaire ont guidé la reprise du contour de la mâchoire. Les essais où le nez était accentué ont été écartés.

Le modèle local Huohuo a été observé aux cinq positions −30, −15, 0, +15 et +30 de son axe horizontal. Le menton y accompagne la bouche, la joue éloignée se raccourcit et le bas du cou bouge très peu. Dans le showcase d’Ironmouse Pink Rock, la mèche recouvre l’étoile sur la joue quand la tête tourne. La présentation de Neuro-sama permet de suivre la joue sous la frange pendant la parole et jusqu’au clignement. [Ironmouse par 2wintails à 21 s](https://www.youtube.com/watch?v=e2hTtltCmXc&t=21s) · [Présentation de Neuro-sama à 1 min 08 s](https://www.youtube.com/watch?v=OSDL-AkIRME&t=68s)

## Édition et reprise

La [planche validée de Jade](../../../jade-modeling/assets/live2d/r21_professional_art/Jade_enjouee_trois_quarts_gauche_droite.png) fixe le dessin dans les deux orientations. La [source éditable v45.5](../../../jade-modeling/assets/live2d/r21_professional_art/working_v005/Jade_r21_v45_5_trois_quarts.cmo3) s’ouvre dans Cubism PRO 5.3.05. Pour la PWA, exporter le MOC3 pour SDK 5.0, à 3 840 pixels par unité et en textures de 4 096 px. Le manifeste mobile de l’application associe cette géométrie aux quatorze motions d’intention et à la physique.

La sonde du rig se lance avec Node et le Cubism Core JavaScript utilisé par l’installation mobile. Elle suit le menton, la bouche, les yeux et le clignement aux inclinaisons et ouvertures combinées. Le contrôle visuel porte en plus sur le contour réellement découvert sous les cheveux et sur la jonction avec le cou. [Sonde du trois-quarts](../../../jade-modeling/tools/check_r21_face_turn.cjs)

## Pourquoi le premier essai a été refusé

Dans les trois captures du propriétaire, le bas de la joue changeait de pente juste devant le cou. Cette cassure donnait l’impression d’un deuxième coin avant le menton. Sur les poses gauche et droite, la vraie pointe restait respectivement à 9 et 11 pixels de la position dessinée sur le canevas de 3 840 px. L’écart médian de l’ensemble de la mâchoire était voisin de 2 pixels et sous-estimait le défaut. La parole et le clignement rendaient le problème visible dans des poses combinées.

La correction ajoute deux formes latérales au maillage de peau sous le déformeur de tête. Elles règlent séparément la pointe et les pentes de joue sur les deux dessins. La pose de face reste la troisième forme de ce maillage. Les poses intermédiaires utilisent l’interpolation de Cubism, aussi bien au repos que pendant chacune des quatorze motions. Le cou se prolonge derrière la mandibule quand Jade relève la tête.

Le propriétaire a ensuite désigné la rangée supérieure de la planche à sept poses. Le raccord avec les yeux et la coiffe restait en cause lorsque la tête était visible en entier. Ce témoin possède déjà la nouvelle mandibule. La recette reprend les mêmes poses, dont le mi-clignement à X +24 / Y −6 et la parole à X +30 / Y +5 / Z −5. Les deux dessins approuvés ont des inclinaisons différentes. Pour comparer leur perspective en rotation, le contrôle remet chaque dessin à niveau et prend la calotte comme repère de taille.
