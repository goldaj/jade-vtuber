# Revue de conservation du modèle — 16 novembre 2026

Périmètre : 221 fichiers suivis sous `jade-modeling/` dans `develop` au commit `5368f008b8970532702ceac1e50ca6b60fd5c1d7` ; revue de l'arborescence et des SHA de blobs Git, pas de contrôle visuel des fichiers LFS ou de disponibilité locale Cubism.

## Constat factuel

- **Aucun SHA Git identique parmi les 221 fichiers** : aucune copie d'octets strictement identiques évidente à supprimer. Cela n'exclut pas des variantes graphiques quasi identiques.
- Les sources r21 et le package runtime r20 ont des rôles différents. Les CMO3 v30, v31 et r02, KRA/PSD et master ne doivent pas être fusionnés/supprimés sur leur simple nom ; le [guide modèle](../MODEL_GUIDE.md) donne les chemins et leurs statuts.
- Les rapports antérieurs v28/v29 et les outils `cmo3_*` versionnés peuvent représenter une histoire expérimentale. Leurs dépendances, recettes et utilisation réelle n'ont pas été tracées exhaustivement. **Pas de suppression décidée ici.**

## Nettoyage futur sans perte

1. Distinguer les scripts génériques, les scripts d'étape et les outils d'export ; mesurer les imports et les chemins mentionnés dans les guides.
2. Identifier les candidats historiques dans `reports/` et `tools/`, et archiver **uniquement après** vérification qu'ils ne sont ni appelés, ni nécessaires à la reconstruction des rig/rapports.
3. Ne pas renommer des objets LFS, des fichiers référencés par `ASSET_MANIFEST.json`, ni la hiérarchie `runtime-installed/` avant validation des références et tests Cubism/VTube Studio.
4. Effectuer toute réduction graphique à partir d'un backup récupérable, avec manifeste et empreintes ; ne pas confondre un artefact généré avec un jalon natif.

**Décision :** conserver les 221 éléments à cette étape, documenter le tri futur plutôt que risquer une suppression destructrice.
