# Construire la démo Windows

Cette démo locale présente le portrait statique r21 et utilise la classe de
dialogue du projet avec un backend simulé. La réponse répète le message ; il
n'y a aucun appel IA, audio, réseau ou connecteur. Le modèle r20 est fourni en
complément pour VTube Studio, installé séparément ; il ne s'anime pas dans la
fenêtre de la démo et ne représente pas le modèle r21 final.

Depuis Windows 64 bits avec Python 3.11 et les objets Git LFS téléchargés :

```powershell
python -m venv D:\Codex\caches\venvs\jade-demo-build
D:\Codex\caches\venvs\jade-demo-build\Scripts\python.exe -m pip install "pyinstaller==6.22.3"
D:\Codex\caches\venvs\jade-demo-build\Scripts\python.exe demo\windows\build_demo.py
```

Le script ne lit aucun fichier de configuration privé et n'embarque que la
fenêtre, ses dépendances Python automatiquement détectées, le portrait, le
dossier de modèle précisément listé, la notice et les licences. Il écrit un
ZIP daté sous `D:\Codex\outputs\jade-demo` et ses temporaires sous
`D:\Codex\tmp`. L'installation de PyInstaller peut nécessiter Internet ; la
construction et la démo n'effectuent aucun appel réseau.

Vérifier le ZIP produit, son contenu et ses sommes, puis l'extraire pour tester
`Jade-demo.exe`. L'option interne `--smoke-test` initialise Tk, charge le
portrait et vérifie une réponse simulée avant de quitter ; elle ne remplace
pas une vérification visuelle manuelle. Aucun essai de VTube Studio n'est
réalisé par cette commande.

## Contrôle du paquet construit le 3 novembre 2026

Le paquet local testé contient 1 015 fichiers et mesure environ 18,5 Mo. SHA-256
: `ac86229254d2b43e3bc3988336b05b71721d3f4f5c98c19f9390791c70c6f9df`.
Les sommes de son contenu ont été vérifiées après extraction et le test du
binaire extrait a réussi avec un PATH minimal et sans configuration privée. Un
scan du paquet et une recherche ciblée de valeurs privées connues n'ont rien
signalé ; ces contrôles ne prouvent pas l'absence de secrets inconnus. Les
modules Python compressés ont aussi fait l'objet d'un contrôle ciblé.

La fenêtre a été détectée, mais sa capture visuelle a expiré : son rendu à
l'écran reste à vérifier manuellement. VTube Studio et le modèle animé n'ont
pas été testés. Cette empreinte identifie ce paquet précis ; une reconstruction
n'a pas forcément les mêmes octets.
