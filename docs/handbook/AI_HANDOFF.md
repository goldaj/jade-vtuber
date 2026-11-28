# Contrat et passation permanente pour les agents IA : develop

**Cartographie obligatoire avant modification des flux de dialogue, arbitrage, mémoire ou diffusion :** [atlas fonctionnel à cinq vues](../architecture/atlas-fonctionnel-2026-11-16/README.md) et [contrat détaillé](../architecture/atlas-fonctionnel-2026-11-16/CONTRAT_FLUX_COMPLET.md). Réviser les diagrammes lors de tout changement fonctionnel ; les vues de novembre 2026 sont datées, seule l'implémentation de la branche courante est source de vérité.

**Cartographie de référence :** consulter les [deux schémas visuels](../architecture/README.md) avant d'analyser les flux ou de déplacer des composants. Ils servent d'orientation, jamais de preuve à eux seuls : examiner `main.py`, la configuration, les adaptateurs et les sorties. Lorsqu'une modification rend une flèche ou une fonction obsolète, mettre à jour les images et cette documentation dans la même branche.

## Documentation et communication entre agents (contrat allégé)

Le point d'entrée est **[`AGENTS.md`](../../AGENTS.md)**. Le [backlog opérationnel](../backlog/README.md) et sa [Definition of Done officielle](../backlog/DEFINITION_OF_DONE.md) gouvernent les tâches et leur clôture. La documentation fonctionnelle courante vit dans ce manuel et la coordination inter-agents dans [`docs/operations/AGENT_COORDINATION.md`](../operations/AGENT_COORDINATION.md). Une mission active possède **sa propre fiche** dans [`docs/operations/handoffs/`](../operations/handoffs/README.md) et une PR clairement liée ; ne pas modifier un ancien dossier historique comme canal de coordination.

Une modification technique doit **actualiser seulement `docs/operations/CHANGELOG.md` de manière obligatoire** afin de tracer la décision et les preuves ; la garde CI `scripts/check_docs.py` vérifie cette règle. Actualiser en plus uniquement les guides, schémas et données de référence affectés, notamment `BRANCH_STATE.md` si le comportement réel change. Ne pas ajouter des mentions « vérifié, inchangé » aux huit autres manuels par automatisme. Une modification de tests uniquement n'exige pas d'entrée de changelog si elle ne modifie pas les contrats produit.

Les versions de documentation sont **spécifiques à chaque branche** et reflètent son code. Les anciennes passations datées dans [`docs/history/`](../history/README.md) sont des preuves et non des instructions d'exécution actuelles.

## Décisions produit non négociables sur develop

1. **Une seule Jade, tous les supports simultanément.** Le launcher n'a pas de menu de mode. Utiliser `--all-channels`, pas choisir Discord au détriment de mobile/micro/Twitch. Les flags individuels existent pour le diagnostic et tests uniquement. Aucune priorité fixe par canal.
2. **Jade décide du prochain tour en attente.** `TurnArbiter` permet un choix LLM sensible au contexte, limité par délais et équité, sans préemption d'une réponse en cours. Garder l'ordre d'un fil, le fallback FIFO, la file bornée et `task_done`.
3. **Routes privées** : un message mobile/micro/HTTP local ne doit pas être diffusé publiquement via Discord, OBS ou Twitch par simple présence de ces canaux ; respecter l'identité authentifiée du propriétaire.
4. **Android.** PWA via Tailscale Serve et le PC Jade en loopback sur `8766`, avec identité Tailscale et jeton Bearer. Installer le SDK Web Live2D compatible séparément sur D:. Le r21 est le modèle des recettes mobiles. Utiliser les instructions d’installation du manuel.
5. **Mémoire persistante optionnelle et respect du consentement** : SQLite hors repo, identités transport vérifiées, Core Memories non purgées automatiquement mais effaçables sur demande, curation facultative avec coûts et risques.
6. **Voix/intention** : préfixe strict `[INTENT:...]` supprimé avant sorties et mémoire, pitch DSP nécessitant FFmpeg/rubberband ; aucune affirmation de prosodie garantie sans écoute.
7. **Démo Express.** Le programme Windows simule le dialogue localement. Le moteur complet lance son renderer Live2D séparément selon le profil.

## Procédure de travail des agents

1. **Inventaire** : vérifier `git status --short --branch`, SHA courant, branches et PR ouvertes, modifications locales d'autres agents. Ne pas écraser un état de travail ni utiliser `reset --hard` pour faciliter une action.
2. **Choisir la bonne branche** : travail sur `develop` ou branche dédiée à partir de `develop`, `main` uniquement sur autorisation séparée. Voir la [note de nettoyage](BRANCH_MAINTENANCE.md) ; les anciennes branches ancêtres de develop sont candidates à suppression par Codex, celles divergentes demandent revue.
3. **Lire les sources et les docs exactes** de cette branche, surtout `main.py`, `config.py`, `orchestrator.py`, les transports touchés, `AGENTS.md` et le guide concerné. Ne pas considérer un rapport d'une ancienne PR comme la preuve d'un comportement courant.
4. **Analyser avec perspectives PO, architecture, backend, audio/Live2D, SRE/infra, sécurité/privacité et QA** : user journey, coût, compatibilité, tests et mode dégradé. Corriger les contradictions plutôt que les documenter comme des réussites.
5. **Coder puis documenter** en actualisant le journal technique obligatoire `docs/operations/CHANGELOG.md`, puis uniquement les guides, schémas et passations réellement impactés sur la branche concernée. Ne pas recopier des documents de develop sur main si le runtime diffère.
6. **Tester le travail** : `poetry run python -m compileall -q src main.py`, `poetry run python -m unittest discover -s tests -v`, `poetry run python main.py --preflight`, `python scripts/check_docs.py`, tests ciblés, Windows PowerShell parser **selon pertinence** ; plus essais physiques **avec consentement** quand nécessaires. Conserver les résultats réels, sans prétendre qu'une simulation valide le poste.
7. **Faire une passe de validation distincte** conformément à la [DoD officielle](../backlog/DEFINITION_OF_DONE.md) : **Codex (tous modèles/sous-agents) OU propriétaire**, un seul suffisant, sans validation humaine obligatoire ; consigner résultat et preuve par ID de carte.
8. **Revoir et merger** selon la politique propriétaire : ne pas modifier `main` ni les routes du VPS sans instruction claire. Un connecteur qui n'est pas configuré ne doit pas être masqué pour faire passer le launcher.
9. **Livrer** une synthèse avec SHA/branche/PR, fichiers et documents mis à jour, tests automatiques vs tests réels, limites ouvertes, dépendances manuelles et risques. **La clôture Done** exige en plus les cinq conditions de la DoD et la mise à jour du statut de la carte ; un compte rendu seul ne suffit pas. Les consignes de chat ne remplacent pas les changements enregistrés dans le dépôt.

## Reprise sur Windows et Android

Suivre l’installation actuelle et l’état de la branche. Faire l’inventaire du SDK, du paquet r21, de la route Serve et du volume D:. Pour les essais PC, utiliser la configuration Run de PyCharm lorsque le poste en dispose. Les secrets, journaux et données SQLite restent dans les emplacements privés. [Installation](INSTALLATION.md) · [PyCharm](../operations/reference/REMOTE-PYCHARM-CONTROL-20261123.md)

## Nettoyage des branches

Examiner la pointe exacte de chaque référence, les PR et le travail local. Comparer les apports divergents avant retrait et consigner leur emplacement de reprise. `main` est le point de retour quand le propriétaire autorise sa mise à jour. [Maintenance](BRANCH_MAINTENANCE.md)

## Checklist avant fermeture d'une PR

- [ ] Cette branche reflète les fonctions réellement présentes, et non des intentions futures
- [ ] Journal technique actualisé si nécessaire ; guides et passations touchés par la modification corrigés
- [ ] Aucun secret, piste audio privée ou mémoire dans les commits
- [ ] Aucune priorité fixe de canal ni sélecteur de mode réintroduit
- [ ] L'isolation mobile/micro et la confidentialité OBS/Discord/Twitch restent testées
- [ ] Test automatique Windows/Linux et scan secrets, et limites de recette matérielle détaillées
- [ ] Aucun changement de `main` ou VPS non demandé

## Contrats à préserver

- **Rendu.** Neuf intentions et dix-huit mouvements sur le r21 mobile. La recette vise ce modèle. L’avatar autonome Windows reste dépendant du paquet r20 tant que DEV-001 est ouvert. [État courant](BRANCH_STATE.md)
- **Dialogue et mémoire.** La personnalité approuvée se trouve dans `prompt_chat.txt`. Le moteur d’intention conserve sa métadonnée hors du texte livré et de la mémoire. Le schéma SQLite v8 permet la lecture globale L1/L2/L3 avec provenance. Les écritures et effacements restent soumis aux droits d’identité. [Contrat mémoire](../operations/handoffs/2026-11-22-jade-global-memory.md)
- **Vérification.** Exécuter les contrôles adaptés aux changements sur Ubuntu et Windows. Pour les essais matériels, consigner les canaux, la version observée et les preuves de fonctionnement. L’historique DevOps est conservé parmi les audits datés. [Audit d’origine](../history/gpt6-jade/AUDIT-DEVOPS-DEVELOP-20261115.md)

## Références courantes

**État des fonctions codées :** [BRANCH_STATE.md](BRANCH_STATE.md). **Améliorations futures :** [catalogue](../ameliorations/README.md). Ne pas recopier des résultats d'anciens audits comme s'il s'agissait de déficiences actuelles du code.
