# Passation obligatoire pour Codex, Terra et tous les agents IA : branche feat/turn-conversation-logs-20261115

**Branche divergente : feat/turn-conversation-logs-20261115.** Journalisation des tours de conversation (messages, intentions et modalités de réponse), avec module turn_logging.py, adaptation de l'orchestrateur et tests de journalisation. Les dix commits propres recensés face à develop demandent une revue de contenu avant suppression. Pas de PWA mobile, de mémoire SQLite ou de launcher unifié. Les guides sont spécifiques à cette branche et ne doivent pas être confondus avec ceux de develop.

## Directive permanente de documentation

**Toute modification de code, configuration, scripts, dépendances, ressources, tests, interfaces ou infrastructure DOIT entraîner une mise à jour de la documentation de la BRANCHE CONCERNÉE dans le même commit/PR.** Ce contrat s'applique aux changements minuscules autant qu'aux nouvelles fonctions, même si la correction consiste seulement à actualiser « aucun changement fonctionnel » dans certaines pages.

Mise à jour systématique des fichiers suivants :
1. `docs/handbook/INSTALLATION.md` : prérequis, OS, clone, configuration, mises à niveau.
2. `docs/handbook/DEMO.md` : procédure de démo, statut simulé/réel, limites.
3. `docs/handbook/USER_GUIDE.md` : comportement visible, commandes, toutes les fonctionnalités.
4. `docs/handbook/TECHNICAL.md` : architecture, interfaces, algorithmes, infrastructure, sécurité, coût, opérations.
5. `docs/handbook/AI_HANDOFF.md` : périmètre, passation, risques, décisions et nouvelles règles agents.
6. `docs/handbook/BRANCH_STATE.md` : présence/absence des fonctions, différences avec autres branches, preuves de test.
7. `AGENTS.md` et l'index `docs/handbook/README.md` si leur portée, chemin ou consigne change.

**Ne pas mettre la documentation d'une branche « au niveau de develop » en copiant du contenu** : les éléments absents doivent explicitement rester absents. Relire le code de la branche avant d'affirmer qu'une fonction y existe ; les discussions, tickets et anciennes PR sont des archives, pas la vérité opérationnelle. En cas de conflit entre anciens documents et nouveau manuel, le code testé et les décisions les plus récentes priment ; corriger les documents contradictoires.

## Workflow concret obligatoire

- **0. Inventorier** : `git status --short --branch`, `git log -1`, `git branch -avv`, liste des PR encore actives. Ne pas forcer, rebaser ou supprimer du travail de quelqu'un d'autre. Préserver `main` et `develop` selon les instructions de l'utilisateur.
- **1. Analyser l'impact** : fonctionnement utilisateur, comportements, config, infra, interfaces, sécurité, secrets, coûts, compatibilité, logs, modèles graphiques, tests et erreurs, **pour cette branche**.
- **2. Développer** dans une branche dédiée si nécessaire, sans déploiement ou appel payant implicite.
- **3. Mettre à jour TOUS les guides** au même niveau de changement et noter les fonctionnalités nouvelles, modifiées, retirées ou non vérifiées. Ne pas faire d'affirmation de succès matériel sans essai réel.
- **4. Tests** : lint/compile, unittest offline, préflight, validation de la Démo Express et éventuellement des tests matériels autorisés.
- **5. Vérifier la garde documentaire** `python scripts/check_docs.py` ; son mode CI compare les fichiers sources et les guides modifiés par la PR.
- **6. Passer en revue/PR** : exposer dans le résumé l'état de chaque guide, les branches impactées, les limites, et signaler toute procédure manuelle restante.
- **7. Fusionner selon la politique du propriétaire** ; surtout pas de merge automatique du code de `develop` dans `feat/turn-conversation-logs-20261115` sous prétexte de synchroniser les textes.

## Sauvegarde, confidentialité et coûts

Aucun token API, compte privé, clé GitHub, fichier `.env`, audio, transcript ou mémoire personnelle dans Git ou les logs. La démo Express ne contacte personne. Un test réel Discord/Twitch, microphone/voix ou OpenAI doit être autorisé, et le coût/les données transmises annoncés. Ne pas modifier le VPS de trading ni publier les ports du PC pour faciliter un essai. Distinguer tests simulés de validation physique.

Les branches de fonctionnalités **déjà intégrées à develop** peuvent être supprimées après preuve d'ascendance et revue des PR ; le connecteur GitHub disponible lors de cette intervention n'autorise pas la suppression de références. La liste et les commandes prévues pour Codex figurent dans [BRANCH_MAINTENANCE.md](BRANCH_MAINTENANCE.md). **Ne pas supprimer un travail divergent sans l'avoir comparé**.

## Checklist de PR pour agents

- [ ] Fonction ou correction testée sur cette branche
- [ ] Installation, démo, utilisateur, technique, agents et état de branche révisés
- [ ] `AGENTS.md` et liens index cohérents
- [ ] Aucune fonctionnalité de `develop` revendiquée par `main` sans code présent
- [ ] CI Windows/Linux verte, scan secrets, guide de démo et scripts compatibles
- [ ] Résumé clair des essais réels manquants, des risques et des autres branches à documenter séparément

**Fin d'intervention :** indiquer fichiers et branche modifiés, SHA, résultats de tests, PR, statut de fusion et corrections restant à faire. Ne pas dire « testé sur le PC » si seules des actions GitHub ont été effectuées.

## Avertissement de maintenance pour feat/turn-conversation-logs-20261115

Journalisation des tours de conversation (messages, intentions et modalités de réponse), avec module turn_logging.py, adaptation de l'orchestrateur et tests de journalisation. Les dix commits propres recensés face à develop demandent une revue de contenu avant suppression. Pas de PWA mobile, de mémoire SQLite ou de launcher unifié.

Codex doit comparer les dix commits propres et leurs tests à develop. Si toutes les fonctionnalités sont déjà reprises, documenter la preuve avant d'effacer la branche ; sinon conserver/apporter les modifications utiles, sans merger develop à l'aveugle. Les documents de cette branche doivent rester alignés sur ce runtime ancien.
