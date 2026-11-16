# Passation active à Codex — clôture du rangement Jade (16 novembre 2026)

**Mission :** finir les seules vérifications et opérations non réalisables depuis la revue GitHub, sans rouvrir le périmètre produit.
**Agent repreneur :** Codex (développement senior / DevOps / QA / Live2D suivant chaque tâche).
**Référence de départ contrôlée :** `develop` à `b10fe709ad5777c54ea83aad915302c745789c6f` (revalider le SHA au démarrage).
**Livré :** [PR #22](https://github.com/goldaj/jade-vtuber/pull/22), puis [PR #24](https://github.com/goldaj/jade-vtuber/pull/24). Les deux sont fusionnées dans `develop`. **`main` n'a pas été modifiée.**
**Coordination :** lire [`AGENTS.md`](../../../AGENTS.md), [contrat inter-agents](../AGENT_COORDINATION.md), consigner le résultat dans cette fiche ou une nouvelle fiche de mission référencée ici, et utiliser la PR correspondante pour la discussion. Ne pas ressusciter les vieux journaux de `docs/history/` comme consignes.

## Décisions déjà prises : à respecter

- **Le dépôt `goldaj/jade-vtuber` est volontairement PUBLIC et doit rester PUBLIC.** La visibilité n'est **pas** une anomalie, un problème à corriger ni un sujet à arbitrer de nouveau. **Ne pas rendre le dépôt privé**, ne pas proposer sa privatisation, ni modifier ses paramètres de visibilité.
- **Seule la Démo Express est conservée** sous `demo/express/`. Le véritable renderer r20 a été déplacé dans `src/jade_runtime/avatar_renderer.py`, appelé par `src/jade_runtime/avatar.py`. Ne pas réintroduire `demo/reelle/` ou `demo/windows/`.
- Les 83 déplacements documentaires sont achevés ; l'historique reste dans `docs/history/`. Les **passations ACTIVES** vont dans `docs/operations/handoffs/`. Un changement technique exige une entrée dans `docs/operations/CHANGELOG.md`, **pas** la réécriture systématique de neuf manuels.
- Les **sources et checkpoints du modèle r21**, le **runtime r20** et les assets LFS sont préservés. Ne pas supprimer un CMO3, PSD, KRA, script ou rapport seulement parce que son nom semble ancien. Aucune fonctionnalité du [catalogue des améliorations](../../ameliorations/README.md) ne doit être développée dans cette mission : le propriétaire veut d'abord tester Jade.
- Ne pas toucher à `main`, au VPS Hyperliquid, aux secrets/mémoires réels, ni aux changements locaux non committés d'autres agents. Pas de suppression de branche sans revalidation de la pointe et de l'absence de travail restant.

## Déjà fait et vérifié : ne pas recommencer sans raison

| Sujet | État et preuve |
| --- | --- |
| Nettoyage du dépôt | **LIVRÉ** sur `develop`, 503 fichiers suivis ; uniquement trois fichiers dans `demo/express/`, aucun `demo/reelle/`, `demo/windows/` ou `.idea/` |
| Live2D de production | **CODE PRÉSERVÉ** : `src/jade_runtime/avatar_renderer.py` et son appel ; tests du protocole conservés dans `tests/test_jade_avatar_controls.py`. Cela ne prouve pas le rendu graphique sur le PC |
| Documentation / agents | **LIVRÉ** : `AGENTS.md`, `docs/operations/`, `docs/history/`, journal technique unique et contrôle des liens dans `scripts/check_docs.py` |
| GitHub Actions | **RÉUSSI** sur `b10fe709` : `Jade rebuild offline tests` (Ubuntu + Windows) et `Jade secret scan`. Aucun appel réel aux fournisseurs ni essai GPU n'est impliqué |
| Modeling | **REVUE UNIQUEMENT** : 221 blobs Git sans SHA identique dans l'arbre initial ; 222 fichiers sous `jade-modeling/` après l'ajout du rapport ; aucune suppression artistique |
| Paramètres GitHub | **OBSERVÉ** : dépôt public sur décision du propriétaire ; `main` et `develop` non protégées à la date du contrôle. Ces deux faits sont indépendants |

## À faire par Codex, classé par dépendance

### 1. Réception sur le vrai PC Windows (QA système / développeur desktop) — À FAIRE SUR LE POSTE

**Pourquoi ce n'était pas fait :** accès GitHub/CI seulement, pas au GPU, à Cubism, aux comptes/services, aux périphériques audio et aux fichiers privés du PC.

- [ ] Avant de synchroniser : inspecter `git status --short --branch`, les processus Jade éventuels, l'installation du launcher sur D: et tout travail non committé d'un autre agent. **Ne rien écraser**, ni réinitialiser le dépôt.
- [ ] Synchroniser `develop` en fast-forward uniquement ; installer/récupérer Git LFS. Contrôler `git lfs fsck` et `poetry run python jade-modeling/verify_assets.py` après `git lfs pull`, en distinguant les fichiers absents d'une incompatibilité du rig.
- [ ] Vérifier le lancement réel du renderer r20 : fenêtre, Idle, bouche synchronisée à l'audio, changements d'expression, fermeture et retour au neutre, sans que la disparition du renderer coupe le dialogue.
- [ ] Vérifier `Installer-Demo-Express.cmd` et `Lancer-Demo-Express.cmd` **dans une vraie session graphique Windows**, raccourci inclus ; confirmer que la simulation reste sans IA ni clé API.
- [ ] Réinstaller le launcher utilisateur depuis `Installer-Launcher-Jade.cmd` si son code installé est ancien ; vérifier `--preflight --all-channels` sans imprimer de secrets. Ne lancer les services externes potentiellement facturés qu'avec le feu vert du propriétaire.
- [ ] Pour la PWA Android : vérifier la version réelle des SDK JavaScript propriétaires, la compatibilité `.moc3`/Cubism, l'accès privé Tailscale Serve (sans Funnel), l'authentification et, si autorisé, voix/écrit/animation sur Wi-Fi et 4G/5G. Ne pas importer les SDK propriétaires dans Git.
- [ ] Si des services réels sont utilisés : contrôler Discord écrit/vocal, Twitch, micro local, sorties, isolement privé/public, coexistence des canaux, reprise de connexion et arrêt propre. Documenter les vrais résultats séparément des tests simulés.

**Critère de clôture :** matrice « composant / version et configuration non sensible / vérification effectuée / résultat / erreur reproductible / correctif » jointe à une passation ou PR. Une limitation liée au matériel ou aux accès doit rester explicitement notée, pas déclarée « OK » par inférence.
**Référence :** [installation](../../handbook/INSTALLATION.md), [guide démo](../../handbook/DEMO.md), [guide technique](../../handbook/TECHNICAL.md).

### 2. Redondances *sémantiques* du modeling (expert Live2D/Cubism + gestion de configuration) — À ANALYSER, PAS À PURGER AUTOMATIQUEMENT

**Pourquoi ce n'était pas fait :** empreintes Git uniques ne signifient pas absence d'images quasi identiques, de générateurs obsolètes ou de jalons inutilisés ; outils graphiques et fichiers LFS complets indisponibles dans la revue à distance.

- [ ] Sur les assets téléchargés, comparer visuellement et fonctionnellement les candidats de `jade-modeling/assets/live2d/r21_professional_art/`, les versions CMO3 v30/v31/r02 et les variantes exportées **avec l'historique et le manifeste**.
- [ ] Pour les scripts spécialisés de `jade-modeling/tools/` et les `reports/`, déterminer qui les importe/invoque, ce qu'ils produisent et s'ils servent à reconstruire la version source actuelle. Distinguer source essentielle, généré reproductible et archive obsolète.
- [ ] Produire un tableau **chemin / rôle / dépendances entrantes / recommandation garder-archiver-supprimer / preuve / risque de perte**, en protégeant `runtime-installed/`, `ASSET_MANIFEST.json`, les références Cubism et les sources natives.
- [ ] Ne supprimer/renommer qu'après preuve de non-utilisation et conservation récupérable (historique/backup vérifié) ; en cas de doute, **conserver** et proposer un candidat au propriétaire, pas une suppression silencieuse.

**Critère :** aucune ressource utilisée pour compiler, éditer ou lancer Jade perdue ; mêmes références valides avant/après ; vérification `verify_assets.py` et recette visuelle si des assets changent.
**Référence :** [revue de conservation](../../../jade-modeling/reports/RETENTION_REVIEW_20261116.md), [guide du modèle](../../../jade-modeling/MODEL_GUIDE.md).

### 3. Nettoyage des branches déjà fusionnées (Git / DevOps) — À FAIRE AVEC PERMISSIONS ADAPTÉES

**Pourquoi ce n'était pas fait :** le connecteur GitHub de la revue ne pouvait pas supprimer les références Git.

- [ ] `git fetch --prune`, inventorier les PR ouvertes et les pointes **actuelles**. En particulier, examiner `chore/develop-repository-cleanup-20261116` (PR #22) et `docs/final-post-cleanup-review-20261116` (PR #24), encore visibles après fusion.
- [ ] Attention : les PR #22 et #24 ont été fusionnées en **squash** ; un test `merge-base --is-ancestor` peut échouer alors que le contenu a bien été intégré. Vérifier aussi PR fusionnée, diff résiduel et nouveaux commits éventuels avant de proposer de supprimer les branches.
- [ ] Revalider **une par une** les anciennes branches candidates de [`BRANCH_MAINTENANCE.md`](../../handbook/BRANCH_MAINTENANCE.md) ; inclure les branches techniques nouvelles seulement après comparaison, sans suppression par motif de nom.
- [ ] **Ne pas supprimer** une branche divergente, une PR ouverte, une branche utilisée par un autre agent, `main` ou `develop`. Consigner « supprimée / conservée / bloquée » avec SHA, motif et preuve.

**Critère :** réduction des références réellement sans utilité, sans perte d'un commit unique ni de travail Codex/Terra.

### 4. Hygiène technique et droits dans un dépôt PUBLIC (sécurité / conformité) — VÉRIFICATIONS SANS CHANGER LA VISIBILITÉ

**Décision ferme : dépôt public maintenu.** Il ne faut pas confondre vérification de provenance et proposition de privatisation.

- [ ] Si le périmètre de contrôle le permet, vérifier que fichiers historiques et objets LFS ne contiennent pas de credentials ou de données personnelles accidentellement committés. **Ne jamais afficher les valeurs sensibles dans les logs, tickets, commits ou PR**. Signaler une exposition avérée au propriétaire pour révocation/rotation hors Git.
- [ ] Examiner provenance et autorisations de redistribution des illustrations, modèles, SDK et composants tiers déjà présents dans ce dépôt public. Faire un inventaire d'attribution et des mentions éventuellement dues. Ne pas retirer massivement des ressources sans accord du propriétaire.
- [ ] Constater que `main` et `develop` ne sont pas protégées. **Option de gouvernance à soumettre**, pas une anomalie à corriger d'autorité : éventuellement règles de PR/CI, seulement après décision explicite du propriétaire. **Aucun rapport avec la visibilité publique**, qui ne doit pas changer.

**Critère :** rapport factuel sur les risques *observés*, les preuves, les décisions demandées et les corrections éventuellement autorisées. Un scan GitHub vert ne prouve pas l'absence de secrets dans tous les objets de l'historique.
**Référence :** [statut public confirmé](../../publication/CURRENT_PUBLIC_STATUS.md) et [provenance](../../../jade-modeling/PROVENANCE.md).

### 5. Contrôle final de cohérence documentaire / livraison (tech writer + PO) — À CLÔTURER

- [ ] Après toute opération ci-dessus, contrôler les éventuels liens **textuels** vers `docs/gpt6-jade/`, `docs/conversations/`, `demo/reelle/` ou `demo/windows/` ; les références **historiques explicites** sont admises si elles sont étiquetées comme telles. Le contrôle automatisé des liens Markdown des guides actifs a déjà réussi.
- [ ] Maintenir `AGENTS.md` comme point d'entrée, cette fiche comme relais de mission, `docs/handbook/BRANCH_STATE.md` comme état fonctionnel du code et `docs/operations/CHANGELOG.md` comme journal technique. Modifier uniquement ce qui est impacté.
- [ ] Mettre à jour les cases de cette fiche au fur et à mesure, avec résultats réellement observés et SHA/PR, puis marquer la mission clôturée lorsque toutes les actions applicables sont résolues ou explicitement différées par le propriétaire.

## Hors périmètre de cette passation

Les idées de faible latence, routage par canal exclusif, préchargement mémoire, avatar conditionnel, modèle Realtime sans Luna et motions corporelles r21 relèvent du [catalogue d'améliorations](../../ameliorations/README.md) et d'autres chantiers. **Ne pas les développer au prétexte de terminer le rangement.** Ne pas créer de nouvelle branche sur `main` ni déployer le bot depuis cette mission.

## Résultat attendu de Codex

Un bref compte rendu final : statut pour chacune des cinq rubriques, commits/PR, commandes et tests réellement exécutés, tout blocage propre au PC ou aux autorisations, et les éventuelles décisions à demander au propriétaire. Clore ou archiver cette fiche après l'avoir reliée au suivi approprié.
