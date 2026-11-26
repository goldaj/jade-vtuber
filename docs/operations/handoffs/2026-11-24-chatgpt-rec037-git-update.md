# REC-037 — Correctif mise à jour distante PyCharm

Le propriétaire confirme le redémarrage depuis Android mais pas la mise à jour. Le superviseur refusait tout fichier local modifié ou non suivi avant même le fetch. Remplacement par un merge fast-forward natif Git avec protection des fichiers locaux, sans reset ni stash ; diagnostic filtré et état explicite dans les deux interfaces. LFS est réessayé même si HEAD a déjà avancé. La configuration Run personnalisée reste inchangée.

Tests ajoutés dans tests/test_jade_remote_control.py : vrais dépôts Git temporaires, conservation des fichiers, refus de conflit et masquage des URLs. CI à vérifier ; recette PC/Android à valider. Amorçage : arrêter une fois le Run, récupérer develop manuellement sans écraser les modifications, puis relancer le Run existant. REC-037 reste À valider.
