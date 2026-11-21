# Jade Démo Express (Windows)

Double-cliquer **Installer-Demo-Express.cmd** à la racine du dépôt sous Windows 10/11. L'installateur copie l'interface locale dans le profil utilisateur et crée l'entrée **Jade Demo Express** au menu Démarrer. Sans droits administrateur, Python, Poetry, Discord, OpenAI, SDK Live2D, microphone, carte graphique spéciale ni compte externe. Windows PowerShell 5.1 et WinForms font partie de Windows.

Alternative sans installation : double-cliquer **Lancer-Demo-Express.cmd** depuis le clone. Pour désinstaller, fermer la démo, supprimer le dossier local JadeDemoExpress dans LOCALAPPDATA et son raccourci du menu Démarrer. Aucun message n'est conservé sur disque par ce programme.

Les réponses de Jade sont **simulées et déterministes**, le portrait est dessiné par Windows. **Ce n'est pas une preuve de fonctionnement IA, voix, Live2D ou connexion Discord/Twitch.** Il s'agit de la **seule démo distribuée** sur `develop` : les anciennes démos `demo/reelle/` et `demo/windows/` ont été retirées. Pour utiliser Jade réelle (ce n'est pas une deuxième démo), voir [le guide d'installation](../../docs/handbook/INSTALLATION.md) et [le guide des démonstrations](../../docs/handbook/DEMO.md).

Test sans interface : powershell.exe -NoLogo -NoProfile -File demo/express/Jade-Demo-Express.ps1 -SelfTest. Les tests automatiques ne remplacent pas un essai visuel sous Windows.
