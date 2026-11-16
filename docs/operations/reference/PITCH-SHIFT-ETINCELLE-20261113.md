# Étincelle : pitch +2 demi-tons — implémentation et passation Codex

**Date :** 13 novembre 2026  
**Branche :** `develop` uniquement. **Non déployé sur le PC**, pas de mesure de rendu vocal humain ou téléphonique.  
**Statut :** traitement logiciel implémenté et testé hors ligne ; activation réelle **conditionnée** à un FFmpeg compilé avec le filtre `rubberband`.

## Décision du propriétaire et objectif

Après la sélection provisoire de la voix **Étincelle** (`shimmer`, vitesse 1,25×, TTS `gpt-realtime-2.1-mini`), Goldaj a explicitement demandé d'implémenter le pitch envisagé de **+2 demi-tons** au lieu de le laisser comme simple idée. L'objectif est une voix plus aiguë **sans accélérer la durée ni déformer exagérément les formants**. Le registre et les directions d'intention validées en code restent inchangés.

**Ce que le moteur ne fait pas :** il ne modifie pas le pitch via l'API OpenAI, qui n'expose pas de paramètre natif de hauteur en demi-tons. Il transforme le **PCM local** retourné par le TTS avec un filtre audio facultatif ; aucune nouvelle requête LLM/STT/TTS facturable n'est créée.

## Chemin d'exécution actuel

```text
LLM → [INTENT:label] + texte
        │
        └→ intent_engine retire les balises, conserve Reply.intent
                        │
                        ▼
                TTS OpenAI Realtime
                    24 kHz / mono / s16le
                        │
                        ▼
             pitch_shift.py / FFmpeg rubberband
           tempo = 1 ; pitch = 2^(2/12) ≈ 1,12246
           formant = preserved ; window = short
           pitchq = speed
                        │
             24 kHz / mono / s16le
                        │
                        ▼
       Lecture locale WAV / Discord PCM / sous-titres OBS
```

Le filtre est **en aval** de la synthèse : la balise `[INTENT:...]` ne peut pas apparaître à cause de ce traitement. Les instructions `playful`, `tender` etc. sont appliquées au TTS **avant** la modification de pitch.

### Fichiers du changement

- `src/jade_runtime/pitch_shift.py` : conversion +2 demi-tons, contrôle du filtre `rubberband`, traitement asynchrone du PCM, backpressure, fermeture/cancellation et gestion WAV.
- `src/jade_runtime/config.py` : nouvelle configuration bornée `tts_pitch_semitones` (défaut `2.0`, plage `[-6, 6]`, `0` = désactivé). `JADE_TTS_PITCH_SEMITONES` dans le chargement.
- `src/utility/public_profile.py` : **allowlist mise à jour** pour que le profil TOML puisse contenir le pitch. Ce point était manquant dans le premier patch et aurait bloqué le profil `fast-openai`.
- `.env.example` et `config/profiles/fast-openai.toml` : réglages publics de l'exemple.
- `src/jade_runtime/output.py` : prise en charge de la sortie **WAV** et du **PCM progressif Discord**.
- `src/jade_runtime/early_speech.py` : même filtre pour **tout le tour**, pas un nouveau processus FFmpeg par phrase ; conserve la segmentation TTS existante.
- `tests/test_jade_pitch_shift.py` : validation mathématique, bornes, délai de démarrage (quand le filtre existe), préservation de la durée et hausse de fréquence d'une sinusoïde, repli, annulation.
- `tests/test_jade_publication_profiles.py` et `tests/test_jade_early_speech.py` : chargement de profil, précédence des réglages privés, filtre unique pour la réponse anticipée.

### Préconditions sur le PC de Terra / Codex

Vérifier d'abord le **même** `ffmpeg` que Jade lance, accessible par son `PATH`. Le filtre est optionnel dans les distributions FFmpeg : il faut une compilation avec `--enable-librubberband`.

**Windows :**
```powershell
ffmpeg -hide_banner -filters | findstr /i rubberband
```

**Linux :**
```bash
ffmpeg -hide_banner -filters | grep rubberband
```

- Si une ligne `rubberband` apparaît : le traitement peut fonctionner.
- Si aucune ligne n'apparaît ou si `ffmpeg` n'est pas accessible : Jade utilise **la voix native inchangée** (repli sans coupure ni nouvelle requête TTS). Il faut installer/choisir une **distribution FFmpeg avec le filtre** sur le PC pour entendre réellement les +2 demi-tons. Ne pas supposer que toute installation Windows fournit ce filtre.
- Un FFmpeg présent mais incapable d'exécuter les options indiquées peut entraîner une erreur du traitement audio. Tester l'exécution réelle avant de conclure que le filtre est opérationnel.
- Le traitement utilise un **processus enfant local** par réponse/turn, mais le mode early-speech mutualise ce processus sur les phrases. Aucun secret, texte d'inférence ou enregistrement audio n'est envoyé à un service tiers.
- Les réglages privés/processus peuvent remplacer le défaut `2.0`. Mettre `JADE_TTS_PITCH_SEMITONES=0` pour revenir immédiatement au timbre natif, sans changer le modèle ni la voix.

### Choix techniques et limites

1. `pitch=1.122462...` élève théoriquement la hauteur de **2 demi-tons** ; `tempo=1` vise la durée inchangée. `formant=preserved` est demandé au filtre pour limiter la modification de l'identité vocale, **sans garantie de qualité naturelle**.
2. `window=short`, `pitchq=speed` : optimisation de latence, à apprécier en écoute comparative ; une autre configuration sera possible en V2 si elle améliore nettement la qualité.
3. Les fichiers WAV non conformes au PCM 24 kHz mono restent inchangés. Le mode PCM progressif repose sur un flux valide ; si l'amont a déjà produit des octets et que le DSP échoue, **ne pas relancer le TTS facturé pour rattraper**.
4. La sortie de chaque filtre est bornée, le tube d'entrée applique une pression de retour, et un arrêt précoce termine le processus fils. Une absence du filtre entraîne une lecture **sans modification** et un avertissement local sans données audio privées.
5. Le contrôle `ffmpeg -filters` est mis en cache pendant le processus Jade. Si l'on remplace FFmpeg en cours de session, **relancer Jade** pour redétecter la disponibilité.
6. Un traitement supplémentaire peut retarder le premier son et consommer du CPU ; **aucune mesure end-to-end Discord/téléphone sur le PC réel** n'a été obtenue.
7. Le filtre cible la **hauteur et le timbre audio**, pas les instructions émotionnelles. Il peut nuire à la différence entre `playful`, `tender` etc. : refaire la recette d'intentions avec le filtre activé.

### Vérifications automatisées et recette réelle

Tests hors ligne : `poetry run python -m unittest discover -s tests -v` ; `poetry run python -m compileall -q src main.py`.

Le module contient des tests conditionnels de **DSP réellement exécuté**, mais ils sont ignorés lorsqu'un runner CI n'a pas de filtre `rubberband`. Un CI vert ne prouve donc pas forcément que l'algorithme natif a été exécuté sur un runner donné. Le scan des secrets et la CI sont à vérifier sur le dernier SHA (ne pas attribuer à ce lot les résultats d'une CI précédente).

**Recette à exécuter par Codex/Terra sur le PC :**

1. Vérifier le FFmpeg et l'absence d'override privé `JADE_TTS_PITCH_SEMITONES=0`.
2. Faire prononcer un texte identique par `shimmer` à 1,25× avec pitch **0** puis **+2**, enregistrer modèle/version, délai premier son, durée, ratio de hauteur et CPU.
3. Tester en Discord PCM progressif, puis `JADE_EARLY_VOICE=1` avec au moins deux phrases ; vérifier le maintien d'une voix naturelle et l'absence de pause entre phrases ou sous-titres incohérents.
4. Tester une coupure volontaire de diffusion et une reconnexion pour contrôler l'arrêt du FFmpeg et de la synthèse en cours.
5. Vérifier les sept intentions une à une. Comparer la naturalité et l'intelligibilité sur téléphone au témoin natif sans filtre.
6. S'il apparaît des artefacts importants ou un surcoût de latence non acceptable, revenir à **0** et documenter la mesure plutôt que d'imposer la modification.

**Critère de livraison :** code intégré sur `develop` et tests hors ligne verts ; **validation sonore produit et déploiement local restent ouverts**. Aucun merge `main` implicite.
