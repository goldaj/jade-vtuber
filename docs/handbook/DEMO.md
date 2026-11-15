# Démonstrations : branche main

## 1. Démo Express : installation Windows la plus simple

**Public :** un visiteur qui vient de cloner Jade et veut voir une interface sans installer l'écosystème des connecteurs.

1. Cloner le dépôt ou recevoir son dossier de sources.
2. Depuis l'explorateur Windows, double-cliquer `Installer-Demo-Express.cmd` à la racine.
3. Ouvrir **Jade Demo Express** depuis le menu Démarrer.
4. Taper « Bonjour », « Qui es-tu ? » ou « Avatar ». Une réponse de démonstration s'affiche.

**Prérequis : Windows 10/11 avec Windows PowerShell 5.1 / .NET WinForms**, présent par défaut. Pas de compte, clé OpenAI, Python, Poetry, Discord, carte graphique 3D, microphone, SDK propriétaire ou réseau. Sans installation, double-cliquer `Lancer-Demo-Express.cmd` depuis le clone.

**Ce que la démo ne fait PAS :** aucune inférence IA, aucune synthèse vocale, aucun avatar Live2D réel, aucune connexion mobile/Discord/Twitch, aucune sauvegarde des discussions. C'est un **outil de découverte du flux et du visuel**, pas une preuve de fonctionnalité des services du moteur complet.

Installation dans le profil utilisateur `%LOCALAPPDATA%\JadeDemoExpress`, raccourci menu Démarrer ; aucun accès administrateur requis. Désinstallation manuelle : supprimer ce dossier et son raccourci du menu Démarrer. Le lancement est local ; vérifier la provenance du clone avant d'exécuter des scripts PowerShell.

Test sans interface (Windows) :
~~~powershell
powershell.exe -NoLogo -NoProfile -File demo\express\Jade-Demo-Express.ps1 -SelfTest
~~~

## 2. Démo console réellement intégrée au moteur

**Prérequis :** Python 3.11 et Poetry 2.2.1 ; aucun secret.

~~~powershell
poetry sync --only main
poetry run python main.py
~~~

L'utilisateur peut discuter dans le terminal ; le backend `DemoChat` produit des réponses déterministes de type « Mode démo ». C'est utile pour tester la file, la session et l'interface CLI, pas le raisonnement IA.

## 3. Démo Live2D animée + IA déjà présente

Le projet comprend un **autre produit de démonstration** dans `demo/reelle/` avec son propre installateur Windows construit par le projet. Guide : [GUIDE-DEMO.md](../../demo/reelle/GUIDE-DEMO.md). Construction : [README-BUILD.md](../../demo/reelle/README-BUILD.md). Requiert un compte API OpenAI avec clé personnelle et budget pour les réponses effectives. Le modèle animé r20, les appels STT/TTS et le matériel doivent être testés sur le PC. **Le dépôt cloné n'implique pas qu'un exécutable Windows déjà compilé soit disponible.**

L'ancienne démo statique Tk/PyInstaller `demo/windows/` existe aussi et peut être reconstruite ; elle ne doit pas être confondue avec le modèle Live2D complet.

## 4. Critères de recette avant publication

- Démo Express : installation propre Windows 10/11, aucune permission administrateur, aucune connexion réseau, auto-test, rendu visuel de la fenêtre, désinstallation.
- Console : préflight, entrée/sortie, absence d'appels API.
- Démo réelle : licence, dépendances embarquées, démarrage sans fuite de secrets, clé API demandée en session, animation, texte, micro avec consentement, coûts et arrêt.
- Ne pas annoncer une recette physique sur la base des seuls tests GitHub Actions.
