# Launcher Windows personnel pour Jade

**Date : 15 novembre 2026.** Lot isolé \`feat/jade-windows-launcher-20261115\`, ciblant \`develop\`, sans intervention sur \`main\`, le PC physique ni le VPS Hyperliquid.

## But et installation (sur le PC Windows Jade)

Depuis le clone Git de Jade sur **D:**, exécuter une fois \`Installer-Launcher-Jade.cmd\` (double-clic). Il installe :

- \`D:\Jade\launcher\Lancer-Jade.cmd\` : double-clic quotidien, raccourci Bureau possible ;
- \`D:\Jade\launcher\JadeLauncher.ps1\` : interface Windows avec choix de branche et mode ;
- \`D:\Jade\launcher\JadeRunner.ps1\` : console du vrai runtime Jade ;
- \`D:\Jade\launcher\launcher.json\` : **uniquement** chemin du dépôt et chemin optionnel du fichier privé, **jamais les tokens**.

Le launcher reste **hors Git** : changer de branche ne fait pas disparaître le programme. Après une évolution du launcher lui-même, relancer l'installateur de la branche contenant la nouvelle version. Le chemin de dépôt est déduit de l'emplacement réel de l'installateur, pas deviné.

Prérequis : **Windows PowerShell 5.1**, Git (+ Git LFS pour l'avatar), Python 3.11 compatible avec le projet, Poetry 2.2.1, FFmpeg/ffplay pour les modes audio requis, configuration privée Jade préexistante. Pour la PWA, Tailscale Serve doit être **configuré séparément sur le PC**, avec l'identité propriétaire, le HTTPS et le SDK Web conforme à sa licence. Ne jamais renseigner les jetons dans le launcher ou Git.

## Utilisation

1. Ouvrir \`D:\Jade\launcher\Lancer-Jade.cmd\`.
2. Sélectionner une branche distante. **Actualiser Git** interroge \`origin\` sans changer la branche ; le lancement refait un \`fetch\`.
3. Sélectionner un mode : Discord voix + texte + avatar (**par défaut**) ; Discord texte ; micro local + avatar ; application mobile privée ; Discord + avatar + mobile ; ou démo hors ligne.
4. Conserver les options Poetry et Git LFS pour le premier lancement ou après un changement de branche. Sur les suivants, on peut les désactiver si l'environnement est déjà installé.
5. Si \`JADE_SECRETS_FILE\` n'est pas défini durablement dans Windows et que les secrets ne sont pas dans \`.env\` local ignoré par Git, choisir explicitement le fichier privé. Seul son **chemin** est mémorisé.
6. Cliquer **Mettre à jour et lancer Jade**. La console de Jade s'ouvre si le préflight réussit. **Ctrl+C** dans cette console arrête le moteur ; fermer ensuite la console avant de relancer ou changer de branche.

La fenêtre Console ne simule rien : elle exécute \`poetry run python main.py\` avec les flags du profil. Les modes **live** sont explicitement sélectionnés et peuvent facturer OpenAI. Le mode **Démo hors ligne** n'ouvre aucun service ; écrire dans sa console puis \`/exit\`.

## Ce que le lanceur fait / ne fait pas

- \`git fetch --prune origin\`, vérifie l'absence de modifications locales ou fichiers non suivis, puis \`git switch\` et \`git merge --ff-only origin/<branche>\`. Aucun \`reset --hard\`, nettoyage, force-push ni écrasement de changements locaux.
- Lance \`poetry sync --only main\` avec les extras du profil choisi, récupère Git LFS pour les modes avatar, puis exécute \`main.py --preflight\` avec **exactement les mêmes options** (aucun accès fournisseur dans le préflight).
- Lance Python dans **une console séparée** pour laisser les logs visibles. Le runner quitte après confirmation, ce qui évite les consoles qui disparaissent avant lecture d'une erreur.
- Pour Discord, l'application Discord de bureau n'est pas nécessaire au bot ; le runtime se connecte directement. Pour l'avatar, \`--avatar\` lance son moteur r20, **pas** VTube Studio. Le launcher ne démarre donc pas arbitrairement OBS, Discord Desktop ou Steam.
- Pour mobile, le launcher **ne modifie jamais** la configuration Tailscale Serve, les routes réseau, les pare-feu ni le VPS trading. Il lance seulement le serveur mobile privé de Jade, dont la configuration existante reste nécessaire.
- La fenêtre ne ferme pas la console par kill forcé pour éviter de laisser Jade et sa SQLite dans un état incertain. Arrêt par Ctrl+C.

## Limitations et recette du poste

Le code est livré à distance, **sans exécution sur Windows, ni Discord/Tailscale actif, ni tests micro/audio/graphique**. Sur le PC, vérifier :

1. Installation hors Git, raccourci et fonctionnement après sélection d'une autre branche.
2. Liste des branches, erreurs si dossier local modifié, refus de fusion non fast-forward, aucun changement de \`main\` automatique.
3. Préflight sans appel externe, gestion d'un fichier privé hors Git et d'une dépendance manquante.
4. Profil Discord vocal + avatar avec config active : démarrage, connexion, bouche r20 et Ctrl+C ; tests locaux et coûts contrôlés.
5. Profil mobile et HTTPS Tailscale déjà configuré : identité propriétaire, jeton privé, rendu Android puis arrêt.
6. **Tester les changements de branche uniquement après avoir fermé la console de Jade** pour éviter les processus et modules de versions mixtes.

Une réussite CI ou de syntaxe ne prouve pas l'usage réel sur le PC. Les profils historiques peuvent avoir des flags / dépendances incompatibles : dans ce cas, le préflight doit bloquer plutôt que tenter une migration forcée. L'installation Poetry s'exécute sur le poste et peut télécharger des paquets ; c'est distinct des appels OpenAI.

## Passation à Codex

Code : \`scripts/jade-launcher.ps1\`, \`scripts/jade-runner.ps1\`, \`scripts/install-jade-launcher.ps1\`, \`Installer-Launcher-Jade.cmd\`.

Points à examiner en recette Windows : gestion PowerShell 5.1 de stderr natif, séparation des arguments de \`Start-Process\` avec chemins contenant des espaces, comportement de Ctrl+C, présence de Git/Poetry dans le PATH, branch checkout si fichiers non suivis, et absence de collision avec les processus Jade démarrés hors launcher. Ne pas toucher aux secrets ni annoncer un déploiement matériel avant observation.
