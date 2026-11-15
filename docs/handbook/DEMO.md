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
