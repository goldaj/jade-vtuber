# AGENTS.md — Jade

> **Coordination en cours** : avant toute modification par Codex, lire
> [`docs/CODEX_PARALLEL_GPT6.md`](docs/CODEX_PARALLEL_GPT6.md) : GPT-6 Chat
> développe sur `codex/chat-gpt6-jade-rebuild` (branche séparée).
> Aucun merge ou déploiement implicite.

## Protocole validé de production du modèle 2D de Jade — 28 octobre 2026

**OBLIGATOIRE dès la prochaine session de travail consacrée au personnage 2D** (dessin, calques/assets, rig, physique, animations, expressions, export et tests VTube Studio). Le propriétaire a expressément approuvé le protocole général et son extension à l'ensemble du modèle 2D. Ce n'est **pas** l'approbation d'un plan technique encore inexistant.

1. Lire [`jade-modeling/MODEL2D_CODEX_PLAYBOOK.md`](jade-modeling/MODEL2D_CODEX_PLAYBOOK.md) pour les rôles Astra/Terra/Sol, l'organisation et les changements manuels de modèle.
2. Lire [`jade-modeling/MODEL2D_CODEX_STATE.md`](jade-modeling/MODEL2D_CODEX_STATE.md) pour la prochaine action, le modèle recommandé, les preuves et la reprise.
3. Lire `jade-modeling/MODEL2D_MASTER_PLAN.md` **seulement s'il existe et a été validé**. Sinon demander le passage manuel à **GPT-6 Astra** pour produire le plan détaillé de toute la chaîne 2D ; puis faire valider ce plan avant exécution.
4. Codex **ne change jamais de modèle automatiquement**. Au besoin, s'arrêter et demander à l'utilisateur le passage à Astra (plan/complexité/revue de phase), Terra (exécution ordinaire), ou Sol (blocage intermédiaire), en précisant le niveau de raisonnement, la raison, la prochaine action et l'état sauvegardé.
5. Conserver les checkpoints natifs, les sources et les preuves ; tests ciblés durant les petites unités et revue Astra aux jalons importants. Les validations visuelles natives ne peuvent pas être inventées.
6. Le protocole **ne s'applique pas à la refonte Python du bot**, aux services de Jade ni aux autres branches en cours, sauf outils strictement nécessaires à la production/validation du personnage 2D. Ne pas fusionner, écraser ou déployer implicitement.

Les fichiers `jade-modeling/RIG_CODEX_PLAYBOOK.md` et `jade-modeling/RIG_CODEX_STATE.md` sont d'anciennes entrées, conservées comme renvois : **utiliser exclusivement les fichiers MODEL2D pour l'organisation actuelle**.

## Avant toute intervention
- Lire `README.md`, puis **`docs/CHATGPT_PROJECT_HISTORY.md`** pour les décisions de conception et les limites documentaires. Consulter ensuite les documents spécialisés cités par le README.
- Mission : Personnage VTuber IA, bot Python 3.11 (Twitch/Discord/LLM/audio) et art/rig Live2D VTube Studio. État r21, jalon natif v30, runtime animé r20, fichiers volumineux LFS.
- Invariants : Lire jade-modeling/MODEL_GUIDE.md, manifestes d'assets et PRIVATE_CONFIGURATION.md ; ne pas toucher aux éléments de coffre privé ou à l'historique sensible ; pas d'appels payants non requis.

## Exécution
- `poetry run python -m unittest discover -s tests -v` ; `python jade-modeling/verify_assets.py` après récupération Git LFS.
- Préserver le travail préexistant, les versions anciennes et les fichiers non concernés. Valider uniquement ce qui peut être vérifié dans l'environnement disponible.

## Continuité du contexte
- Après toute modification de projet, consulter et enrichir `docs/CHATGPT_PROJECT_HISTORY.md` avec les échanges fournis, les décisions et le résultat de la validation.
- Distinguer `Utilisateur (verbatim)`, `Assistant (verbatim)` et `Résumé reconstruit (non verbatim)`. Donner date et heure uniquement si attestées, sinon noter qu'elles manquent.
- Ne pas inventer d'échanges ou de tests. Si une transcription n'est pas accessible, demander son export plutôt que supposer son contenu.
- Le dépôt peut être public : expurger secrets, données personnelles et contenus ne relevant pas du projet. Ne pas écraser les éléments historiques.
