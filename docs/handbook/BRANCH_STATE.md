# État de la branche test/intent-all-channels-20261115

Pointe examinée **3b59e86edc2570196b00e418a361bf5fb852d58f**, avant ce commit documentaire. **Diverge de develop de deux commits propres** lors du contrôle.

Branche expérimentale de tests de journalisation et d'intentions, avec deux commits propres face à develop lors du contrôle. Malgré son nom, main.py dans CETTE branche n'a pas --all-channels. Les tests supplémentaires doivent être comparés aux tests de develop avant toute suppression. Le tronc possède intent_engine.py, pitch_shift.py et turn_logging.py, sans PWA, launcher unifié ni SQLite.

## Code effectivement présent

Python 3.11/Poetry, connecteurs activables individuellement : `--live`, `--discord`, `--discord-voice`, `--twitch`, `--mic`, `--voice`, `--http`, `--vts`, `--avatar`, `--preflight`. File FIFO bornée, sessions volatiles, r20 Live2D autonome, voix OpenAI. Modules d'intentions et de pitch DSP, journalisation et **tests spécifiques de journalisation**. Démo Express Windows autonome ajoutée sans modification du runtime.

## Fonctionnalités absentes malgré le nom de branche

**Aucun `--all-channels`**, aucun `TurnArbiter`, aucune PWA Android, aucun launcher Windows unifié, aucune base de mémoire SQLite/Core. Aucun essai matériel réalisé pendant la mise à jour documentaire.

## Revue de fin de vie

Comparer les deux commits et leurs 61 lignes de tests uniques à la suite de develop ; ne demander une suppression qu'après reprise ou rejet motivé de cet apport. Revalider les SHA/PR, ne pas supprimer cette branche uniquement parce que son nom rappelle une fonctionnalité aujourd'hui intégrée ailleurs.
