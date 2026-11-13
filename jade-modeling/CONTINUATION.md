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

Scène visage : après quatre essais non validés de fondu et d'alignement, le clignement conserve des cils gris, contours doubles ou un filet d'iris selon la variante. Le détail et les pistes sont consignés dans le [relais Astra](reports/Jade_r21_relais_Astra_yeux.md). Ne pas promouvoir ces essais ni déclarer le clignement validé.

Priorité précisée par l'utilisateur : poursuivre vers un modèle complet utilisable même imparfait, sans rester bloqué sur les yeux. Partir du checkpoint natif v31, préparer un export candidat Cubism/VTS et ses physiques, avec défaut visuel explicitement signalé ; aucune validation finale. Suivre [le plan professionnel actualisé](PLAN_QUALITE_PRO_20261113.md), notamment synchronisation des sous-calques dans des copies KRA/PSD, rig, physiques et retour ultérieur sur les yeux. Le modèle Huohuo a servi uniquement de référence structurelle ; pas de copie de ses fichiers. Ne pas régénérer les anciens filtres PSD.

Export en cours : la copie v31 avant atlas montre bien jambes et chaussures. Deux essais automatiques d'atlas 4096 (par Mesh puis Model Image) font disparaître le bas du corps : les coordonnées UV des pièces concernées sortent de [0,1]. Ces essais locaux sont non valides ; conserver v31 intact et corriger le remappage avant tout paquet VTS. La physique r20 comporte 37 sorties absentes de r21 ; ne pas la recopier sans adaptation.

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
