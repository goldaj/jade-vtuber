# Jade — plan d'exécution du MVP Discord

> **Décision du propriétaire du 10 novembre 2026 :** le serveur privé est dédié
> à Jade ; elle peut interagir avec les personnes et les autres bots dans tous
> ses salons, sans validation ou liste individuelle. Les anciennes restrictions
> contraires ci-dessous sont remplacées par le [plan à jour](PLAN-4-ETAPES-20261110.md).

La [feuille de route produit](ROADMAP-MVP-DISCORD-PRODUIT-MOBILE.md) fait foi :
MVP Discord d'abord, puis produit mobile autonome après validation du MVP.
Le [découpage pratique en quatre étapes](PLAN-4-ETAPES-20261110.md) précise
l'ordre de réalisation et les critères de passage.
Développement sur `develop`, sans fusion automatique vers `main`. Aucun nom
d'activation n'est obligatoire dans une session vocale autorisée ; les règles
des transports texte ne changent pas implicitement.

## D0 — Base reproductible

Le commit `49a88e8` a été vérifié dans un worktree Windows séparé sur D:, avec
Python 3.11.1, Poetry 2.2.1 et un environnement isolé installé depuis le lock
avec les extras `discord-voice` et `vts`. `pip check`, les 135 tests hors ligne,
la compilation, la démo et le préflight sans compte ont réussi. Les 103 objets
LFS et les 202 fichiers / 23 références du manifeste ont été contrôlés.

Le test CI de scan des secrets a ensuite été stabilisé. Sur le SHA exact
`bb44d7a`, les deux CI GitHub, l'installation isolée, les 135 tests, la
compilation, la démo, le préflight sans compte et les contrôles LFS sont verts.
L'autotest du scanner et le scan local de l'histoire ne signalent aucune fuite.
**Gate D0 validé pour ce SHA** ; chaque lot ultérieur doit être vérifié sur son
propre SHA et ne peut pas réutiliser cette preuve comme résultat de tests nouveaux.

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

1. **D0** : base vérifiée au SHA ci-dessus. Conserver les preuves d'installation
   et revalider les changements ultérieurs sur leur SHA exact.
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
   Voir la [préparation et recette D3–D4](PREPARATION-D3-D4-HORS-LIGNE.md).
5. **P0–P6** : ne commencer le produit mobile sans Discord qu'après validation du
   MVP Discord par le propriétaire.

Le texte Twitch et Discord conserve sa politique actuelle. Les valeurs privées,
les transcriptions et les enregistrements ne sont jamais mis dans Git ni dans
les comptes rendus.

## Premières briques D2 — non recettées

Le contrôle d'accès vocal exige un salon, une liste privée d'utilisateurs et un
consentement explicite ; il vérifie les participants présents et révoque la
session lors des changements. Les réponses sont liées à leur session vocale ;
la rediffusion globale d'autres sources est suspendue jusqu'à un routage sûr
par source et destination. Une révocation interrompt aussi les sorties locales et OBS,
sous réserve de l’ordonnancement et du comportement des lecteurs. Ces protections
ne prouvent pas le consentement réel des personnes et le cache/les événements Discord ne constituent pas un instantané
réseau atomique. Aucune session vocale réelle n'a été engagée pour ce lot.

La segmentation PCM bornée et la décision de pertinence sont raccordées au
bridge et testées avec de l'audio synthétique et des services simulés. En salon
privé avec une seule personne, un tour terminé et intelligible peut déclencher
une réponse sans prononcer le nom. Les sources texte conservent leurs règles.
En groupe, aucun signal fiable d'adresse directe n'est encore disponible : la
politique actuelle reste silencieuse plutôt que de deviner le destinataire.

Les participants présents sont figés pour la session et chaque contrôle de
capture et de sortie revérifie le snapshot ; une modification détectée révoque
la session. Les durées, buffers et files sont bornés ; le demi-duplex suspend la
capture pendant la lecture. Il ne permet donc pas d'interrompre Jade oralement
pendant qu'elle parle. Les seuils énergétiques sont expérimentaux et le cache
Discord n'est pas atomique. Une recette vocale humaine, l'écoute physique, les
mesures de latence et la validation des cas de groupe restent nécessaires avant
de considérer le MVP comme validé.

## D1 — premiers appels et migration OpenAI à prévoir

Un essai court, sans microphone et sans nouvelle tentative automatique, a
effectué une synthèse OpenAI puis la transcription OpenAI du WAV synthétique.
Les deux appels ont réussi ; les mots attendus sont présents. L'audio comporte
environ 2,41 secondes de PCM effectif. Les durées observées des appels étaient
environ 3,47 s pour la synthèse et 2,63 s pour la transcription. Le montant
facturé n'a pas été mesuré ; ces deux appels respectent le budget minimal convenu.
Cette vérification n'est pas une recette vocale humaine ni une écoute physique.
Un troisième appel court sur le même WAV synthétique a validé `gpt-transcribe` :
les mots attendus sont présents, en 1,25 s. Ce résultat ne constitue pas une
comparaison représentative de qualité ou de coût entre modèles.

L'en-tête WAV de cet essai indiquait une taille indéterminée disproportionnée :
mesurer la durée à partir des échantillons effectivement reçus, pas uniquement du
nombre de trames déclaré. Garder cet écart à l'esprit pour l'instrumentation A/V.

Avant la migration de l'étape 1, les anciens modèles étaient annoncés retirés :

- `gpt-4o-mini-tts` : 6 janvier 2027 ; le remplacement recommandé utilise
  Realtime et ne fonctionne pas comme simple nom sur `/v1/audio/speech`.
- `gpt-4.1-mini-2025-04-14` : 14 janvier 2027 ; vérifier l'alias configuré et
  comparer qualité, coût et compatibilité avant migration du dialogue.
- `gpt-4o-mini-transcribe` : 26 février 2027 ; le guide recommande notamment
  `gpt-transcribe`, dont le contrat diffère pour la langue.

Sources officielles : [retraits OpenAI](https://developers.openai.com/api/docs/deprecations),
[synthèse vocale](https://developers.openai.com/api/docs/guides/text-to-speech),
[transcription de fichiers](https://developers.openai.com/api/docs/guides/speech-to-text).
L'étape 1 a remplacé les valeurs par défaut et testé le transport Realtime ; les
anciennes valeurs explicites restent configurables. Conserver STT/TTS chez OpenAI.
