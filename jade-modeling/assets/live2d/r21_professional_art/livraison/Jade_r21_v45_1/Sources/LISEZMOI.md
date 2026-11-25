# Sources de peinture de Jade v45.1

Ouvrir **Jade_r21_v45_1.kra** dans Krita ou **Jade_r21_v45_1.psd** dans un éditeur compatible Photoshop. Les deux copies ouvrent Jade en pied au repos sur un canevas transparent de 3840 × 5000 px.

## Retoucher une pièce

Le groupe **Materiaux natifs - edition** contient les 76 plaques référencées par les 93 maillages du CMO3 v45.1, rangées par famille. Chaque calque conserve le nom de son *ModelImage* et sa résolution native. Pour peindre une pièce, masquer le groupe de vue, afficher celui des matériaux et isoler le calque voulu. Les quatre calques `MOUTH_OPEN_*` portent la bouche de parole v43. Les `EYE_*_SOCKET_SKIN` portent les deux iris v45.1 et les `EYE_*_CLOSED_TRUE` les deux yeux entièrement fermés. Les jambes et leurs chaussures utilisent chacun une seule pièce continue par côté. Le groupe des autres matériaux inclut des pièces historiques encore référencées par le rig.

Le groupe visible **Jade au repos - surfaces du modele** contient les 24 surfaces peintes qui composent cette pose, dans l’ordre Cubism. Cette vue restitue les déformations, les masques et les recouvrements au repos. Elle sert de repère pour peindre et pour juger les raccords. Les animations, le mouvement du regard et le changement de forme des lèvres se reprennent dans le CMO3. Un changement sur une plaque demande de le reporter dans le CMO3 puis de régénérer la vue de repos lors de la prochaine livraison.

## Reporter dans Cubism

Pour retrouver une pièce, chercher le nom de son calque dans **Sources.json**. Le manifeste associe son GUID, le membre PNG dans le CMO3, son empreinte, ses dimensions, son placement d’édition et les maillages qui l’emploient. Les plaques brutes conservent leurs pixels à l’échelle 1:1 dans le document. Quand le modèle agrandit ou déforme la pièce, sa position finale est visible dans le groupe de repos. Les marges complètement transparentes se reconstruisent à partir de la taille et de l’origine du manifeste. Les groupes de matériaux incluent les plaques des masques ; leurs liens et leurs valeurs animées sont portés par le rig.

Les KRA et PSD ont été rouverts et leurs 100 calques de peinture comparés au contenu source. Le manifeste consigne la comparaison du plein pied recomposé avec le rendu de Cubism Core sur six zones, ainsi que les empreintes des documents. Les anciens KRA/PSD restent dans le projet d’origine pour consulter l’historique du dessin.
