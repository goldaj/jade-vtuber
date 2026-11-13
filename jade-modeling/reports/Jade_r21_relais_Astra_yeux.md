# Relais Astra — fermeture des yeux de Jade r21

## Décision et limite

L'utilisateur souhaite avancer vers un modèle complet utilisable, même imparfait, sans rester bloqué sur une sous-étape. Les essais ci-dessous n'ont pas été retenus : repartir du candidat natif v31 d'épaules publié, sans affirmer que son clignement est validé. Avant livraison professionnelle, reprendre la fermeture de façon propre et contrôler le mouvement continu.

## Observations et essais locaux

- Le vrai `CLOSED_TRUE` disparaît dès 4 % d'ouverture dans v31 alors que la paupière ouverte est encore très fine : transition abrupte entre formes distinctes.
- `blink_handoff_r01` élargit le fondu complémentaire : cils gris à 0,04. `blink_handoff_r02` utilise un recouvrement plus opaque : double contour visible à 0,12.
- `blink_align_r01` rapproche cadre `LID_FRAME` et `APERTURE_MASK` de la courbe du sprite fermé. Aucun triangle inversé dans le contrôle géométrique, mais le double contour persiste à 0,04–0,06.
- Déplacer directement les sommets du sprite fermé hors de sa grille a échoué lors de l'inversion ; aucun fichier n'a été écrit pour cette variante. `blink_warp_r01` anime à la place les deux déformeurs `D_JAD_EYE_*_CLOSED` sans modifier leurs sprites : ouverture native réussie, mais à 0,06 la paupière reste grise et un filet bleu demeure visible. Aucun contrôle d'animation continue n'a été effectué.
- Les onze poses du maillage d'iris ouvert sont géométriquement identiques ; le masque est animé. Cela ne prouve pas que le rendu en mouvement soit satisfaisant.

## Pistes de reprise

Aligner manuellement les contours et les keyforms du cadre, du masque et du vrai dessin fermé ; régler séparément leurs opacités et leur ordre d'empilement. Rechercher une transition sans cil fantôme ni iris qui transparaît sous la paupière. Ne pas redessiner le sprite fermé ni comprimer l'iris ; conserver les deux yeux indépendants et les extrémités identiques aux originaux. Vérifier ensuite fermeture, ouverture et réouverture en continu à plusieurs vitesses dans Cubism, puis VTube Studio.

Les essais et leurs scripts/audits sont conservés dans l'espace de travail local uniquement : `working_v005/jade_cubism_v005_r21_v31.TEST_blink_handoff_r01.cmo3`, `...handoff_r02.cmo3`, `...align_r01.cmo3` et `...warp_r01.cmo3`, `tools/cmo3_r21_blink_handoff_v31.py`, `tools/cmo3_r21_blink_align_v31.py`, `tools/cmo3_r21_blink_closed_deformer_v31.py`, et les audits `reports/Jade_r21_v31_blink_*.json`. Ce sont des brouillons, pas des checkpoints validés ni des livrables. Les captures locales ciblées sont indiquées dans `CONTINUATION.md` local.
