# Instructions historiques — remplacées

Les instructions ci-dessous sont conservées pour contexte historique ; les instructions applicables sont dans le fichier AGENTS.md à la racine.

## Reprise migration applicative — 2 novembre 2026

Avant toute modification, lire [l’index de conversation](docs/conversations/INDEX.md),
puis [le dossier de migration courant](docs/migration/2026-11-02/README.md).
La revue Astra est terminée : lire ses [précisions d’exécution](docs/migration/2026-11-02/06-ASTRA-REVIEW.md)
avant la reprise Terra. Elles prévalent sur les passages correspondants du plan initial.
Le propriétaire a confirmé dans ce chat qu’il n’existe **aucune production active**.
`develop` est la cible Git proposée pour l’intégration ; `master` reste historique.
La revue Astra est achevée et le propriétaire a demandé à Terra d’exécuter
les corrections et l’intégration selon le plan amendé.
Le visuel et l’animation 2D sont temporairement hors périmètre. Ne pas réactiver
ce chantier à partir d’un ancien document de continuation.

## Coordination des documents Codex 2D — 29 octobre 2026

La branche Codex `develop` apporte `jade-modeling/MODEL2D_CODEX_PLAYBOOK.md`, `jade-modeling/MODEL2D_CODEX_STATE.md` et les anciens renvois `RIG_CODEX_*`. Consulter ces sources avant tout travail sur Jade 2D. **En cas de divergence, la politique propriétaire la plus récente du 29/10 prime : Tera 6.1 exécute par défaut ; il sollicite lui-même un changement manuel vers Astra uniquement en cas de doute motivé ; la revue Astra ultérieure est laissée à la décision du propriétaire.** Les anciennes prescriptions de plan Astra obligatoire ne sont pas activées par cette consolidation. Le texte antérieur de Codex est archivé sous `docs/merge-archive/CODEX_DEVELOP_AGENTS.md` sans perte d'information.

# AGENTS.md — Jade, branche de refonte GPT-6

> Codex : travail isolé en cours sur `codex/chat-gpt6-jade-rebuild`.
> Sur `develop`, lire `docs/CODEX_PARALLEL_GPT6.md` pour la coordination.
> **Ne pas merger ni déployer sans revue du propriétaire.**

## Politique propriétaire de répartition des modèles — 29 octobre 2026

**Tera 6.1 est l'exécutant par défaut pour Jade**, en particulier pour tous les
travaux nécessitant un ordinateur : dessin, modèle 2D/Live2D, rigging, animation,
physique, retouches, exports Cubism, intégration VTube Studio et vérifications
sur le poste. Ne pas réserver par habitude ces travaux à Astra.

**Escalade exceptionnelle :** si Tera rencontre un doute réel nécessitant une
analyse supérieure, il **termine d'abord la sous-tâche en cours dans les
limites de sécurité**, sauvegarde et documente le résultat et ses incertitudes,
puis **demande explicitement au propriétaire de basculer manuellement sur
Astra**. Tera doit lui-même formuler cette demande motivée ; aucune bascule
implicite ou automatique. Si la sous-tâche ne peut pas être achevée sans risque
irréversible, s'arrêter au dernier état sûr et expliquer le blocage.

**Pas de double revue automatique :** le propriétaire décide seul quand il
fait contrôler par Astra les travaux de Tera. Cette revue éventuelle est
**hors du processus de Tera** : ne pas la déclencher, la planifier, ni l'exiger
après chaque tâche. Les tests techniques, sauvegardes, permissions et revues
humaines de sécurité restent obligatoires selon le type de modification.

Contrat complet : `docs/gpt6-jade/TERA-ASTRA-WORKFLOW.md`.

## Avant toute intervention
- Lire `README.md`, `docs/CHATGPT_PROJECT_HISTORY.md`, `docs/gpt6-jade/DECISIONS.md`,
  `docs/gpt6-jade/HANDOFF.md`, `docs/gpt6-jade/TASKS.md` et `PRIVATE_CONFIGURATION.md`.
- Code runtime : Python. STT et TTS = **OpenAI exclusivement**, modèles configurables
  favorisant une faible latence. Le dialogue LLM est interchangeable.
- Ne pas activer automatiquement Twitch, Discord, microphone ou VTube Studio.
  Ne pas appeler de service payant en test. Ne pas journaliser clés ou transcriptions.

## Sources artistiques à préserver
- Lire `jade-modeling/MODEL_GUIDE.md` et `jade-modeling/CONTINUATION.md`.
- Garder les ressources LFS, natif r21 v30, candidat r02 et runtime r20 intacts.
- `python jade-modeling/verify_assets.py` seulement après `git lfs pull`.
- Pas de modification des coffres privés, historiques ou secrets.

## Validation et mémoire
- `python -m unittest discover -s tests -v`, `python -m compileall -q src main.py`.
- Après chaque sous-lot : mettre `docs/gpt6-jade/TASKS.md` à jour avec les
  *résultats réellement observés* et la confiance. Actualiser `CONVERSATIONS.md`
  uniquement avec des dialogues accessibles ; citer les heures si attestées.
- Ne jamais annoncer de réussite de connexion Twitch/Discord/OpenAI/STT/TTS
  en se basant uniquement sur un mock CI.
