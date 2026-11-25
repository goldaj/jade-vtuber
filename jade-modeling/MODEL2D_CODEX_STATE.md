# Jade — état de reprise du modèle 2D

## Décision du 25 novembre 2026

Le propriétaire a approuvé le [plan directeur Live2D](MODEL2D_MASTER_PLAN.md). La préparation est autorisée. Elle couvre la documentation, le retrait des fichiers obsolètes confirmés et l’ouverture des copies de travail dans les outils. **La production attend un feu vert distinct du propriétaire.** Celui-ci observera les validations en direct, sans ScreenToGif.

- **État :** plan approuvé et préparation de l’unité 1 (ART-001/002) réalisée. Les unités d’édition et de recette attendent le feu vert.
- **Base locale :** `Jade_r21_v32.cmo3`, 62 650 660 octets, SHA-256 `C26C686DBF6A9DE08FBAD281088118A6EDF2CFBDBDCEC993058C039F81294D1C`. Le v31 natif reste un jalon de référence visuelle.
- **État de la recette :** l’ourlet festonné a été revu dans Cubism sur la base intermédiaire de l’atlas recalé. Le v32 complet, son clignement et son export VTube Studio restent à valider.
- **Préparation locale :** une copie `Jade_r21_travail.cmo3` est prête sur D:. PSD2Live a chargé le v32 dans un projet séparé (canevas 3840 × 5000, 78 maillages et 42 paramètres). Le propriétaire a ouvert la copie dans Cubism 5.3.05 et Turboism la voit comme document actif avec 78 maillages et 42 paramètres. Le projet PSD2Live local enregistré sous `Jade_r21_atelier.psd2live` contient aussi la physique candidate et Smile/Sad. La comparaison du rendu appartient au lot de production.
- **Outils :** Cubism PRO 5.3.05 et Turboism pour le CMO3 natif, PSD2Live pour la préparation et les essais sur copie isolée. VTube Studio dispose du r20 de secours. Les fichiers r21 de physique, d’expressions et d’idle sont en attente d’assemblage.
- **Branche :** plan aligné sur `develop` à `c3c17b0`, en préparation sur `codex/jade-r21-reprise`. Le modèle de travail est encore local sur D:.

**Prochaine action de production après le feu vert.** Observer le plein pied et les pièces sensibles du v32 en vue atlas dans Cubism, en vue d’un premier chargement r21 dans VTube Studio. Exécuter le lot avec le modèle Codex courant s’il convient et réserver un relais aux difficultés qui le justifient.

## Informations à relever à chaque jalon

Indiquer l’unité, le statut, la version ou le SHA, le fichier obtenu, la vérification réellement faite et son résultat, les limites utiles et la prochaine action. Pour les changements de branche ou de modèle Codex, suivre le [protocole](MODEL2D_CODEX_PLAYBOOK.md). [Point de reprise et fichiers](CONTINUATION.md) · [Passation](../docs/operations/handoffs/2026-11-25-codex-jade-r21-reprise.md)
