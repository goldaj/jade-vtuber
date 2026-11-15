# Plan de nettoyage des branches Git pour Codex

**Demande du propriétaire du 15 novembre 2026 :** supprimer les vieilles branches dont le travail est déjà intégré dans `develop`. Ne pas toucher à `main` ni à `develop`. Le connecteur GitHub accessible à l'assistant dans cette session **ne dispose pas de suppression de branche** ; ce fichier sert de passation pour une session Codex possédant la permission de le faire. Ce n'est pas une confirmation de suppression.

## Branches dont la pointe était ancêtre de develop

Comparaison GitHub `compare/<branche>...develop` : statut `ahead`, `behind_by=0`, pointe de la branche = merge-base au contrôle effectué :

- `docs/codex-pc-mobile-onboarding-20261115`
- `feat/jade-autobiographical-memory-20261115`
- `feat/jade-discord-unified-conversations-20261115`
- `feat/jade-persistent-memory-core-20261115`
- `feat/jade-private-mobile-pwa-20261115`
- `feat/jade-windows-launcher-20261115`
- `fix/jade-unified-always-on-20261115`
- `review/jade-mobile-memory-integration-20261115`

**Candidats au nettoyage**, sous réserve de vérifier à nouveau les nouvelles pointes, l'absence de travail nouveau ou de PR ouvertes. Le document n'autorise pas une suppression aveugle : une branche peut avancer entre deux vérifications. Au moment de la suppression, Codex doit relire `git status`, `git fetch --prune`, comparer la pointe exacte et n'effacer qu'avec une ascendance confirmée.

### Procédure dans le clone local (Codex avec permission Git)

~~~bash
git fetch --prune origin
git branch -r --merged origin/develop
git merge-base --is-ancestor origin/feat/jade-private-mobile-pwa-20261115 origin/develop
# Si la commande précédente renvoie 0 ET qu'aucun travail récent/PR ouverte
# ne dépend encore de cette branche, demander confirmation puis :
git push origin --delete feat/jade-private-mobile-pwa-20261115
~~~

Répéter **individuellement** pour chaque branche, pas de suppression par motif de nom. Une alternative est la suppression dans l'interface GitHub après la même vérification. Garder trace du nom, de la pointe SHA contrôlée, de la date et du résultat. Une branche locale non publiée est hors périmètre : ne pas l'effacer.

## Trois branches divergentes : ne PAS supprimer sans revue

Au contrôle GitHub de ce jour, elles ne sont **pas** des ancêtres de develop, même si certaines fonctions ont été reprises ailleurs :

| Branche | Écart vs develop | Examen nécessaire |
| --- | --- | --- |
| `docs/jade-persistent-memory-identity-20261115` | 5 commits propres, 242 commits derrière | Vérifier les notes et l'inventaire mémoire conservés dans develop |
| `feat/turn-conversation-logs-20261115` | 10 commits propres, 244 derrière | Comparer l'implémentation `turn_logging`, les tests et les journaux |
| `test/intent-all-channels-20261115` | 2 commits propres, 243 derrière | Comparer les nouveaux tests d'intentions/journalisation, reprendre toute amélioration utile avant archivage |

Pour chacune, comparer les changements et vérifier les PR associées. Si les changements uniques sont réellement repris dans `develop` ou inutiles, documenter la décision et ne la supprimer qu'après autorisation/validation ; sinon maintenir cette branche et actualiser sa documentation à son propre code.

## Documentation des branches actives

Une branche encore utilisée doit posséder **ses propres** fichiers `docs/handbook/`, pas des liens qui prétendent que `main` et `develop` ont le même runtime. Après la suppression des branches intégrées, concentrer la maintenance sur `main`, `develop` et les branches divergentes encore utiles. Les PR de documentation elles-mêmes, une fois fusionnées, deviennent candidates au nettoyage après validation d'ascendance.
