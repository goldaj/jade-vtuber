# Démonstrations de Jade : branche develop

## Démo Express à installer en moins de manipulations

Sous Windows 10/11, double-cliquer `Installer-Demo-Express.cmd` à la racine du clone, puis ouvrir l'entrée **Jade Demo Express** du menu Démarrer. Cela copie un petit programme PowerShell WinForms dans `%LOCALAPPDATA%\JadeDemoExpress` et crée son raccourci **sans droits administrateur**. Il utilise uniquement les composants Windows intégrés. Aucun Python, Poetry, OpenAI, Discord, Twitch, micro, Tailscale, SDK Live2D, modèle Git LFS ou compte requis.

Alternative sans installation : `Lancer-Demo-Express.cmd` depuis le clone. Les réponses sont **pré-écrites, déterministes et non IA** et le personnage est **un dessin local, pas le modèle Live2D r20/r21**. Aucun message stocké sur disque ni appel réseau. Tester « Bonjour », « Qui es-tu ? », « Avatar », « Discord ». Pour désinstaller, supprimer le dossier JadeDemoExpress dans LOCALAPPDATA et son raccourci Start Menu.

Test hors interface : `powershell.exe -NoProfile -File demo\express\Jade-Demo-Express.ps1 -SelfTest`. L'interface réelle doit être vérifiée sous Windows interactif, la CI n'affiche pas de fenêtre.

## Démo du vrai moteur avec backend simulé

Avec Python 3.11 et Poetry 2.2.1, `poetry sync --only main` puis `poetry run python main.py`. Les phrases « Mode démo » viennent de `DemoChat`, pas d'un LLM. Quitter par `/exit`. Cela permet de parcourir une requête dans le runtime sans autorisation de connecteur, sans compte ni coût.

## Démo animée IA indépendante déjà présente

`demo/reelle/` contient son guide d'installation et sa procédure de build `Installer-Jade.exe`. Cette version peut utiliser **le vrai modèle r20 et une clé OpenAI facturable**. Elle est distincte de la PWA Android et du launcher « tous supports ». Les objets LFS, la carte graphique, le son et la clé API doivent être vérifiés. La présence de scripts de construction ne garantit pas la disponibilité d'un exécutable précompilé dans le dépôt.

## Démontrer le produit complet

Le parcours utilisateur normal de `develop` est `main.py --all-channels` via le launcher Windows. Il exige tous les connecteurs et ne doit pas être appelé « démo sans prérequis ». Pour tester un système complet, suivre [INSTALLATION.md](INSTALLATION.md) puis [USER_GUIDE.md](USER_GUIDE.md). Un préflight réussi prouve seulement la configuration locale, pas un fonctionnement réel sur le téléphone, Discord ou Twitch.

La Démo Express permet donc la découverte immédiate **sans contourner la décision produit « tous les supports toujours actifs » dans la vraie Jade**.

## Différence entre démos et rendu d'intention (15/11/2026)

Le moteur réel sur `develop` sait choisir parmi deux réactions faciales et textuelles par intention avec un toggle global. La **Démo Express hors ligne** reste volontairement une simulation sans avatar Live2D et ne prétend donc pas démontrer ce comportement. La démo animée séparée `demo/reelle/` possède déjà un renderer acceptant des commandes `expression` ; ce chantier route les intentions depuis le **runtime principal** et la PWA, sans modifier la politique de facturation ni garantir une démonstration matérielle. Voir [passation et exigences des 14 motions futures](../gpt6-jade/LIVE2D-INTENT-ANIMATION-HANDOFF-20261115.md).

## Comportement dialogue réel et limites de la démo (2026-11-15)

La Démo Express simulée ne permet **pas** de conclure que les réglages `low/320`, le nouveau prompt approuvé, le journal SQLite ou les taux d'intervention ont été testés contre OpenAI/Discord/Twitch. Ces fonctions existent dans le runtime `develop`, pas nécessairement dans les simulateurs. Les animations futures à deux réactions par intention sont un chantier documentaire, non un ajout d'assets. Voir [passation dialogue](../gpt6-jade/DIALOGUE-LOW320-HISTORIQUE-PARTICIPATION-20261115.md).

## Vérifications CI et produit (15/11/2026)

**Audit de référence** : [revue DevOps develop du 15 novembre 2026](../gpt6-jade/AUDIT-DEVOPS-DEVELOP-20261115.md). La Démo Express hors ligne confirme uniquement son parcours simulé. Ni une démo réussie, ni un scan de secrets vert ne valident les connexions Twitch/Discord, la mémoire SQLite, la PWA ou le moteur de voix réel. Pour l'usage complet, attendre une suite Ubuntu/Windows verte au commit de déploiement et une recette matérielle spécifique.

## Contrôle P0 CI du 16 novembre 2026 (develop)

- Politique de réponse conservée : **100 % en solo vérifié, 30 % en groupe** ; sollicitation explicite prioritaire. Les suivis contextuels en groupe restent échantillonnés et ne garantissent pas une réponse.
- Tests de transport Discord vocal : échantillonnage neutralisé **dans les doubles de test seulement** pour vérifier indépendamment déplacement de canal, interruption et récupération. La présence des participants est une information en lecture seule permettant de distinguer solo/groupe, jamais une autorisation d'écoute.
- Tests Discord écrit : salons à plusieurs participants simulés explicitement pour vérifier le taux et les limites de réponses, sans supprimer la réponse automatique en salon solo.
- Twitch : le test de non-empilement des réponses initialise le participant que l'adaptateur IRC observe normalement. Aucun changement de comportement de production dans ce lot.
- Vérification GitHub Actions Windows/Ubuntu, export de publication, scripts PowerShell et scan de secrets indispensable avant toute affirmation de CI verte. Aucun test vocal matériel ni appel OpenAI réalisé par cette revue.

- Correctif Windows du test IPC Live2D : la simulation valide toujours les deux trames d'expression et de bouche, puis termine par une coupure de pipe contrôlée. L'attente auparavant non bornée du faux moteur était responsable d'annulations Windows au délai de huit minutes ; aucun runtime ni test réel de Live2D n'est remplacé.
