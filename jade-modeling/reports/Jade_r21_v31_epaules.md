# Jade r21 — candidat sous-cheveux épaules

Le candidat natif `jade_cubism_v005_r21_shoulder_underpaint_v31_candidate.cmo3` est une copie dérivée de r02 ; SHA256 `39C00ECC82468B70004590E6E8EC549C7C16150A03341A322CB5A223A7CEBA8C`. Deux bandes effilées sous les cheveux et le vêtement complètent la matière manquante. Elles suivent actuellement la branche globale de cheveux arrière ; leur comportement avec de futurs déformeurs locaux doit être ajusté.

Dans Cubism 5.2.03 PRO, la pose neutre et HeadZ −30/+30 ont été observés : les grandes ouvertures claires entre cheveux et épaules sont réduites ; la version rectangulaire précédente a été écartée à cause de bords visibles. Il reste des raccords fins, des combinaisons et l'ensemble du mouvement à examiner ; aucune validation VTube Studio ou qualité finale n'est revendiquée.

La source `Jade_r21_rear_hair_underpaint_candidate_v1.png` a été créée avec l'outil intégré de génération d'images à partir du maître graphique Jade fourni au modèle : cheveux arrière seuls sur fond transparent, couleurs vert/bleu-vert et texture existantes, overscan sous épaules, sans visage, yeux, oreilles, robe ni mèches avant. Elle est utilisée comme matière sous-jacente, sans remplacer les pixels du maître. `tools/cmo3_r21_shoulder_hair_underpaint.py` crée la copie expérimentale et conserve les objets et rasters précédents ; le checkpoint natif a ensuite été enregistré par Cubism.

Le KRA et le PSD ne contiennent pas encore ces sous-couches. Les synchroniser soigneusement avant tout réimport, préserver les sprites de paupières et l'iris, puis vérifier les mouvements et interactions sur la vraie chaîne de sortie.
