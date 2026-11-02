# Jade — état de reprise Codex de l'ensemble du modèle 2D

**Protocole approuvé par le propriétaire le 28 octobre 2026.** Périmètre : dessin, découpage, préparation des calques/assets, rig, physique, animations, expressions, export et validation VTube Studio. **Pas** la refonte du bot Python. Cette validation concerne la **méthode de collaboration**, pas le plan technique futur ni l'état graphique actuel.

## Situation de décision
- **État courant : `planning_required`**. La stratégie Astra → Terra → Sol/Astra → revue Astra est approuvée.
- **Plan directeur 2D : non produit / non validé à ce jour**. Le fichier à produire est `jade-modeling/MODEL2D_MASTER_PLAN.md`. Ne pas prétendre qu'il existe.
- **Prochaine étape :** analyse des sources existantes et rédaction sous **GPT-6 Astra** du plan directeur couvrant **toute** la chaîne de production du modèle 2D jusqu'à une validation réelle dans VTube Studio. Demander ensuite l'approbation du plan technique avant l'exécution structurante.
- **Modèle recommandé pour cette étape : GPT-6 Astra** (raisonnement élevé si disponible). L'utilisateur sélectionne le modèle **manuellement**. Modèle actif réel : **inconnu du dépôt**.
- **Après validation du plan :** proposer **GPT-6.1 Terra** pour l'exécution ordinaire ; **GPT-6.1 Sol** pour les blocages intermédiaires ; **Astra** pour les problèmes complexes et la fin des grandes phases.
- **Résultat de la présente intervention :** documentation et coordination uniquement. **Aucun dessin, rig, animation ni export modifié ou validé.**

## Données existantes à réévaluer, sans les écraser
- Checkpoint connu r21 v30 : `jade-modeling/assets/live2d/r21_professional_art/working_v005/jade_cubism_v005_r21_back_hair_restore_v30.cmo3`.
- Candidat `jade_cubism_v005_r21_v30.TEST_hair_leaves_r02.cmo3` : 9 mèches/feuilles indépendantes, 45 poses ; validation native restante.
- `CONTINUATION.md` mentionne contrôle frange/raccords, neutre et HeadZ ±30 puis enregistrement éventuel v31 **seulement si vérifié**.
- Package animé r20 : recours archivé, non preuve de finalisation de r21.
- Sources KRA/PSD non totalement synchronisées avec le CMO3 r21 ; tout réimport doit être justifié et protégé.
- Coordination avec branches/PR de refonte Python, Git LFS et conservation d'assets impérative.

## À enregistrer après chaque unité / session
- État : `planning_required`, `plan_review_required`, `ready_for_execution`, `in_progress`, `blocked`, `phase_review_required`, `completed_verified`.
- Grande phase et unité du plan / dépendances.
- Modèle réellement confirmé par l'utilisateur, modèle recommandé pour la prochaine action, raison du relais.
- Résultat et preuves : fichiers, branche, commit, tests ciblés ou observations visuelles **réellement réalisés**.
- Inconnues restantes, notamment validations natives inaccessibles.
- Tentatives infructueuses et diagnostic ; limites environnementales.
- **Une seule prochaine action claire et exécutable**, avec prérequis.
- Revues Astra de grande phase et décisions humaines explicitement confirmées.

Consulter `jade-modeling/MODEL2D_CODEX_PLAYBOOK.md` et les consignes du `AGENTS.md` racine à chaque session de création 2D. Ne pas créer de tâche récurrente ni supposer une exécution autonome entre les sessions.