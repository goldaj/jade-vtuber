# Provenance et droits à régulariser sur le dépôt actuellement public

Cette sélection figure déjà dans le dépôt GitHub public `goldaj/jade-vtuber` (vérifié le 16 novembre 2026). Elle conserve les
dernières sources pertinentes du poste ; elle n'établit pas les droits de
redistribution. Les archives et versions intermédiaires restent locales.

| Groupe du manifeste | Provenance locale | Situation |
| --- | --- | --- |
| `current-editable-source` | `Documents/Jade AI Streamer Project/assets` | CMO3 natif v30, candidat courant r02, derniers KRA et PSD pertinents |
| `current-art-components` | Derniers ensembles du même dossier | Couches du maître v4, endpoints yeux/bouche et base originale des yeux fermés |
| `current-art-input` | Entrées artistiques courantes du même dossier | Derniers apports du bas du corps, épaules, bouche, yeux et maître nettoyé |
| `current-runtime` | Package r20 installé dans VTube Studio | Textures, physique, expressions, mouvements et réglages du dernier runtime pertinent |
| `current-documentation` | Plans et derniers rapports liés à la reprise | État courant et preuves immédiatement utiles |
| `current-tools` | Sources locales de `tools/` | Outils de la reprise courante et fermeture de leurs dépendances locales |

Les modèles Pixiv et autres exemples tiers situés dans `pixiv_free_models` ne sont
pas importés comme sources Jade. Les captures et références artistiques déjà
présentes dans les dossiers Jade restent à attribuer individuellement avant une
mise en public. Ne pas leur appliquer une licence générale sans vérification.

Le `pyproject.toml` actuel déclare `Jade contributors`, sans établir à lui seul la provenance historique de tous les composants. Il faut retracer les auteurs et licences de la base d'origine, conserver les mentions requises et distinguer les contributions propres au projet. Les fichiers de
licence ou de provenance existants dans les sources ne doivent pas être supprimés.

Comme le dépôt est déjà public, il faut traiter en priorité la provenance et les droits : établir une liste des auteurs et licences par composant,
vérifier les droits des images/textures/sons/animations et des sources modifiées,
remplacer ou retirer ce qui ne peut pas être redistribué, puis terminer le
nettoyage des identifiants dans toutes les références de l'historique Git.
