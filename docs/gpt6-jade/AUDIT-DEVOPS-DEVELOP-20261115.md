# Audit DevOps/PO transverse de `develop` — 15 novembre 2026

> **Périmètre réel** : `goldaj/jade-vtuber`, base `develop`, revue à partir de la pointe `1669d954717d3ac2939f2e094432a48197d3d8c5`. **Ce n'est ni la branche `devops` ni `main`.**
> Ce rapport décrit les observations distantes (code GitHub + GitHub Actions), les modifications proposées et les opérations restant à effectuer sur le vrai PC Windows. La documentation n'est pas une preuve de recette réelle.

## Synthèse PO / SRE

**Décision de livraison : CI rouge, ne pas déclarer la branche prête pour un déploiement normal.**
Il existe bien une CI Ubuntu/Windows, un scan historique Gitleaks et un préflight local, mais le statut observable au départ du travail n'est pas vert.

**Preuve** : run [43767519744](https://github.com/goldaj/jade-vtuber/actions/runs/43767519744), job Ubuntu `132975854846`, commit `1669d954...`, **520 tests, 17 failures, 5 errors**, résultat `failure` (observé le 15/11). Le scan secrets [43767519734](https://github.com/goldaj/jade-vtuber/actions/runs/43767519734) sur le même commit était `success`. L'état du job Windows était encore en cours lors de l'examen ; ne pas le qualifier de vert sans vérifier son résultat final.

## Corrections codées dans la branche de travail

| ID | Problème vérifié | Modification | Validation disponible |
| --- | --- | --- | --- |
| D01 | Plusieurs pushes de `develop` déclenchent chacun deux runners Linux/Windows complets, souvent alors que le commit est déjà remplacé | Ajout d'une `concurrency` par workflow/ref/PR avec `cancel-in-progress: true` dans `jade-rebuild.yml` | Revoir le YAML et observer deux pushes rapprochés en PR |
| D02 | Les scans historiques de secrets et le contrôle publication courent aussi sans regroupement | Même contrôle de concurrence dans `jade-secret-scan.yml` et `jade-publication.yml` | Vérifier que le dernier run par ref termine ; scan complet non supprimé |
| D03 | Le checkout du workflow principal utilisait un tag d'action mouvant et persistait par défaut le token GitHub dans la configuration Git | Checkout fixé au SHA déjà utilisé par le scanner, `persist-credentials: false`, historique conservé pour `scripts/check_docs.py` | Tests sur PR de `develop` |
| D04 | La suite complète et l'installation des extras démarrent avant les contrôles légers sans dépendance | Ajout de `python tools/jade_ci_preflight.py` avant installation Poetry | Consulter la nouvelle étape dans Actions |
| D05 | Le workflow diagnostic avait une souscription push sur une branche historique absente | Diagnostic rendu uniquement manuel (`workflow_dispatch`) | Vérification du trigger |
| D06 | Le magasin SQLite crée `user_version=3`, mais l'export et l'import refusent 3 : sauvegarde/restauration cassées | `memory_transfer.py` accepte les schémas 1, 2, 3 tout en préservant contrôle d'intégrité/manifest/absence d'écrasement ; test d'autobiographie mis à jour pour la version réelle | Relancer tests ciblés, puis toute la CI |
| D07 | La doc ne disait pas clairement ce qui avait été corrigé, non testé ou reporté | Présent dossier, mises à jour du handbook et passation Codex | `scripts/check_docs.py` en PR |

**Limites de cette passe** : accès au dépôt et aux logs GitHub, **pas** au poste Jade, à Tailscale Serve, aux secrets, aux périphériques audio ni aux installations Live2D. Les commandes GitHub Actions pourront confirmer les tests hors ligne uniquement ; aucune connexion Discord/Twitch/OpenAI ni dépense API n'a été effectuée. Aucun redéploiement, changement de `main` ou de VPS.

### Note de sécurité sur l'annulation des anciens scans

Le dernier scan secrets vérifie les références Git **encore accessibles** (`--all HEAD`), ce qui détecte les anciens commits conservés dans leur histoire. La concurrence évite de multiplier les checks identiques. Ce mécanisme **n'est pas une garantie** sur des commits rendus inaccessibles par `force push` ou sur des secrets déjà publiés ; conserver les protections de branche et le processus de révocation. Ne pas remplacer le scan Gitleaks par le seul préflight de syntaxe.

## Backlog d'incidents à reprendre par Codex

| Priorité | Sujet et preuve | Action demandée | Critère de fin |
| --- | --- | --- | --- |
| **P0** | `develop` échoue globalement sur Ubuntu : run 43767519744, 17 FAIL + 5 ERROR ; ne pas confondre avec les nombreuses erreurs `planned_not_confirmed` journalisées pendant des tests attendus | Extraire la liste à partir du **dernier** job sur la pointe à intégrer, reprendre les régressions **sans désactiver ni ignorer les tests** ; les 3 erreurs de backup schéma v3 sont ciblées par D06 | Ubuntu + Windows verts pour le SHA final, sans `continue-on-error` |
| **P1** | `tests/test_jade_discord_open_voice.py` : 2 ERROR et environ 8 FAIL sur déplacement de salon, interruption, reprise, réception et reconnexion | Comparer les nouveaux contrats vocal/consentement, corriger code ou tests devenus réellement obsolètes, prouver l'isolation et l'absence d'auto-écho | Tests ciblés verts et recette Discord réel |
| **P1** | `tests/test_jade_discord_text_policy.py` : 5 FAIL concernant suivi d'auteur, messages sans mention, commandes mémoire, groupe/solo et anti-bot | Réconcilier le comportement PO **solo 100 % / groupe 30 % sous conditions** avec les règles par canal, cooldown et anti-boucle. Ne pas transformer les tests en assertions vides | Suite texte verte, cas solo/groupe/DM documentés |
| **P1** | `tests/test_jade_voice_decision.py` : garde de groupe non respectée selon l'ancien test ; `tests/test_persona_runtime_20261115.py` : backpressure Twitch au milieu d'une réponse | Revoir les règles d'adresse explicite, le multi-utilisateur et l'inflight Twitch | Tests corrigés avec scénarios contradictoires, zéro fuite inter-canal |
| **P1** | `tests/test_jade_publication_export.py::test_real_preview_runs_its_own_offline_suite` échoue : la suite indépendante de l'aperçu échoue aussi. Potentielle conséquence d'autres tests, pas preuve isolée d'une fuite | Relancer après correction des tests sources, puis diagnostiquer les éventuelles erreurs résiduelles de l'export | Suite preview verte, artefact toujours non autorisé à publier |
| **P1** | GitHub rapporte `develop` avec `protected: false` et pas de `required_status_checks` | Une fois la CI verte, configurer règles de protection/ruleset avec checks Ubuntu, Windows et Gitleaks ; empêcher fusion si statut rouge et `force push` non désiré | Règle active vérifiée sur une PR test ; ne pas imposer un blocage aveugle aujourd'hui |
| **P1** | Sauvegarde SQLite en ZIP **non chiffrée** : le manifest SHA-256 garantit l'intégrité, **pas la confidentialité** ; anciennes sauvegardes subsistent après un oubli | Choisir emplacement/ACL Windows + disque chiffré, vérifier restauration sur copie et rétention/suppression des archives ; envisager chiffrement de bout en bout si transfert | Restauration de DB v3 sans perte de `conversation_turns`, politique de purge documentée |
| **P1** | `turn_logging.py` journalise les auteurs, identifiants, textes et transcriptions en clair dans stderr | Confirmer avec le propriétaire la politique de journalisation exhaustive ; prévoir fichier privé hors Git, ACL strictes, rotation/rétention et redaction/opt-in pour diagnostics partagés. Ne **pas** retirer arbitrairement les logs demandés | Logs utiles et confidentiels même sur incident ou support |
| **P2** | Launcher dans `D:\Jade\launcher` est une copie distincte ; le code peut se mettre à jour alors que le launcher reste vieux. PID peut devenir obsolète ; pas de supervision automatique | Ajouter contrôle de version du launcher, détecter PID réutilisé et définir démarrage/reprise sûrs (sans boucle payante de requêtes) | Essai Windows : mise à jour, reboot, crash, arrêt volontaire, reprise contrôlée |
| **P2** | Pas de recette réelle automatisable Discord/Twitch/PC/Android ; GitHub ne possède pas les secrets ni les périphériques | Préparer recette manuelle PC/Android avec latence, coupure réseau, microphone/haut-parleur, Tailscale, Live2D, mémoire et coût OpenAI ; conserver preuve locale sans données privées | PV de recette daté, environnement/version/SHA et résultats |
| **P2** | Dépendances d'actions encore référencées par tags (`actions/setup-python@v5`, `actions/checkout@v4` dans le workflow publication) ; Poetry installé sur chaque matrix | Fixer les SHAs après validation, envisager cache de dépendances sûr, mesurer le gain sous Windows/Linux et garder verrouillage `poetry.lock` | Actions identiques reproductibles, durée médiane observée |
| **P2** | `main` et `develop` divergent : comparaison au contrôle, `develop` 386 commits devant / 9 derrière `main` | Établir stratégie d'intégration, inventaire des 9 commits de `main`, ne pas forcer de merge ni remplacer l'historique | Plan de release et tests depuis la future branche de release |
| **P3** | Nombreuses branches historiques candidates au nettoyage, diagnostic inutile sur branche morte | Revalider les SHA/PR avant suppression ; suivre `docs/handbook/BRANCH_MAINTENANCE.md` | Branches supprimées seulement si ancêtres de develop et sans travaux actifs |

## Reprise opérationnelle (Codex)

1. `git fetch origin && git switch develop && git pull --ff-only`, puis relever le SHA exact. Rejouer l'audit si `develop` a évolué.
2. Comparer/merger le correctif `fix/develop-devops-audit-20261115` **vers develop uniquement** après vérification des éventuelles collisions avec d'autres agents. Le correctif ne doit pas écraser de commits en cours.
3. CI : `python tools/jade_ci_preflight.py`, `poetry sync --only main -E discord -E mic -E vts -E discord-voice`, `poetry run python -m compileall -q src main.py`, `poetry run python -m unittest discover -s tests -v`, `poetry run python scripts/check_docs.py`. Vérifier également la syntaxe des scripts PowerShell sur Windows. **Aucun contournement de tests rouges.**
4. Recette mémoire ciblée : `poetry run python -m unittest tests.test_jade_persistent_memory tests.test_jade_autobiographical_memory -v`, export/import sur une **copie de base factice** v3, comparer l'intégrité, contrôler les conversations v3 et la confidentialité des ZIP.
5. Une fois **tous** les checks verts, valider l'environnement réel Windows/Discord/Twitch/PWA (hors CI), puis seulement envisager un déploiement/une protection de branche suivant décision du propriétaire.
6. Conserver le modèle de gouvernance : modifications de code/CI et de docs ensemble dans **la branche correspondante** ; mettre à jour les notices et les schémas si le runtime/infra change. Ne pas affirmer qu'une demande est réalisée parce que ce document la mentionne.

### Vérifications finales attendues dans la PR

- [ ] CI Linux et Windows au **SHA final**, pas seulement sur un commit ancien.
- [ ] Scan Gitleaks réussi sur le dernier SHA.
- [ ] Aucun test retiré, ignoré, rendu non bloquant, ni donnée sensible publiée.
- [ ] Journaux et ZIP de mémoire jamais copiés dans les artefacts publics.
- [ ] Windows launcher, voix et mobile testés sur le vrai matériel avant annonce de livraison.
- [ ] Aucun merge dans `main`, aucune configuration du VPS Hyperliquid modifiée.
