# Statut de publication vérifié le 27 novembre 2026

Le dépôt GitHub `goldaj/jade-vtuber` est public et sa branche par défaut est `main`. Le 27 novembre, `main@e5dd826` a reçu l’état de `develop@56eb108` comme point de retour avant nettoyage. Le projet conserve les audits de provenance et de confidentialité ainsi que l’outil d’export isolé. [Dépôt GitHub](https://github.com/goldaj/jade-vtuber) · [Instantané](https://github.com/goldaj/jade-vtuber/commit/e5dd826)

## Risques et contrôles à ne pas ignorer

1. Examiner les fichiers et **toutes les références/historiques Git**, y compris les anciennes branches, tags et objets LFS, avec une méthode qui n'expose pas les valeurs trouvées. Un scan CI après push ne prévient pas une exposition passée.
2. Auditer la provenance/licence du code et des éléments artistiques, dont les sources Cubism/Krita et l'avatar r20. Voir [`jade-modeling/PROVENANCE.md`](../../jade-modeling/PROVENANCE.md).
3. Vérifier séparément les paramètres publics des dépôts de sauvegarde et les éventuels exports/révisions déjà diffusés. **Ne pas copier de secrets dans une issue ou une PR**.
4. Si un secret réellement exposé est identifié, le faire révoquer et renouveler hors Git ; ne pas supposer qu'un simple nettoyage de branche suffit.
5. Ne pas transformer le snapshot de readiness daté du 28 octobre (`04-RELEASE-GATES.json`) en état courant ; il correspond à un ancien plan sur un autre dépôt.

L’outillage de prévisualisation produit un export local selon sa liste de fichiers. Examiner en particulier l’historique, les ressources Git LFS et les droits de redistribution pour toute utilisation de cet export.
