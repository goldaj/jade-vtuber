# Objectif actuel

Terminer Jade r21 professionnel, plein pied et fonctionnel dans VTube Studio. Modèle uniquement.

# Terminé

- Dernier checkpoint NATIF : assets/live2d/r21_professional_art/working_v005/jade_cubism_v005_r21_back_hair_restore_v30.cmo3, 2026-09-13 07:51:16 ; 29 785 986 octets ; SHA256 2AFC3C21F451626156B138733D0BC792CEB3463E086FA21334307FFC8B73A1EE.
- v30 : six segments arrière restaurés sous les oreilles depuis le maître RGBA, deux raccords derrière le cou ; 74 ArtMeshes. Neutre et HeadZ ±30 observés. Petits fragments bas et raccords latéraux encore imparfaits.
- v29 : HeadZ -30/0/+30 → -15/0/+15°, robe/manches/cou séparés des cheveux, deux vraies pointes blanches mobiles restaurées depuis le maître RGBA intact. Deux extrêmes et retour neutre observés. Pas une validation de la chevelure arrière ni de qualité finale.
- v28 intact : appui, jupe, détente genoux R/L et souffle ; v27 hiérarchie corps ; v26 plein pied ; v25 iris stables, vrais CLOSED_TRUE ; v24 MouthForm3×6.

# Étape en cours

Étape 1 : v30, r02, KRA, PSD et maître comparés aux objets LFS ; `python jade-modeling/verify_assets.py` réussit après correction de l'empreinte du présent suivi dans le manifeste. Package r20 présent et 23 références vérifiées ; rendu VTube Studio non recetté.

Cheveux A/B : candidat natif `assets/live2d/r21_professional_art/working_v005/jade_cubism_v005_r21_shoulder_underpaint_v31_candidate.cmo3`, 31 143 973 octets, SHA256 39C00ECC82468B70004590E6E8EC549C7C16150A03341A322CB5A223A7CEBA8C. Il dérive de r02, conserve ses neuf feuilles et ajoute deux sous-peintures effilées derrière les épaules. Neutre et HeadZ ±30 observés : les larges ouvertures sont réduites ; raccords fins et mouvements combinés encore à vérifier. Ce candidat n'est pas une validation professionnelle ni un export VTS. Les sources KRA/PSD ne sont pas synchronisées.

# Prochaine action exacte

Scène visage : les essais locaux `blink_handoff_r01/r02` et `blink_align_r01` sont non validés. Les deux premiers produisent respectivement cils gris et double contour ; le troisième rapproche cadre et masque sans inversion de triangles mais conserve un double contour vers 0,04–0,06. Le sprite fermé ne peut pas simplement être translaté hors de son déformeur : tentative refusée avant écriture. Dans Cubism, reprendre l'alignement manuel des keyforms et du déformeur des vrais yeux fermés, sur une copie versionnée ; préserver l'iris géométriquement fixe et vérifier le mouvement continu avant promotion. Cubism est ouvert sur l'essai local d'alignement.

Suivre ensuite [le plan professionnel actualisé](PLAN_QUALITE_PRO_20261113.md) : terminer la scène visage/VTS ; isoler et intégrer les sous-calques dans des copies KRA/PSD, puis poursuivre raccords, rig, physiques et export. Le modèle Huohuo a servi uniquement de référence structurelle : physiques distinctes pour frange, côtés, arrière, épi et oreilles ; pas de copie de ses fichiers. Ne pas régénérer les anciens filtres PSD.

# Fichiers importants

- tools/cmo3_r21_hair_independent_leaves.py (--seam-roots) et cmo3_r21_hair_seam_roots.py ; reports/Jade_r21_v30_hair_leaves_r02.json.
- `tools/cmo3_r21_shoulder_hair_underpaint.py` et `assets/live2d/r21_professional_art/Jade_r21_rear_hair_underpaint_candidate_v1.png` : image générée à partir du maître et bandes ajoutées au candidat ; détail dans [le rapport de travail](reports/Jade_r21_v31_epaules.md). La bitmap n'est pas la source KRA/PSD synchronisée.
- select_hair(xml,{token:valeur}) fournit un miroir géométrique pour les neuf feuilles ; ne jamais le sérialiser en livrable. Feuilles parentes de HeadZ, compensées au neutre (anciens parents trop étroits pour l'amplitude).
- tools/cmo3_r21_back_hair_master_restore.py ; reports/Jade_r21_v29_back_hair_r01.json : restauration v30, rasters intacts.
- tools/cmo3_r21_tips_master_texture.py : r04→r05, utilise le maître intact pour les deux PAINTED_TIP ; audit reports/Jade_r21_v28_shoulders_r05.json.
- assets/live2d/r21_professional_art/master_v4_assets_v1/Jade_r21_master_v3_canvas_3840x4160.png SHA011B9D9C06190CE044120BA7640FEB575A0A76A10F620575BD90F2A20CBB3275 ; vrais blancs alpha255.
- tools/cmo3_r21_hair_shoulder_cleanup.py : onze maillages nettoyés r02 ; géométrie LOCK_ROWS ; rasters segmentés incomplets.
- tools/cmo3_r21_head_z_v28.py::neutral_model(xml) : miroir pour résoudre neutre corps+HeadZ. Ne jamais sérialiser le miroir comme modèle final.
- tools/cmo3_r21_underpaint_clone.py ; cmo3_r21_add_model_image.py : ajouts locaux/texture sans édition bitmap.
- reports/Jade_r21_v29_shoulders_headZ.md : résultats natifs, diagnostic corrigé et limites.
- v29 source candidat : working_v005/jade_cubism_v005_r21_v28.TEST_shoulders_r05.cmo3 SHA6AA8B90E0B9C992421DD07A2823F27AD34937E34481CEBC49782EFB549D568B5.
- KRA v9 / PSD rig_only_v2 NON synchronisés avec nouveaux art et plein pied ; ne pas régénérer les anciens filtres PSD.
- tools/cubism_window_driver.py : secours capture Java ; refuse bureau verrouillé et input si focus incorrect. Capture standard SetIsBorderRequired échoue, ne pas reboucler. Pour focus récalcitrant utiliser sky.activate_window sur la fenêtre Cubism retournée, puis état du secours.

# Vérifications utiles

- python tools/cmo3_inventory.py --details --pretty <modele.cmo3>
- (Get-FileHash -LiteralPath <modele.cmo3> -Algorithm SHA256).Hash
- ParamAngleZ 3e ligne en haut ; -30,0,+30. Outils de modèle : vérifier alpha réel et formes, pas seulement nombre de refs. Ancien ex._xml_summary rejette ROOT inline légal, ne pas modifier le modèle pour lui.

# Décisions / limites

- Copies versionnées, checkpoints intacts, Cubism PRO jamais mis à jour ; même session, stop bureau verrouillé.
- Vrais sprites fermés et iris stable au blink ; oreilles normales en Surprise ; plein pied obligatoire.
- Objectif NON terminé : raccords/art, tête/regard, cheveux souples, oreilles, physiques, idle, expressions/toggles, sync source, export/mapping VTS et contrôle final restent.
- ScreenToGif uniquement final. Aucun code applicatif modifié.
- État actuel de la relance automatique non revérifié ; ne pas dupliquer, désactiver à achèvement réel. Aucun crédit/reset.
