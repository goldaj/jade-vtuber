# Démonstration de Jade — develop

## Démo Express (seule démonstration conservée)

Sous Windows 10/11, double-cliquer `Installer-Demo-Express.cmd` à la racine du clone. L'installation crée une entrée **Jade Demo Express** dans le menu Démarrer sans droits administrateur, Python, Poetry, OpenAI, Discord, Twitch, micro, Tailscale, SDK Live2D ou modèle Git LFS. On peut aussi lancer `Lancer-Demo-Express.cmd` sans installation.

Les réponses sont **simulées, déterministes, sans IA et sans accès réseau**. Le personnage est un dessin Windows local, pas le vrai modèle animé r20/r21. Aucun message n'est stocké sur disque. Pour désinstaller, supprimer `%LOCALAPPDATA%\JadeDemoExpress` et le raccourci du menu Démarrer.

Autotest sans interface : `powershell.exe -NoProfile -File demo\express\Jade-Demo-Express.ps1 -SelfTest`. La CI ne remplace pas un essai visuel Windows.

## Produit Jade complet (ce n'est pas une démo autonome)

Le runtime Python reste lancé par `main.py --all-channels` avec les prérequis et canaux réels décrits dans [INSTALLATION.md](INSTALLATION.md) et [USER_GUIDE.md](USER_GUIDE.md). Son renderer Live2D r20 est désormais dans `src/jade_runtime/avatar_renderer.py`, et non dans une ancienne démonstration. Le simple `poetry run python main.py` utilise toujours un backend conversationnel simulé à des fins de diagnostic.

Les anciennes démos `demo/reelle/` et `demo/windows/`, ainsi que leurs guides de build, ont été retirées de `develop` à la demande du propriétaire. Elles restent récupérables dans l'historique Git sans maintenir des builds concurrents.

Voir l'[état des fonctions](BRANCH_STATE.md) et les [améliorations envisagées](../ameliorations/README.md).
