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

## Branches temporaires de cette mise à jour documentaire

Deux branches de travail documentaires ont aussi été **fusionnées** et leurs pointes sont désormais des ancêtres vérifiés de leurs cibles respectives :

- `docs/handbook-demo-express-main-20261115` : ancêtre de `main`, via PR #16.
- `docs/handbook-demo-express-develop-20261115` : ancêtre de `develop`, via PR #17.

Elles sont candidates à la même suppression contrôlée par Codex après revalidation des pointes et de l'absence de nouveau travail. Ne pas confondre leur suppression avec celle de `main` ou `develop` elles-mêmes. Cette note ne vaut pas suppression effective.

## Nouvelle branche active de synchronisation 2D (15/11/2026)

`feat/live2d-intent-expression-sync-20261115` a été **fusionnée dans `develop` par la PR #18 le 15 novembre 2026**. Comparaison d'ascendance revérifiée le 16 novembre (aucun commit propre restant). Elle est candidate à un nettoyage *après* contrôle de sa pointe et de l'absence de PR ou travail nouveau. Elle ne modifie pas `main`. La passation Codex pour les 14 motions 2D encore absentes est dans [LIVE2D-INTENT-ANIMATION-HANDOFF-20261115.md](../gpt6-jade/LIVE2D-INTENT-ANIMATION-HANDOFF-20261115.md).

## Note sur les commits du 2026-11-15
La mise à jour Low/320, personnalité validée, conservation opt-in sans résumé et politiques de participation est intégrée directement dans `develop` à la demande du propriétaire. Elle ne crée pas de branche supplémentaire à supprimer, ne fusionne pas `main` et ne modifie pas les anciennes branches divergentes. La planification de deux réactions par intention (14 futurs emplacements) **n'implique pas** l'existence des assets. Voir [passation dialogue](../gpt6-jade/DIALOGUE-LOW320-HISTORIQUE-PARTICIPATION-20261115.md).

## Branche corrective DevOps (15/11/2026)

**Audit de référence** : [revue DevOps develop du 15 novembre 2026](../gpt6-jade/AUDIT-DEVOPS-DEVELOP-20261115.md). La branche `fix/develop-devops-audit-20261115` part de `develop` et contient des corrections CI, mémoire ZIP et documentation. La PR #19 a été **fusionnée dans `develop` le 15 novembre 2026**. La branche pourra être supprimée **uniquement** après vérification d'ascendance, d'absence de nouveaux commits et de PR encore actives. Aucun changement de `main` n'est demandé.

## Contrôle P0 CI du 16 novembre 2026 (develop)

- Politique de réponse conservée : **100 % en solo vérifié, 30 % en groupe** ; sollicitation explicite prioritaire. Les suivis contextuels en groupe restent échantillonnés et ne garantissent pas une réponse.
- Tests de transport Discord vocal : échantillonnage neutralisé **dans les doubles de test seulement** pour vérifier indépendamment déplacement de canal, interruption et récupération. La présence des participants est une information en lecture seule permettant de distinguer solo/groupe, jamais une autorisation d'écoute.
- Tests Discord écrit : salons à plusieurs participants simulés explicitement pour vérifier le taux et les limites de réponses, sans supprimer la réponse automatique en salon solo.
- Twitch : le test de non-empilement des réponses initialise le participant que l'adaptateur IRC observe normalement. Aucun changement de comportement de production dans ce lot.
- Vérification GitHub Actions Windows/Ubuntu, export de publication, scripts PowerShell et scan de secrets indispensable avant toute affirmation de CI verte. Aucun test vocal matériel ni appel OpenAI réalisé par cette revue.

- Correctif Windows du test IPC Live2D : la simulation valide toujours les deux trames d'expression et de bouche, puis termine par une coupure de pipe contrôlée. L'attente auparavant non bornée du faux moteur était responsable d'annulations Windows au délai de huit minutes ; aucun runtime ni test réel de Live2D n'est remplacé.

## Réconciliation historique et maintenance du 16 novembre 2026

- `main` est désormais ancêtre de `develop` depuis `dda14d1`, sans transfert de code vers `main` ni écrasement des guides propres à `develop`.
- PR #18 (intentions 2D), #19 (DevOps + SQLite v3) et #20 (tests de politiques et CI Windows) : **fusionnées**.
- `fix/p0-develop-ci-participation-20261116` est également candidate au nettoyage après revalidation de l'ascendance, mais n'a pas été supprimée ici.
- Ne supprimer aucune branche locale Terra/Codex et ne pas remplacer leurs fichiers non commités. Les actions sur le clone Windows nécessitent une revue locale distincte.

Voir [l'audit code/configuration/documentation](../gpt6-jade/RECONCILIATION-CODE-CONFIG-DOCS-20261116.md).


### Correctifs en PR : Discord PCM / identité mémoire / PWA

La branche de PR `fix/discord-pcm-memory-mobile-20261116` découple le streaming Discord du lecteur `ffplay` local et propose une liaison mémoire Goldaj ↔ Discord/Twitch via un code temporaire créé dans la PWA privée. **Source unique des détails, risques, prérequis et essais PC restant à faire :** [note de correctifs](PR-PCM-MEMOIRE-MOBILE-20261116.md). Ce document décrit une PR **non fusionnée** ; ne pas traiter son contenu comme présent dans `develop` avant le merge.
