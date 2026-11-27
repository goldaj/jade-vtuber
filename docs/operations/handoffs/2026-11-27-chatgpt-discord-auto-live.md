# Mission : Discord Live automatique et interrupteur global

- **Date :** 27 novembre 2026, Europe/Paris.
- **Demande :** suite explicite de la reprise de « Planifier le live mobile » : développer l'automatisme Discord 50/40 EUR maintenant, avec un seul paramètre code pour activer Discord avec sa bascule ou le désactiver complètement.
- **Suivi :** DEV-052 transférée en **REC-051, À valider**, sans doublon actif. Les critères mensuels précédents sont conservés et complétés par l'interrupteur unique. REC-044 à REC-050 et DEV-041 conservent leurs recettes/voix restantes.
- **Branche :** `fix/live-resume-audit-20261127`, depuis le correctif mobile `31efc136c14c4fd394e2baf9f6fa8904ecbf7f8e`. Intégration autorisée sur `develop`, aucun merge sur `main`, aucun travail concurrent effacé.
- **Coordination :** agent principal (raccord CLI/configuration, docs, intégration), sous-agent transport fournisseur, sous-agent collecte/politique, sous-agent adaptateur vocal/mémoire ; contre-revues croisées distinctes de la réalisation.

## Décisions et réalisation

**`src/jade_runtime/discord_config.py`, `DISCORD_ENABLED=True`** est l'unique interrupteur. `False` supprime Discord écrit et vocal avant les prérequis et la création des connecteurs ; `--all-channels` et les options individuelles ne le contournent pas. Les anciens flags privés sont ignorés. Le défaut True conserve l'usage Discord du lancement habituel et rend le moteur vocal automatique, sans activer un micro au simple démarrage.

`global_spend.py` lit les dépenses de toute l'organisation OpenAI et l'usage du compte Tavily, sans limiter le total à la voix. Mois Europe/Paris, change ECB daté, historique et qualité des sources persistés hors Git. `discord_live_policy.py` choisit 50 EUR pour des données monétaires complètes/fraîches avec borne explicite, 40 EUR pour les relevés estimés standard, et classique lorsque des données essentielles sont inconnues. Le seuil consommé déclenche un verrou mensuel durable. Ni quota inutilisé ni simple GET réussi ne deviennent une dépense ou une réconciliation fictive.

Avant ouverture, `reserve_live` engage atomiquement une garde ouverture/clôture/contrôle en SQLite ; `bind_live` l'adapte après réception de l'ID, `settle_live` n'en libère le solde qu'après terminal confirmé ou preuve de non-démarrage. Les engagements restent visibles entre instances, après redémarrage et changement de mois. La durée non observée est une exposition distincte, remplacée par l'usage final valide ; aucun débit fictif de connexion/cleanup et aucun verrou mensuel dû à une seule réserve future. Un refus de marge avant création rend l'énoncé complet au classique.

`discord_live_provider.py` implémente le primaire WebSocket Live, format PCM officiel, conversion filtrée 48 kHz stéréo vers 24 kHz mono, envoi cadencé, réception indépendante du consommateur, fermetures bornées et traitement des annulations. `discord_live.py` raccorde solo natif et groupe après admission STT au lecteur Discord et au pont métier commun. Identité de compte vérifiée, mémoire/histoire/outils, documents, invalidation et reprise sont conservés. Les états fournisseur inconnus et l'usage final en cours de comptabilisation restent durables.

`main.py`, configuration et diagnostics raccordent ces modules, avec arrêt de l'adaptateur avant le collecteur. `discord_voice.py` conserve le classique et son nettoyage. `live_bridge.py` ajoute la source Discord persistée sans changer l'identité du mobile. Les anciens tests de raccord CLI sont isolés des appels réels et vérifient la construction/fermeture des composants.

## Vérification et contre-revue

Les fournisseurs et sons sont injectés ; aucun appel facturé, token privé, serveur Discord réel ou microphone physique utilisé. Les contre-revues ont notamment vérifié le masque global, les schémas du SDK, l'absence de replay, la persistance des états inconnus, le comptage avant effacement du registre, les réservations concurrentes, l'exposition sans événement d'usage et la séparation des buffers/durée maximale.

Résultats consolidés sur le lot final :

| Vérification | Résultat observé |
| --- | --- |
| Suite Python complète, environnement local Python 3.12 | **980 tests, zéro échec, 12 skips Discord optionnels**, 49,1 s ; 968 tests exécutés |
| Commandes JavaScript du workflow `jade-rebuild.yml` | **25 commandes réussies** |
| Collecteur, politique et adaptateur ensemble, dernière passe ciblée | **68 tests réussis** |
| Adaptateur et régressions partagées vocal/mémoire/PCM | **146 tests réussis** |
| Fournisseur Live et schémas du SDK officiel | **18 tests réussis** |
| Contre-revue finale des réservations | **14 tests réussis**, repro interinstances 39,96 → 40,01 EUR corrigé |
| Documentation, liens/backlog, compilation et `git diff --check` | Réussis |

Ces suites ciblées sont des recouvrements de la suite complète, pas des tests à additionner au total. La contre-revue indépendante conclut positivement sur le fournisseur, l'adaptateur, la politique et le switch global après correction des courses observées. **Aucun critère logiciel restant identifié dans le périmètre de REC-051.** La publication regroupe code, tests et documentation dans un commit cohérent sur `develop` après `31efc13`, sans réécrire l'historique. La CI Linux/Windows et le scan de secrets de ce commit sont contrôlés après publication ; leur résultat est rapporté dans la réponse de livraison. Les essais matériels ci-dessous restent `À valider`, quel que soit le résultat de la CI.

## Suivi CI Windows après `0122897`

Le lot fonctionnel a été publié dans [`0122897`](https://github.com/goldaj/jade-vtuber/commit/0122897af7135fe5498e60c4978d6bc4aad20543). Le [scan de secrets](https://github.com/goldaj/jade-vtuber/actions/runs/45960438710) et Linux ont réussi ; Windows a atteint huit minutes dans la [CI initiale](https://github.com/goldaj/jade-vtuber/actions/runs/45960438650), avant la fin et le résumé de toutes les traces d'erreur. Le dépôt contenait bien la livraison ; l'interruption de conversation n'a pas perdu les commits.

Les deux tests de politique `test_month_resets_at_paris_midnight_only_after_new_snapshot` et `test_unknown_failed_and_stale_collections_remain_classic` pouvaient nettoyer leur répertoire pendant qu'un thread continuait à écrire dans SQLite. Deux régressions déterministes tiennent une vraie connexion par barrière : elles échouent avant correction et passent après. Le helper `run_blocking_owned` attend réellement le worker avant de propager l'annulation, même répétée ; la collecte rejoint toutes ses sources. Les transactions, prix, seuils, réserves et délais réseau restent identiques.

Le test mémoire L2/Core présentait un autre défaut reproduit avec des écritures de journal lentes : son helper de test annulait les délégations après trois secondes, même pendant un commit d'action terminée. Il attend maintenant sans injecter cette annulation, avec la borne de délégation et une marge de persistance. Le scénario lent passe en 6,249 s après correction ; les assertions métier sont conservées. Le journal interrompu ne permet pas d'attribuer formellement l'erreur Windows à ce mécanisme, mais le défaut de fixture est établi.

Enfin, la suite exportée complète était relancée à l'intérieur de la suite principale, sous un timeout de 180 s, sans sortie visible avant la fin. Elle a atteint ce timeout. Le test unitaire conserve ses vérifications d'isolation/imports/smoke et de réexport ; un nouveau job `preview-offline` exécute **tous** les tests depuis l'export isolé sur les deux OS. Le script affiche la progression en continu. Les quatre jobs de la matrice gardent chacun huit minutes, les permissions de lecture seule et les dépendances verrouillées. Aucune validation d'export n'est abandonnée.

Contre-revues distinctes favorables sur le nettoyage, la fixture et la séparation CI. Suites ciblées : **104 tests** collecte/politique/adaptateur/fournisseur/configuration et **22 tests** du pont métier réussis. Vérification locale du correctif final : **982 tests sur le dépôt en 25,2 s, zéro échec, 12 skips** ; puis **982 tests depuis l'export isolé en 23,5 s, zéro échec, 18 skips** liés aux transports optionnels et aux éléments privés/non Git exclus de l'export. Ces deux exécutions vérifient la même suite dans deux environnements et ne s'additionnent pas en une couverture de 1 964 tests distincts. Le préflight contrôle 290 fichiers Python/TOML ; compilation, documentation/liens/backlog, YAML et diff-check sont conformes. La CI du commit de suivi valide ensuite séparément dépôt et export sous Linux et Windows. REC-051 demeure À valider pour les essais réels.

## Limites et reprise

La collecte normale utilise **40 EUR**, car les fournisseurs ne publient pas de garantie comptable instantanée. Sans clé d'administration OpenAI utilisable, change ou usage Tavily nécessaire, Discord reste classique avec une raison. Les comptes partagés avec d'autres applications sont inclus au niveau organisation/compte ; la qualification sur le poste doit confirmer ce périmètre. Une frontière mensuelle Tavily non identifiable impose temporairement le classique au lieu d'inventer un zéro ou une consommation égale au plan.

Le seuil choisit uniquement le moteur vocal Discord et ne plafonne pas la facture finale : classique, outils et mobile continuent. **Live mobile reste ON par défaut, désactivable dans Profil, sans budget financier.** Son comportement et ses tests sont conservés.

**REC-051, À valider :** après mise à jour et redémarrage du poste, observer audio solo/groupe et latence, permissions/DAVE, accès Live/Costs et Tavily, seuil réel, déconnexion/reconnexion, fermeture fournisseur, OFF complet et mobile simultané. Le parcours groupe conserve STT avant le Live. Une session d'issue inconnue ne doit pas être effacée manuellement pour forcer une nouvelle ouverture.

La voix originale reste DEV-041 ; Brise demeure le recours API explicite et Aube n'est pas présumée disponible. Les autres développements non liés à cette demande ne sont pas engagés.

## Documents canoniques

[Architecture Discord](../../architecture/DISCORD_LIVE.md), [Live mobile](../../architecture/LIVE_MOBILE.md), [état develop](../../handbook/BRANCH_STATE.md), [guide technique](../../handbook/TECHNICAL.md), [guide utilisateur](../../handbook/USER_GUIDE.md), [REC-051](../../backlog/02-RECETTE.md#rec-051--live-discord-automatique-et-interrupteur-global-ancienne-dev-052), [journal technique](../CHANGELOG.md).


## Passation à Codex sur demande du propriétaire

Le propriétaire demande de pousser l'état prêt sur `develop`, après fusion si nécessaire, puis de laisser Codex poursuivre. Les changements mobiles concurrents `4ad1005` (Config et persistance des réglages) sont intégrés avant la publication du correctif de suivi. Le conflit du journal conserve les deux entrées ; l'export conserve à la fois `preferences.js` et le nouveau runner de tests. Les 982 tests dépôt/export ci-dessus ont été exécutés avant cette fusion. **La CI du résultat fusionné et les éventuels correctifs suivants sont laissés à Codex**, sans présumer leur réussite ni celle des recettes réelles.
