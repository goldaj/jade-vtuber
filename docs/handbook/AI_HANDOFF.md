# Contrat et passation permanente pour les agents IA : develop

**Cartographie de référence :** consulter les [deux schémas visuels](../architecture/README.md) avant d'analyser les flux ou de déplacer des composants. Ils servent d'orientation, jamais de preuve à eux seuls : examiner `main.py`, la configuration, les adaptateurs et les sorties. Lorsqu'une modification rend une flèche ou une fonction obsolète, mettre à jour les images et cette documentation dans la même branche.

## Instruction impérative : documentation synchronisée avec le code

**Après CHAQUE modification de code, test, configuration, outil, dépendance, route infra, interface, API ou ressource, un agent IA doit revoir et mettre à jour TOUS les documents de la branche modifiée dans la même PR**, même si certains se contentent de signaler « vérifié, sans changement de comportement ». Une action ne doit pas finir avec seulement un commit de code et un message de chat.

Fichiers à actualiser systématiquement :
- `docs/handbook/INSTALLATION.md`
- `docs/handbook/DEMO.md`
- `docs/handbook/USER_GUIDE.md`
- `docs/handbook/TECHNICAL.md`
- `docs/handbook/AI_HANDOFF.md`
- `docs/handbook/BRANCH_STATE.md`
- `docs/handbook/BRANCH_MAINTENANCE.md`
- `AGENTS.md` et `docs/handbook/README.md` dès que leur index/règle/état doit évoluer.
- **En complément** : toutes les passations spécialisées `docs/gpt6-jade/` impactées (mobile, voix, mémoire, launcher, historique de décisions). Une mise à jour dans un seul ancien guide ne suffit pas si les autres deviennent contradictoires.

La garde `scripts/check_docs.py` vérifie le contrat en PR et les workflows GitHub exécutent tests Windows/Linux et scan de secrets. **Chaque branche a ses propres versions**, révisées en fonction du code **réellement présent sur cette branche**, y compris `main`. Ne pas propager une revendication de develop vers main, ni écraser le code d'une branche de feature pour « mettre à jour la doc ».

## Décisions produit non négociables sur develop

1. **Une seule Jade, tous les supports simultanément.** Le launcher n'a pas de menu de mode. Utiliser `--all-channels`, pas choisir Discord au détriment de mobile/micro/Twitch. Les flags individuels existent pour le diagnostic et tests uniquement. Aucune priorité fixe par canal.
2. **Jade décide du prochain tour en attente.** `TurnArbiter` permet un choix LLM sensible au contexte, limité par délais et équité, sans préemption d'une réponse en cours. Garder l'ordre d'un fil, le fallback FIFO, la file bornée et `task_done`.
3. **Routes privées** : un message mobile/micro/HTTP local ne doit pas être diffusé publiquement via Discord, OBS ou Twitch par simple présence de ces canaux ; respecter l'identité authentifiée du propriétaire.
4. **Android est une PWA privée** : Tailscale Serve uniquement sur le PC vers loopback `8766`, double protection compte Tailscale + Bearer ; aucun service public, aucune modification du VPS Hyperliquid. SDK Web Live2D propriétaire installé hors Git et compatible avec le modèle r20.
5. **Mémoire persistante optionnelle et respect du consentement** : SQLite hors repo, identités transport vérifiées, Core Memories non purgées automatiquement mais effaçables sur demande, curation facultative avec coûts et risques.
6. **Voix/intention** : préfixe strict `[INTENT:...]` supprimé avant sorties et mémoire, pitch DSP nécessitant FFmpeg/rubberband ; aucune affirmation de prosodie garantie sans écoute.
7. **Deux démos clairement distinctes** : Démo Express Windows sans API et purement simulée ; démo OpenAI Live2D réelle séparée, avec clé/budget. Ne pas vendre la simulation comme preuve d'IA opérationnelle.

## Procédure de travail des agents

1. **Inventaire** : vérifier `git status --short --branch`, SHA courant, branches et PR ouvertes, modifications locales d'autres agents. Ne pas écraser un état de travail ni utiliser `reset --hard` pour faciliter une action.
2. **Choisir la bonne branche** : travail sur `develop` ou branche dédiée à partir de `develop`, `main` uniquement sur autorisation séparée. Voir la [note de nettoyage](BRANCH_MAINTENANCE.md) ; les anciennes branches ancêtres de develop sont candidates à suppression par Codex, celles divergentes demandent revue.
3. **Lire les sources et les docs exactes** de cette branche, surtout `main.py`, `config.py`, `orchestrator.py`, les transports touchés, `AGENTS.md` et le guide concerné. Ne pas considérer un rapport d'une ancienne PR comme la preuve d'un comportement courant.
4. **Analyser avec perspectives PO, architecture, backend, audio/Live2D, SRE/infra, sécurité/privacité et QA** : user journey, coût, compatibilité, tests et mode dégradé. Corriger les contradictions plutôt que les documenter comme des réussites.
5. **Coder puis documenter** la modification dans TOUS les fichiers listés, et dans chaque branche réellement concernée. Ne pas copier des documents tels quels sur main si le runtime diffère.
6. **Valider** : `poetry run python -m compileall -q src main.py`, `poetry run python -m unittest discover -s tests -v`, `poetry run python main.py --preflight`, `python scripts/check_docs.py`, tests ciblés, Windows PowerShell parser ; plus essais physiques **avec consentement** quand nécessaires.
7. **Revoir et merger** selon la politique propriétaire : ne pas modifier `main` ni les routes du VPS sans instruction claire. Un connecteur qui n'est pas configuré ne doit pas être masqué pour faire passer le launcher.
8. **Livrer** une synthèse avec SHA/branche/PR, fichiers et documents mis à jour, tests automatiques vs tests réels, limites ouvertes, dépendances manuelles et risques. Les consignes de chat ne remplacent pas les changements enregistrés dans le dépôt.

## Reprise Codex sur le PC Windows et Android

Avant toute manipulation sur le vrai PC de Goldaj, lire [le guide d'installation PC Android](../gpt6-jade/HANDOFF-CODEX-MOBILE-20261115.md), le [launcher](../gpt6-jade/LAUNCHER-WINDOWS-20261115.md), les [voix](../gpt6-jade/HANDOFF-CODEX-VOICE-INTENTS-20261113.md), la [mémoire](../gpt6-jade/HANDOFF-CODEX-MEMORY-20261115.md) et [l'audit transverse](../gpt6-jade/AUDIT-TRANSVERSE-20261115.md). Réaliser l'inventaire du volume D:, de la config privée, du SDK/Live2D, des routes Serve et du stockage SQLite avant installation. Ne pas afficher/committer le contenu des secrets. Ne pas annoncer de connexion ou d'animation réussie sur Android sans avoir vu le test.

L'utilisateur ne veut pas de longue chaîne de prérequis pour la **démo** : privilégier le programme WinForms simulé pour les visiteurs, et conserver la chaîne technique complète seulement pour le **vrai runtime**.

## Nettoyage des branches historiques

Le connecteur GitHub de cette session ne dispose pas d'action de suppression de référence. **Codex devra supprimer les huit branches déjà ancêtres de develop après revalidation individuelle**, voir [BRANCH_MAINTENANCE.md](BRANCH_MAINTENANCE.md). Ne pas supprimer les trois branches divergentes tant que leur apport unique n'est pas audité et repris ou rejeté. Ne pas créer un clone de travail entier uniquement pour modifier la doc d'une autre branche sans vérifier ses commits.

## Checklist avant fermeture d'une PR

- [ ] Cette branche reflète les fonctions réellement présentes, et non des intentions futures
- [ ] Tous les guides et les passations de domaine corrigés
- [ ] Aucun secret, piste audio privée ou mémoire dans les commits
- [ ] Aucune priorité fixe de canal ni sélecteur de mode réintroduit
- [ ] L'isolation mobile/micro et la confidentialité OBS/Discord/Twitch restent testées
- [ ] Test automatique Windows/Linux et scan secrets, et limites de recette matérielle détaillées
- [ ] Aucun changement de `main` ou VPS non demandé

## Addendum obligatoire : 14 réactions propres par intention (15/11/2026)

Le propriétaire demande maintenant **deux animations Live2D réellement différentes ET deux représentations textuelles par chacune des sept intentions**, sur un modèle **2D**, pas 3D. Sur cette branche, seules deux expressions faciales de substitution et deux libellés PWA ont été codés par intention, avec toggle global et synchronisation PC/mobile. Les **14 motion assets dédiés** et le rig en pied validé ne sont PAS livrés. Codex doit lire la [passation Live2D explicite et sa matrice de statuts](../gpt6-jade/LIVE2D-INTENT-ANIMATION-HANDOFF-20261115.md), réaliser le travail artistique/technique qui manque sur une branche indépendante, ne brancher aucun motion ID fictif ou SDK incompatible, effectuer une recette réelle PC + Android, et synchroniser **toutes** les documentations de la branche. Ne pas afficher de didascalies sur les canaux publics ni modifier `main` sans accord.

## Passation obligatoire : évolution dialogue (2026-11-15)

Goldaj a validé un prompt exact : **ne pas le réécrire** sans autorisation. Fichier d'exécution `prompt_chat.txt` ; les trois prototypes dans `docs/gpt6-jade/PROPOSITIONS-PERSONNALITE-20261115.md` ne sont plus à activer. Garder les intentions `[INTENT:...]` séparées et inchangées. Le code `develop` a reçu `low / 320`, mémoire SQLite v3 des échanges entiers opt-in, 48 messages d'historique, et participation solo 100 % / groupe 30 % des interventions spontanées admissibles sur Discord/Twitch, avec contraintes de plateforme.

Avant toute autre modification, lire [la passation technique de ce chantier](../gpt6-jade/DIALOGUE-LOW320-HISTORIQUE-PARTICIPATION-20261115.md), examiner les variables privées et contrôler les règles de consentement. Tester la migration d'une base v2 sur copie de sauvegarde, les reprises après redémarrage, l'effacement, les politiques solo/groupe et le coût. Aucun test réel PC/Discord/Twitch n'a été observé dans ce chantier : tests Python ajoutés, pas encore exécutés. Deux réactions par intention sont seulement **planifiées** ; ne pas prétendre que 14 animations nouvelles sont prêtes.

## Passation Codex : sécurité, CI et restauration (15/11/2026)

**Audit de référence** : [revue DevOps develop du 15 novembre 2026](../gpt6-jade/AUDIT-DEVOPS-DEVELOP-20261115.md). Priorité : garder les checks Ubuntu/Windows bloquants, **ne pas** masquer les erreurs de la suite ni fusionner dans `main` pour contourner un échec. Vérifier l'ordre des changements des agents sur `develop`, le diagnostic des 17 tests en échec et 5 erreurs observés sur le commit initial, le transfert SQLite v3, la conservation des logs privés et la protection GitHub de `develop`. Les documents et l'historique GitHub Actions décrivent les résultats observables, pas un test sur le poste Jade. Après toute modification, actualiser les guides de cette branche.
