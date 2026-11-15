# Manuel de Jade : branche main

**Périmètre :** ce dossier décrit le **code réellement présent sur cette branche Git**, pas une promesse de fonctionnalités disponibles dans `develop`.

| Besoin | Document |
| --- | --- |
| Partir d'un Windows/Linux neuf et cloner le dépôt | [INSTALLATION.md](INSTALLATION.md) |
| Installer une démonstration en quelques clics | [DEMO.md](DEMO.md) |
| Utiliser chaque fonctionnalité disponible | [USER_GUIDE.md](USER_GUIDE.md) |
| Architecture, flux, algorithmes, infrastructure et sécurité | [TECHNICAL.md](TECHNICAL.md) |
| Consignes pour Codex et agents IA | [AI_HANDOFF.md](AI_HANDOFF.md) |
| Périmètre des fonctionnalités réellement présentes ici | [BRANCH_STATE.md](BRANCH_STATE.md) |
| Nettoyage prudent des branches intégrées | [BRANCH_MAINTENANCE.md](BRANCH_MAINTENANCE.md) |

La branche `main` contient le moteur modulaire de Jade, une démo de dialogue hors ligne, des connecteurs opt-in et une démo Windows animée distincte. Elle **n'intègre pas** la PWA Android moderne, les mémoires SQLite/Core, le launcher tout-en-un ou l'arbitrage par IA de `develop`. La démo Express est une **simulation Windows autonome**, clairement distincte du moteur. Ne jamais transformer une possibilité d'intégration en succès matériel : les connexions réelles ont besoin de clés, autorisations, tests et parfois de coûts.

La documentation de chaque branche est conservée **dans cette branche elle-même**. Pour une autre branche, ouvrir les mêmes chemins après avoir sélectionné la branche dans GitHub ou Git. Les instructions d'un autre commit ne s'appliquent pas automatiquement. Tous les documents et `AGENTS.md` doivent évoluer avec le code lors de chaque modification.
