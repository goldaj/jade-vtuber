# Objectif actuel

Terminer Jade r21 professionnel, plein pied et fonctionnel dans VTube Studio. Modèle uniquement.

# Terminé

- Dernier checkpoint NATIF : assets/live2d/r21_professional_art/working_v005/jade_cubism_v005_r21_back_hair_restore_v30.cmo3, 2026-09-13 07:51:16 ; 29 785 986 octets ; SHA256 2AFC3C21F451626156B138733D0BC792CEB3463E086FA21334307FFC8B73A1EE.
- v30 : six segments arrière restaurés sous les oreilles depuis le maître RGBA, deux raccords derrière le cou ; 74 ArtMeshes. Neutre et HeadZ ±30 observés. Petits fragments bas et raccords latéraux encore imparfaits.
- v29 : HeadZ -30/0/+30 → -15/0/+15°, robe/manches/cou séparés des cheveux, deux vraies pointes blanches mobiles restaurées depuis le maître RGBA intact. Deux extrêmes et retour neutre observés. Pas une validation de la chevelure arrière ni de qualité finale.
- v28 intact : appui, jupe, détente genoux R/L et souffle ; v27 hiérarchie corps ; v26 plein pied ; v25 iris stables, vrais CLOSED_TRUE ; v24 MouthForm3×6.

# Étape en cours

Cheveux A/B : candidat v30.TEST_hair_leaves_r02 créé (SHA68617D558A59593E54C2582AB7845FFA317D8A7E0676E25D5B5514B083C95F62), pas encore natif. Neuf feuilles, neuf paramètres indépendants et 45 poses ; deux LOWER reconnectés, deux bandes TEMPLE arrière ajoutées. VTS inchangé.
Cubism 5.2.03 PRO même session ; r01 testé LockL ±1 puis fermé ; r02 en cours de chargement. Ne pas écraser v30 ni r01/r02.

# Prochaine action exacte

Terminer le jalon natif r02 : observer raccords, une pose de frange et HeadZ±30, revenir au neutre puis Save As jade_cubism_v005_r21_hair_leaves_v31.cmo3. Ensuite feuilles arrière et physiques ; ne pas refaire LockL±1 déjà observé sur r01 (formes inchangées dans r02).

# Fichiers importants

- tools/cmo3_r21_hair_independent_leaves.py (--seam-roots) et cmo3_r21_hair_seam_roots.py ; reports/Jade_r21_v30_hair_leaves_r02.json.
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
- Relance continuer-jade-r21-toutes-les-5-h-10 ACTIVE (310 min), ne pas dupliquer ; désactiver à achèvement réel. Aucun crédit/reset.
