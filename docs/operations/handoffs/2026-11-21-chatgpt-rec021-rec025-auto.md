# Exécution des recettes automatiques REC-021 et REC-025

- **Mission :** exécuter maintenant sur `develop` les recettes techniques de mémoire SQLite et de sauvegarde/restauration, sans accéder au microphone PC, Twitch, OBS ou aux données privées.
- **Auteur :** ChatGPT via modifications GitHub.
- **Branche et intégration :** `develop`, commit des tests [`955ca2e2551f0d6f159818cc2c12cd765c3c64ee`](https://github.com/goldaj/jade-vtuber/commit/955ca2e2551f0d6f159818cc2c12cd765c3c64ee), validation CI sur ce SHA. Documentation dans le commit contenant cette passation.
- **État des deux cartes :** `À faire` → **`À valider`**. L'exécution technique automatique est réelle, mais le chat ne représente pas la validation Codex et le propriétaire n'a pas encore explicitement validé le résultat. `Done` n'est donc pas attribué artificiellement.

## Preuves réelles de GitHub Actions

- [CI complète Linux + Windows](https://github.com/goldaj/jade-vtuber/actions/runs/44947197393) : **success**.
- **Ubuntu :** job `136977061126`, **612 tests**, résultat OK, **3 tests ignorés**, aucun échec. Les ignorés concernent libopus et FFmpeg Rubber Band natifs, pas la mémoire.
- **Windows :** job `136977061336`, **612 tests**, résultat OK, **2 tests ignorés**, aucun échec.
- **Cinq nouveaux tests :** tous affichés `ok` sur **les deux systèmes** dans `tests/test_jade_rec021_rec025_acceptance.py`. Ils s'ajoutent aux tests existants (curation autonome, identité, rétention, consentement, mémoire autobiographique, échanges intercanaux et export/import).
- **Scan de secrets** sur le commit des tests : résultat `success`.
- **Mode de test :** Python 3.11, `unittest discover -s tests -v`, bases SQLite fictives stockées en répertoires temporaires, aucun service externe ni API payante appelée par ces tests.

## REC-021 : mémoire SQLite, Core et autobiographie

| Contrôle | Preuve |
| --- | --- |
| Consentement / absence de mémoire sans identité inscrite | Nouvelle recette `test_rec021_consent_scope_core_and_restart` |
| Isolation comptes et salons, pas de Core autobiographique publique | Même recette, réouverture de la DB après écriture ; suites de confidentialité existantes |
| Reprise L1 des échanges des dernières 24 h sans plafond, purge brute L1 après 7 jours | `test_rec021_retention_and_unlimited_24h_recovery` |
| Conservation L2 pendant 365 jours, L3 sans expiration, autobiographie persistante | Même recette et tests `test_jade_memory_retention.py` / `test_jade_autobiographical_memory.py` |
| Oubli, suppression de l'identité, opt-out persistant et conservation des autres comptes | `test_rec021_erasure_optout_does_not_delete_other_account` |
| Curation autonome avec modèle simulé, refus après suppression / sans consentement | Suites de régression `test_jade_autobiographical_memory.py`, `test_jade_memory_erasure_race.py` et autres tests de mémoire |

**Limites :** aucun profil utilisateur réel, vraie mémoire privée ou appel de modèle payant. Il s'agit de la recette de conformité technique et non d'une observation sur le PC du propriétaire.

## REC-025 : sauvegarde/restauration/effacement

| Contrôle | Preuve |
| --- | --- |
| Snapshot cohérent de SQLite actif en mode WAL | `test_rec025_wal_backup_restore_and_scoped_erasure` |
| Manifeste SHA-256 et format du ZIP attendus | Même recette |
| Restauration dans une nouvelle DB sans altérer la source | Même recette |
| Effacement ciblé après restauration, autres utilisateurs et Core du propriétaire préservés | Même recette |
| Archive altérée rejetée, fichier de destination existant protégé | `test_rec025_rejects_tampering_and_existing_destinations` |

**Limites importantes :** export ZIP SQLite **non chiffré** par conception et **aucune inspection réelle des journaux, anciennes archives ou copies privées**. Une archive créée **avant** l'effacement d'un utilisateur garde un instantané antérieur ; la suppression de la base active ne purge pas automatiquement ses anciens ZIP. Une politique de conservation, sécurité et effacement des sauvegardes réelles reste à valider. Ne jamais stocker ces archives dans le dépôt public.

## Passe de contrôle distincte

Les cinq tests ont été relus à l'aune des critères des deux cartes, des API `MemoryStore` et `memory_transfer`, et de la DoD avant exécution. Les journaux CI Linux et Windows confirment leur réussite. **Cette vérification de ChatGPT ne vaut pas approbation Codex**. Une validation explicite du propriétaire ou de Codex, et la gestion des limites documentées, sont encore requises avant clôture officielle.

**Aucun secret, base privée, capture ou transcription réelle n'a été transmis ou modifié.** Les cartes en suspension micro/Twitch/OBS et `main` restent inchangées.
