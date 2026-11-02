# CI Jade PR #2 : constat d'échec avant attribution de runner

**Derniere observation : 28 octobre 2026.** Branche isolée `research/gpt6-jade-publication-readiness-20261028`.
Ne pas confondre **absence de runner** avec echec des tests du projet.

## Observation GitHub, vérifiable

- Runs sur la PR #2 : `40667008390` (Jade rebuild) et `40667008628` (publication), puis `40667266039` et `40667266012`.
- Jobs du HEAD `d88377e3824c6372ccd3926034cd423c47f792d8` :
  `122744806154` et `122744805640` en `failure`, mais **`runner_id=0`, `runner_name=""`, `steps=[]`**. Début et fin séparés de quelques secondes seulement.
- L'API de téléchargement des logs des jobs retourne `404 BlobNotFound`. Aucune traceback, aucun pip install, aucune commande de test observés.
- CI de la refonte PR #1 au run `40098104186` avait, au contraire, **11 étapes et statut success** sur un ancien commit. Cela ne valide pas notre contribution.
- Conclusion prudente : **echec de lancement/attribution de runner avant steps**. Cause exacte NON CONFIRMEE : droits/quotas/facturation Actions, execution des workflows dans le dépôt privé, indisponibilité GitHub du moment, politiques de repo ou autre blocage Actions. Ne pas attribuer cet echec à nos tests sans log.

## Ce que la contribution corrige malgré le blocage

1. Import CLI de l'outil d'export corrigé pour l'invocation directe et comme module.
2. Script `python tools/jade_ci_preflight.py` : **sans installer Python-decouple/OpenAI**, relit tous les fichiers Python suivis (analyse AST), les profils TOML et le manifeste pyproject, et vérifie les motifs de secrets sans imprimer de valeur.
3. Tests synthétiques de l'export, du scanner et des profils ; workflow spécifique mis à jour avec préflight avant pip.
4. Sur 67 fichiers texte suivis **hors jade-modeling/** : analyse à distance selon les motifs actuels du scanner, **aucun motif déclenché** (cela ne valide ni l'historique Git, ni les ressources LFS, ni l'absence d'autres formats de secrets).
5. Contrôles Python locaux reproduits sur les modules principaux d'audit/export et profiles isolés : **9 tests OK**, dans un miroir manuel limité (Python3.13). Ce n'est **pas** `unittest discover -s tests` sur la PR réelle.

## Ordre recommandé de résolution par Codex ou le propriétaire

- Contrôler dans GitHub : onglet Actions, détail d'un run, annotations éventuelles, **Settings > Actions > Runners**, politique Actions, usage et limites du compte/organisation, facturation et éventuelle suspension. Un job sans runner ne peut pas exécuter une correction Python.
- Exécuter localement depuis un clone de la branche exact SHA, sous Python 3.11 :
  1. `python tools/jade_ci_preflight.py`
  2. `python -m pip install -e .` dans un venv
  3. `python -m unittest discover -s tests -v`
  4. `python main.py --preflight`, puis `printf '/exit\n' | python main.py` ou saisie console Windows.
- Une fois GitHub Actions de nouveau capable d'allouer un runner, relancer les deux workflows sur le **HEAD exact**. Consigner les traces et corriger tout echec reproductible dans un nouveau commit.
- Ne pas confondre CI technique et autorisation de rendre Jade public. Tous les bloqueurs de `04-RELEASE-GATES.json` restent actifs.

**Aucune action sur les secrets, la production, la visibilite du dépôt, le travail de Codex ni les fichiers artistiques n'a été entreprise.**
