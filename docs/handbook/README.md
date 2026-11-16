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
| Deux schémas visuels de l'infrastructure et des flux d'appels | [Architecture de Jade](../architecture/README.md) |

**Produit visé :** une seule instance Jade active simultanément sur **Discord texte et vocal, Twitch, micro Windows, HTTP local et PWA Android privée**, avec avatar et voix. Pas de classement de plateformes ; Jade peut arbitrer dynamiquement les prochains messages en attente. Le launcher Windows ne propose **pas de profil de démarrage**. Un connecteur obligatoire manquant empêche le lancement complet.

Pour les manipulations concrètes sur le PC déjà utilisé par le propriétaire, Codex doit aussi suivre [le guide de passation PC/Android](../gpt6-jade/HANDOFF-CODEX-MOBILE-20261115.md), sans toucher au VPS Hyperliquid. Pour une **démo qui fonctionne sans ces services**, utiliser la [Démo Express](DEMO.md), une interface Windows purement simulée. Les tests Linux/Windows GitHub sont hors ligne ; les connexions et le rendu mobile doivent encore être recettés sur le matériel réel.

## Synchronisation expressions Live2D des intentions (15/11/2026)

Le chantier de synchronisation du modèle 2D PC/PWA avec `Reply.intent`, les deux variantes textuelles/faciales de chaque intention et le toggle `JADE_AVATAR_INTENT_ENABLED` est décrit dans la [passation dédiée pour Codex](../gpt6-jade/LIVE2D-INTENT-ANIMATION-HANDOFF-20261115.md). **Attention : les 14 véritables animations propres restent à produire et à recetter.** Les visages r20 actuels ne sont que des substituts et le rig final en pied n'est pas branché. Voir les guides d'installation, utilisateur et technique de cette branche.

## Actualisation dialogue, personnalité et mémoire : 2026-11-15
Consulter la [passation dialogue Low/320 et participation](../gpt6-jade/DIALOGUE-LOW320-HISTORIQUE-PARTICIPATION-20261115.md). Le nouveau prompt de caractère exact est actif sur `develop`, les propositions antérieures sont archivées. Conservation opt-in des échanges complets non résumés (SQLite v3), contexte volatile 48 messages, réponse solo systématique sur tours admissibles / groupe échantillonné 30 %. Prévision de deux variantes de réaction par intention, **sans nouveaux assets animés**.

## Suivi DevOps (15/11/2026)

**Audit de référence** : [revue DevOps develop du 15 novembre 2026](../gpt6-jade/AUDIT-DEVOPS-DEVELOP-20261115.md). La CI peut échouer malgré une analyse Gitleaks verte ; vérifier les jobs Windows/Linux sur le SHA ciblé et ne pas présenter les tests hors ligne comme une recette des périphériques ou des connecteurs.

## Contrôle P0 CI du 16 novembre 2026 (develop)

- Politique de réponse conservée : **100 % en solo vérifié, 30 % en groupe** ; sollicitation explicite prioritaire. Les suivis contextuels en groupe restent échantillonnés et ne garantissent pas une réponse.
- Tests de transport Discord vocal : échantillonnage neutralisé **dans les doubles de test seulement** pour vérifier indépendamment déplacement de canal, interruption et récupération. La présence des participants est une information en lecture seule permettant de distinguer solo/groupe, jamais une autorisation d'écoute.
- Tests Discord écrit : salons à plusieurs participants simulés explicitement pour vérifier le taux et les limites de réponses, sans supprimer la réponse automatique en salon solo.
- Twitch : le test de non-empilement des réponses initialise le participant que l'adaptateur IRC observe normalement. Aucun changement de comportement de production dans ce lot.
- Vérification GitHub Actions Windows/Ubuntu, export de publication, scripts PowerShell et scan de secrets indispensable avant toute affirmation de CI verte. Aucun test vocal matériel ni appel OpenAI réalisé par cette revue.

- Correctif Windows du test IPC Live2D : la simulation valide toujours les deux trames d'expression et de bouche, puis termine par une coupure de pipe contrôlée. L'attente auparavant non bornée du faux moteur était responsable d'annulations Windows au délai de huit minutes ; aucun runtime ni test réel de Live2D n'est remplacé.

**Vérification du 16 novembre 2026 :** [audit de réconciliation code, configuration et documentation](../gpt6-jade/RECONCILIATION-CODE-CONFIG-DOCS-20261116.md) ; distingue fonctionnalités raccordées et recette réelle encore nécessaire.
