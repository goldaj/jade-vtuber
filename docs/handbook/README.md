# Manuel de Jade — develop

Les modules raccordés dans le code sont considérés comme **implémentés**. L'[inventaire des fonctionnalités](BRANCH_STATE.md) est la référence documentaire courante ; les rapports datés ne sont pas un deuxième état du produit.

| Objet | Document |
| --- | --- |
| Installer Jade depuis un poste Windows | [INSTALLATION.md](INSTALLATION.md) |
| Démo Express, sans IA | [DEMO.md](DEMO.md) |
| Utiliser les fonctionnalités | [USER_GUIDE.md](USER_GUIDE.md) |
| Architecture, API et algorithmes | [TECHNICAL.md](TECHNICAL.md) |
| Passation aux agents IA | [AI_HANDOFF.md](AI_HANDOFF.md) |
| **État courant du code** | [BRANCH_STATE.md](BRANCH_STATE.md) |
| Maintenance des branches | [BRANCH_MAINTENANCE.md](BRANCH_MAINTENANCE.md) |
| Schémas fonctionnels | [Atlas de Jade](../architecture/atlas-fonctionnel-2026-11-16/README.md) |
| **Travaux futurs classés par thème** | [Catalogue des améliorations](../ameliorations/README.md) |

Le launcher Windows exécute `main.py --all-channels`. L’installation décrit le service mobile privé, les dépendances et les réglages. Le guide utilisateur couvre le Live et les neuf intentions du r21 mobile. Le raccordement de l’avatar autonome Windows au r21 relève de DEV-001. [Installation](INSTALLATION.md) · [Guide utilisateur](USER_GUIDE.md) · [DEV-001](../backlog/01-DEVELOPPEMENT.md)

Pour les agents : commencer par [AGENTS.md](../../AGENTS.md), puis [le centre opérationnel](../operations/README.md). Le contrôle CI ne requiert désormais qu'une entrée technique dans [CHANGELOG.md](../operations/CHANGELOG.md) lorsque le code ou les outils changent ; mettre à jour les autres guides uniquement s'ils sont impactés. Les archives sont dans [docs/history](../history/README.md).
