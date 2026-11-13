# Construire la démonstration Windows de Jade

La distribution visée est un ZIP contenant un installateur Windows 64 bits et
un guide d'utilisation. L'installateur installe une application par utilisateur
sans droits administrateur : dialogue et voix OpenAI avec clé fournie par le
visiteur, et modèle Live2D r20 animé. Le r21 est une source de travail distincte,
pas un modèle final exporté dans ce paquet. Le rendu, les services et l'installation
doivent être vérifiés sur le paquet construit avant de le partager.

## Préparer l'environnement de construction

Sur Windows 64 bits, avec Python 3.11 64 bits et Git LFS :

```powershell
$env:TEMP = 'D:\Codex\tmp'
$env:TMP = 'D:\Codex\tmp'
$env:PIP_CACHE_DIR = 'D:\Codex\caches\pip'
py -3.11 -m venv D:\Codex\caches\venvs\jade-reelle-build
D:\Codex\caches\venvs\jade-reelle-build\Scripts\python.exe -m pip install `
  pyinstaller==6.22.3 live2d-py==1.0.0 pygame==2.6.1 PyOpenGL==3.1.10 `
  Pillow==13.0.0 numpy==2.4.6 openai==3.42.1 sounddevice==0.5.6 `
  python-decouple==3.8 python-dotenv==1.2.4 websockets==16.1.1
git lfs pull
python jade-modeling/verify_assets.py
```

Ces versions définissent les dépendances directes du build ; les dépendances
transitives ne sont pas intégralement verrouillées par cette commande. Installer
les paquets nécessite Internet. Vérifier les conditions de redistribution des
dépendances, notamment le [SDK Live2D Cubism](https://www.live2d.com/en/sdk/license/),
pour le contexte effectif avant publication. La licence du wrapper `live2d-py`
ne remplace pas les conditions du SDK Live2D.

Le texte LGPL 2.1 associé à pygame est conservé dans `licenses/pygame-LGPL-2.1.txt`,
issu de [pygame 2.6.1](https://github.com/pygame/pygame/blob/2.6.1/docs/LGPL.txt).
Le build vérifie son SHA-256 et l'inclut avec les notices trouvées dans les wheels.

Le script attend Inno Setup 7.1.1 sous
`D:\Codex\tools\InnoSetup-7.1.1\ISCC.exe`. Récupérer l'outil depuis
[son éditeur](https://jrsoftware.org/isdl.php) et vérifier la signature avant
installation. Le compilateur peut être installé en mode portable sur D:.

## Construire et contrôler

```powershell
D:\Codex\caches\venvs\jade-reelle-build\Scripts\python.exe demo\reelle\build_reelle.py
```

Le script utilise `D:\Codex\tmp` pour les fichiers temporaires,
`D:\Codex\caches` pour les caches et crée un nouveau ZIP sous
`D:\Codex\outputs\jade-demo`. Il construit deux répertoires PyInstaller :
`Jade.exe` sans console et `renderer/Jade-renderer.exe` avec console masquée
lors de son lancement par l'interface. Seul le renderer embarque la copie
intacte des ressources r20, sous `_internal/assets/model`. Les ressources du
modèle sont copiées selon une liste explicite, puis leurs SHA-256 sont comparés
aux originaux ; l'absence d'objets LFS provoque un échec.
Le `prompt_chat.txt` public du dépôt est intégré à l'interface pour préserver
la personnalité de Jade : le build le contrôle par le scanner de texte du
projet avant de le copier. Le contrôle spécialisé des secrets reste nécessaire.

Le script refuse des noms usuels de fichiers privés et les marqueurs PEM de
clés privées dans la copie à installer. Il ne lit pas le coffre privé ni les
fichiers `.env` du projet. Les variables de services sont retirées de
l'environnement de construction. Ce contrôle est limité : effectuer aussi un
scan dédié des fichiers et des modules Python empaquetés, ainsi qu'une recherche
des valeurs privées connues, sans jamais les afficher.

La construction seule ne valide pas le fonctionnement. Avant livraison :

1. Vérifier les licences, le contenu du ZIP et son fichier SHA-256 ; extraire
   l'installateur et le guide dans un dossier neuf.
2. Installer pour un utilisateur Windows non administrateur, sur un poste propre
   ou un environnement de test représentatif ; ne pas écraser une installation
   personnelle existante. Vérifier que la désinstallation ne touche qu'à cette
   installation et ne supprime aucune configuration personnelle préexistante.
3. Depuis l'installation, exécuter les autotests hors réseau :
   `Jade.exe --dependencies-smoke-test` vérifie les imports OpenAI, son et
   WebSocket sans appel réseau ni activation des périphériques ;
   `Jade.exe --smoke-test` et
   `renderer\Jade-renderer.exe --renderer --smoke-test` vérifient le démarrage
   graphique. Contrôler aussi réellement l'affichage et le mouvement de l'avatar,
   puis son retour au repos.
4. Vérifier la saisie masquée de la clé du visiteur, son absence du paquet,
   des journaux et de Git, ainsi que les erreurs compréhensibles sans clé et
   sans réseau. Tester séparément dialogue, son et micro seulement avec accord
   explicite et budget minimal ; des doubles ne prouvent pas ces appels réels.
5. Suivre le `GUIDE-DEMO.md` livré comme un nouveau visiteur ; noter tout
   prérequis, échec et fonctionnalité non testée. Vérifier le comportement sur
   une seconde machine si possible : OpenGL, pilotes et périphériques varient.

Les modèles OpenAI configurés peuvent être retirés ou modifiés : consulter
le plan du projet et tester une migration avant leur date de retrait. Cette
notice n'affirme pas que la démo, l'animation ou les services ont été validés.
