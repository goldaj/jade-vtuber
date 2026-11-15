# État de la branche docs/jade-persistent-memory-identity-20261115

**Pointe contrôlée avant changement documentaire :** `0083e34461f31cb602453db1f62beb7562ca70ca`. **Divergente de develop**, donc aucune suppression automatique.

Branche de **cadrage mémoire persistante et identités** : ses 5 commits encore uniques face à develop portent principalement sur les documents PLAN-MEMOIRE-PERSISTANTE-IDENTITES-CORE-20261115.md, le journal et les instructions. **Aucune implémentation SQLite/Core Memories dans cette branche.** Le code vocal/intention/log est présent via les travaux antérieurs. Le plan n'est pas le produit. Avant suppression, comparer son contenu de cadrage avec les plans de develop et préserver toute décision non reprise.

## Éléments présents dans le code de cette branche

- Python 3.11 et Poetry, `main.py` avec `--preflight`, `--live`, `--voice`, `--mic`, `--twitch`, `--discord`, `--discord-voice`, `--vts`, `--http`, `--avatar`.
- Connecteurs opt-in Discord/Twitch, API texte HTTP locale, micro/STT, voix/TTS OpenAI, avatar autonome r20, VTube Studio optionnel.
- File de conversation bornée FIFO, sessions en RAM, modules d'intention vocale `intent_engine.py`, de pitch `pitch_shift.py` et de journalisation `turn_logging.py`.
- Démo Express Windows intégrée **sur cette branche de documentation uniquement**, sans appel IA, et démo console via `DemoChat`.

## Éléments absents

- Aucun `--all-channels` ni `TurnArbiter`, aucun launcher graphique de produit unifié.
- Pas de `mobile_gateway.py` / PWA Android Tailscale Serve ; pas de mémoire SQLite `memory_store.py`.
- L'infrastructure privée du PC du propriétaire et le SDK Web Live2D ne sont pas installés par le dépôt.
- Aucun test physique de cette branche par cette opération de documentation.

## Revue avant éventuelle suppression

Comparer les commits propres de cette branche à develop, préserver les apports utiles, puis recontrôler `git merge-base --is-ancestor` ou documenter une équivalence de contenu. Ne pas supprimer un travail divergent par simple ressemblance de nom. Voir [BRANCH_MAINTENANCE.md](BRANCH_MAINTENANCE.md).
