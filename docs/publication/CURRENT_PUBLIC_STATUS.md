# Statut de publication vérifié le 16 novembre 2026

Le dépôt GitHub [`goldaj/jade-vtuber`](https://github.com/goldaj/jade-vtuber) a été **observé comme public** (`private=false`, branche par défaut `main`). Ceci est un constat factuel, **pas** une attestation que l'historique, les secrets, les archives LFS ou les licences sont correctement assainis.

## Risques et contrôles à ne pas ignorer

1. Examiner les fichiers et **toutes les références/historiques Git**, y compris les anciennes branches, tags et objets LFS, avec une méthode qui n'expose pas les valeurs trouvées. Un scan CI après push ne prévient pas une exposition passée.
2. Auditer la provenance/licence du code et des éléments artistiques, dont les sources Cubism/Krita et l'avatar r20. Voir [`jade-modeling/PROVENANCE.md`](../../jade-modeling/PROVENANCE.md).
3. Vérifier séparément les paramètres publics des dépôts de sauvegarde et les éventuels exports/révisions déjà diffusés. **Ne pas copier de secrets dans une issue ou une PR**.
4. Si un secret réellement exposé est identifié, le faire révoquer et renouveler hors Git ; ne pas supposer qu'un simple nettoyage de branche suffit.
5. Ne pas transformer le snapshot de readiness daté du 28 octobre (`04-RELEASE-GATES.json`) en état courant ; il correspond à un ancien plan sur un autre dépôt.

L'outillage de prévisualisation reste distinct d'une publication ou de sa validation. Aucun changement de visibilité n'a été demandé ni effectué par le rangement documentaire.
