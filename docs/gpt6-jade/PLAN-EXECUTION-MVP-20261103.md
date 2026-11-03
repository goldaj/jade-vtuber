# Jade — plan d'exécution du MVP Discord

La [feuille de route produit](ROADMAP-MVP-DISCORD-PRODUIT-MOBILE.md) fait foi :
MVP Discord d'abord, puis produit mobile autonome après validation du MVP.
Développement sur `develop`, sans fusion automatique vers `main`. Aucun nom
d'activation n'est obligatoire dans une session vocale autorisée ; les règles
des transports texte ne changent pas implicitement.

## D0 — Base reproductible

Le commit `49a88e8` a été vérifié dans un worktree Windows séparé sur D:, avec
Python 3.11.1, Poetry 2.2.1 et un environnement isolé installé depuis le lock
avec les extras `discord-voice` et `vts`. `pip check`, les 135 tests hors ligne,
la compilation, la démo et le préflight sans compte ont réussi. Les 103 objets
LFS et les 202 fichiers / 23 références du manifeste ont été contrôlés.

La CI de tests de ce SHA est verte sur Windows et Linux. Le nouveau test CI de
scan des secrets présente une intermittence en cours de correction ; tant que
sa nouvelle exécution n'est pas verte, le gate D0 global reste **en cours**.
Le scan local de ce SHA ne signale aucun secret.

L'exécutable `poetry` présent sur le PATH système est en version 2.0.1. La
version 2.2.1 effectivement utilisée est dans l'environnement d'outillage sur
D:. Une copie vérifiée de `ffmpeg`, `ffplay` et `ffprobe` se trouve dans
`D:\Codex\tools\ffmpeg-2025-02-20\bin` ; elle peut être ajoutée au PATH de
la session ou de la configuration PyCharm, sans modifier les autres services.

Pour une nouvelle installation Windows, sélectionner Python 3.11, configurer
les caches et environnements virtuels sur D:, installer Git LFS, puis dans le
dépôt lancer `git lfs pull` et, avec Poetry 2.2.1 :

```powershell
poetry sync --only main -E discord-voice -E vts
poetry run python -m unittest discover -s tests -v
poetry run python -m compileall -q src main.py
poetry run python main.py --preflight
poetry run python jade-modeling/verify_assets.py
```

Le préflight étendu sans configuration privée signale normalement l'absence de
clés ou d'autorisations ; il ne valide pas une connexion réelle. Les chemins
concrets d'interpréteur, de secrets et les identifiants restent locaux et hors
de ce document public.

## Suite et gates

1. **D0** : rendre le scan CI déterministe et confirmer les deux CI au SHA exact
   intégrant tous les correctifs ; conserver les preuves de l'installation.
2. **D1** : mesurer les étapes de dialogue et de voix OpenAI, puis effectuer une
   courte recette audio réelle convenue avec le propriétaire. Aucun micro physique
   ni appel facturable ne doit être présenté comme testé par une simulation.
3. **D2** : d'abord autorisation/consentement par participant et isolation des
   sessions ; ensuite segmentation complète des tours et décision de pertinence
   vocale sans nom obligatoire. Tester l'arrêt, l'anti-écho et le routage sûr avant
   toute recette d'un salon vocal réel avec les participants informés.
4. **D3–D5** : valider VTube Studio, la visibilité par partage manuel Discord,
   puis stabiliser et documenter. L'avatar et le téléphone exigent une recette
   physique ; leur bon fonctionnement ne découle pas des tests automatisés.
5. **P0–P6** : ne commencer le produit mobile sans Discord qu'après validation du
   MVP Discord par le propriétaire.

Le texte Twitch et Discord conserve sa politique actuelle. Les valeurs privées,
les transcriptions et les enregistrements ne sont jamais mis dans Git ni dans
les comptes rendus.
