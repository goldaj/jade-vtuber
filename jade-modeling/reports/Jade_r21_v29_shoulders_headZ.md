# Jade r21 — raccord épaules / HeadZ (jalon natif v29)

## Résultat du 12 septembre 2026

- Sauvegarde native : `working_v005/jade_cubism_v005_r21_shoulders_head_z_v29.cmo3`, 26 733 480 octets, 18:35:56. SHA256 `F414CDC057CEE33036F975F0455EE43846988DECFB05ACACC0397AC91A6C5208`.
- r02 : robe/manches/cou remappés, fragments de tissu retirés des onze objets cheveux concernés. r03 : ordre avant 510. r04 : deux ArtMeshes de pointes ajoutés, mais pointes encore invisibles.
- Diagnostic corrigé : les PNG segmentés sur disque **avaient aussi alpha=0** sur les zones blanches. Leur aperçu RGB avait été mal interprété. Le probe natif r04 confirme que les liaisons aux images n'étaient pas rompues. Les assertions structurelles seules ne validaient pas l'art.
- r05 : les deux nouveaux meshes utilisent maintenant le **dessin maître RGBA intact**, avec UV canvas/3840×4160. Ses deux pixels blancs de référence sont opaques. Aucun bitmap modifié ni redessiné. Outil `tools/cmo3_r21_tips_master_texture.py`.
- Observations natives r05 : les deux pointes sont visibles, suivent HeadZ -30/+30 et reviennent au neutre ; le col reste indépendant. Captures `jade_r21_v29_r05_plus30.png`, `minus30.png`, `neutral.png`. Sauvegarde v29 au neutre.
- Limite nette : chevelure arrière encore ajourée, petits fragments isolés près des manches, raccords derrière le cou inachevés. Ce checkpoint valide la restauration des pointes et la première inclinaison, **pas** une finition professionnelle globale.

## Modifications fonctionnelles

- Base : checkpoint natif v28 (appuis, jupe, détente R/L, respiration).
- Ajout HeadZ : ParamAngleZ -30/0/30 → rotation -15/0/15°, pivot canvas (1920 ; 1220,52). Neutre et 66 meshes existants conservés exactement.
- Nouvel art sous les cheveux : `assets/live2d/r21_professional_art/Jade_r21_shoulders_underpaint_v1.png`, RGBA 1088×1446, transparence réelle. Seul le haut est intégré ; pas de remplacement des jambes/pieds, mains ou yeux.
- Candidat r01 chargé dans la session Cubism 5.2.03 PRO existante. Le test Z +30 expose encore les fragments de tissu emportés par les meshes cheveux et les pointes blanches fixes dans le tissu : r01 non validé comme jalon.
- Correction r02 en cours : réutiliser le sous-dessin sans cheveux pour BODICE/SLEEVE_L/SLEEVE_R/NECK_SKIN en conservant leurs formes/parents ; retirer les fragments de tissu mobiles, rétablir les vraies pointes des mèches avant.

## Assets / outil de création

Création par édition d'image, à partir de `master_v4_rig_layers_v1/layers/JAD_R21_DRESS_BODICE.png`. Aucune retouche Python du bitmap ; intégration par maillage et UV. Une première sortie RGB avec damier peint a été écartée. Seconde sortie RGBA retenue : `C:/Users/<utilisateur>/.codex/generated_images/019fa44a-97ed-7341-8f72-ad881b1af28b/exec-2401ae5f-c696-43c2-9a3d-d71d5a28ed16.png`, copiée dans le projet.

### Prompt de sous-dessin

Use case: precise-object-edit. Asset type: production Live2D hidden-body underpainting, not a new character design. Image 1 is the exact edit target, a cropped torso sprite of Jade. Remove ALL green and white hair from this image, including the two white-tipped front locks on the collar, all rear hair protrusions beside both shoulders and sleeves, and dark hair behind the neck. Reconstruct the natural continuous sage-green short-sleeved floral dress and rounded cloth shoulders underneath those removed locks. Keep the existing neck skin and collarbones; fill only what was hidden by hair. The shoulders must be complete and smoothly rounded, without missing chunks, holes or disconnected islands. The neckline remains the SAME shallow V-neck, same position and double fabric trim, not a deep neckline. Preserve the exact original front-facing body proportions, sleeve ends, arms, hands, belt, every existing cream flower and dark-green leaf, colors, shading, linework and crop. Do not change, restyle, recenter, rotate, enlarge or shrink the figure. Keep every feature outside the hair regions unchanged. No head, face or eyes: do not add a head. Same portrait framing as target 1339 by 1779, neck cut off at the top and skirt continuing beyond bottom. Genuinely transparent alpha background around the figure and between arms and dress, no checkerboard drawn in pixels, no white/green fringe, no text. This clean torso will be behind separately rigged hair, so absolutely no residual hair or white hair tips may remain anywhere.

### Prompt de transparence

Use case: background-extraction. This is the exact edit target. Keep the entire hair-free dress, neck skin, arms and hands pixel-aligned, with the same size, framing, neckline, folds and floral details. Remove ONLY the gray-and-white checkerboard background and its faint white artifacts, including both spaces between arms and dress. Output a genuinely transparent RGBA PNG with alpha=0 outside the figure, NOT a rendered checkerboard and NOT a solid white background. Crisp natural antialiased outline, no gray white or green halos. Do not repaint the cloth or skin, do not add a head or hair, do not change the body or pose. This image is a Live2D texture and must have real transparency.

## Limites conservées

Cette opération ne constitue pas une validation professionnelle globale : X/Y, regard, cheveux souples, oreilles, physiques et VTS restent au plan. Aucun nouvel export VTS ni vidéo. KRA/PSD non synchronisés : ne pas réimporter l'ancien filtre PSD des images ajoutées.
