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

`main.py --all-channels` lance les connecteurs Discord écrit/vocal, Twitch, PC et PWA privée simultanément, avec mémoire optionnelle, voix et avatar ; aucun sélecteur de plateforme. Pour la configuration PC/Android, utiliser la [passation opérationnelle](../gpt6-jade/HANDOFF-CODEX-MOBILE-20261115.md). Pour les intentions A/B r20 et les animations corporelles futures, consulter [Live2D](../gpt6-jade/LIVE2D-INTENT-ANIMATION-HANDOFF-20261115.md).

Toute modification de code doit maintenir les guides requis par `scripts/check_docs.py` et les documents de domaine concernés. Les historiques de PR restent consultables, sans répéter leurs statuts anciens ici.


### Correctifs en PR : Discord PCM / identité mémoire / PWA

La branche de PR `fix/discord-pcm-memory-mobile-20261116` découple le streaming Discord du lecteur `ffplay` local et propose une liaison mémoire Goldaj ↔ Discord/Twitch via un code temporaire créé dans la PWA privée. **Source unique des détails, risques, prérequis et essais PC restant à faire :** [note de correctifs](PR-PCM-MEMOIRE-MOBILE-20261116.md). Ce document décrit une PR **non fusionnée** ; ne pas traiter son contenu comme présent dans `develop` avant le merge.
