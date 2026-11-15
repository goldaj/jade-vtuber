# Manuel de Jade : branche develop

Documentation **spécifique au code de develop**, actualisée après les intégrations PR #11 (mobile/mémoire/Discord), #13 (launcher), #14 (tous les canaux et arbitrage) et #15 (passation Codex Android). Ne pas lire la documentation de `main` comme si ces capacités étaient déjà en production.

| Objet | Guide |
| --- | --- |
| Installer Jade depuis un PC Windows neuf | [INSTALLATION.md](INSTALLATION.md) |
| Découvrir en 2 clics sans IA ni comptes | [DEMO.md](DEMO.md) |
| Guide détaillé de chaque fonctionnalité | [USER_GUIDE.md](USER_GUIDE.md) |
| Architecture, algorithmes, API, infra, sécurité | [TECHNICAL.md](TECHNICAL.md) |
| Instructions des agents et règle documentaire obligatoire | [AI_HANDOFF.md](AI_HANDOFF.md) |
| Inventaire précis de cette branche | [BRANCH_STATE.md](BRANCH_STATE.md) |
| Branches à nettoyer prudemment | [BRANCH_MAINTENANCE.md](BRANCH_MAINTENANCE.md) |

**Produit visé :** une seule instance Jade active simultanément sur **Discord texte et vocal, Twitch, micro Windows, HTTP local et PWA Android privée**, avec avatar et voix. Pas de classement de plateformes ; Jade peut arbitrer dynamiquement les prochains messages en attente. Le launcher Windows ne propose **pas de profil de démarrage**. Un connecteur obligatoire manquant empêche le lancement complet.

Pour les manipulations concrètes sur le PC déjà utilisé par le propriétaire, Codex doit aussi suivre [le guide de passation PC/Android](../gpt6-jade/HANDOFF-CODEX-MOBILE-20261115.md), sans toucher au VPS Hyperliquid. Pour une **démo qui fonctionne sans ces services**, utiliser la [Démo Express](DEMO.md), une interface Windows purement simulée. Les tests Linux/Windows GitHub sont hors ligne ; les connexions et le rendu mobile doivent encore être recettés sur le matériel réel.
