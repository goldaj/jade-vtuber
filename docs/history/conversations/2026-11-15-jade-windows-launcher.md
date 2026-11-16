# Jade : launcher de demarrage Windows (15 novembre 2026)

**Demande utilisateur (verbatim) :** « J'aimerais qu'on crée aussi un launcher qui permette de lancer la dernière version de Jade sur le pc local de Jade. Où on choisirait la branche et ça lancerait l'ensemble des logiciels nécessaires pour avoir Jade qui tourne. Pas besoin de faire un truc trop générique, juste que ça fonctionne sur mon poste. »

**Reformulation / choix d'implémentation :** application personnelle Windows, sans empaquetage générique. Installation hors clone dans `D:\Jade\launcher`, sélection d'une branche Git distante, mise à jour fast-forward uniquement, préparation des dépendances Poetry et Git LFS selon le mode, préflight local sans réseau puis démarrage du moteur Jade dans une console. Modes : Discord texte/vocal + avatar r20 ; Discord texte ; micro local ; mobile privé ; Discord+mobile ; simulation. Discord Desktop, OBS et VTube Studio ne sont pas lancés arbitrairement puisque le runtime n'en dépend pas en mode avatar autonome. Tailscale Serve déjà configuré sur PC n'est pas modifié et le VPS trading est exclu.

**Travail à distance :** branche `feat/jade-windows-launcher-20261115` créée depuis le `develop` qui intègre l'ensemble des derniers lots. Fichiers `Installer-Launcher-Jade.cmd`, `scripts/install-jade-launcher.ps1`, `scripts/jade-launcher.ps1`, `scripts/jade-runner.ps1`, documentation `docs/operations/reference/LAUNCHER-WINDOWS-20261115.md`, contrôle syntaxique PowerShell en CI Windows.

**État de validation :** absence d'accès au PC de l'utilisateur et à un PowerShell Windows dans l'environnement de l'intervention. La PR #13 et sa CI Windows/Linux (parseur PowerShell inclus) ainsi que le scan de secrets sont verts sur le SHA de la branche ; le lot a été fusionné dans `develop` sans toucher à `main`. Aucun service, appel facturé, route réseau ou logiciel n'a été lancé sur le PC. Test matériel à conduire par le propriétaire/Codex. Ceci est un résumé des messages accessibles et non une transcription exhaustive.

## Correction explicite du propriétaire (même date)

> « Non mais attends on ne doit pas choisir le mode de fonctionnement de Jade. Ça doit TOUJOURS fonctionner sur TOUS les supports. On ne doit pas en prioriser par rapport à l'autre. Et c'est Jade qui va ensuite définir dans quel ordre elle répond à quoi »
>
> « Et assure toi de modifier tout le code de Jade pour que ça fonctionne comme ça, pas que le launcher »

**Décision courante :** annule la sélection des profils de la PR #13, sans annuler le choix de branche Git. Nouveau lot `fix/jade-unified-always-on-20261115` : `main.py --all-channels` active tous les connecteurs ensemble et le moteur arbitre en cas de demandes concurrentes, sans poids fixe par plateforme. Préflight obligatoire, impossibilité de masquer des interfaces non configurées. La correction inclut la politique d'ordre, l'écoute microphone et l'isolation des réponses privées. Le détail opérationnel et les limites sont décrits dans `docs/operations/reference/LAUNCHER-WINDOWS-20261115.md`. Aucun effet sur le PC physique sans mise à jour locale.
