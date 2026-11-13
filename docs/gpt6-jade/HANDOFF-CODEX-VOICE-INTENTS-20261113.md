# Passation Codex — Jade Étincelle et moteur d'intentions vocales (13 novembre 2026)

**État : travail implémenté sur `develop`, pas sur `main` ; code testé hors ligne, écoute et déploiement local NON validés.**

**À lire en priorité :** [spécification des trois voix et contrat détaillé](VOICE-PROFILES-20261113.md), [audit PO/architecture/QA/audio](REVIEW-INTENT-ETINCELLE-20261113.md). Ce document est le **point de reprise opérationnel**. Les fichiers de migration et les anciens HANDOFF/TASKS conservent des états **historiques** : ils ne prévalent pas sur cette passation pour ce chantier.

## Pourquoi ce chantier existe

Décision utilisateur : Jade doit avoir une voix **jeune adulte, aiguë, dynamique et espiègle**, avec parfois une affection timide envers Goldaj, sans infantilisation ni surjeu. **Étincelle** est retenue provisoirement ; **Friponne** et **Rosée** restent des alternatives documentées. Le modèle d'inférence choisit une intention **depuis un vocabulaire fermé**, l'écrit en préfixe strict, puis le runtime la retire de TOUTE sortie et pilote la consigne de prosodie vocale correspondante.

**Priorités produit :** faible latence, coût raisonnable, naturalité en français et fidélité exacte au texte émis par Jade. Pas de second LLM de classification, ni de synthèse supplémentaire simplement pour décider d'une émotion.

## Ce qui a été modifié et où

| Fichier | Rôle |
| --- | --- |
| `src/jade_runtime/config.py`, `.env.example`, `config/profiles/fast-openai.toml` | Défauts publics Étincelle : `JADE_TTS_VOICE=shimmer`, `JADE_TTS_SPEED=1.25`. Le STT `gpt-transcribe` et le TTS `gpt-realtime-2.1-mini` restent inchangés. |
| `src/jade_runtime/intent_engine.py` | Source de vérité : prompt de contrat, registre fermé, directions TTS statiques, parseur plein texte/streaming et neutralisation des métadonnées. |
| `src/jade_runtime/dialogue.py` | Ajoute le contrat au prompt système quel que soit le prompt utilisateur local ; parse la réponse LLM, retire les balises AVANT le `SentenceAccumulator`, place l'intention dans `Reply.intent` et le texte propre dans l'historique. |
| `src/jade_runtime/messages.py` | `Reply.intent` (neutre par défaut), séparé de `Reply.text` qui reste destiné à l'affichage/parole. |
| `src/jade_runtime/orchestrator.py` et `early_speech.py` | Propage une intention unique à la synthèse anticipée par phrases et la fixe avant le premier segment ; aucune mutation de l'émotion au cours de la lecture. |
| `src/jade_runtime/output.py` et `openai_services.py` | Propage l'intention au TTS Realtime dans les voies WAV, PCM progressif et early speech ; conserve les adaptateurs des anciens tests. |
| `src/jade_runtime/realtime_tts.py` | `session.update.instructions` reçoit uniquement la consigne statique autorisée correspondant au label, en demandant une voix jeune-adulte française et la lecture fidèle. |
| `tests/test_jade_intent_engine.py` | Contrat de parsing, fragments, tags parasites, historiques, routage réel des paramètres vers les doubles Realtime et réutilisation WebSocket. |

**Attention aux dépendances locales :** un `.env` privé, `JADE_SECRETS_FILE`, `JADE_PROFILE_FILE` ou des variables processus peuvent encore imposer `coral` / 1,5×, même si `develop` propose `shimmer` / 1,25×. Ne jamais publier les fichiers ou valeurs privés.

## Schéma et exemple

LLM :
```text
[INTENT:playful] Encore une idée, Goldaj ? Je sens venir les ennuis !
```
Sorties Discord/OBS/Twitch/console/API, historique et texte donné au TTS :
```text
Encore une idée, Goldaj ? Je sens venir les ennuis !
```
Métadonnée interne : `Reply.intent = "playful"`.

Intention **unique sur toute la réponse** ; une V2 par phrase est envisageable mais **non livrée**. Les labels permis sont `neutral`, `playful`, `excited`, `curious`, `tender`, `reassuring`, `serious`. Une valeur inconnue ou une balise absente donne `neutral` ; des balises `INTENT` répétées, même coupées entre des fragments, sont filtrées. Un préfixe `INTENT` inachevé provoque un refus plutôt que de le divulguer. Ne jamais transmettre une consigne vocale libre générée par le LLM au TTS ; utiliser uniquement les directions statiques du module.

Le mode `JADE_EARLY_VOICE` est **désactivé par défaut**. S'il est activé localement, le streaming par phrases conserve ses propres limites et ne doit pas dupliquer les synthèses.

## Ce qui est VÉRIFIÉ

- Tests hors ligne GitHub Actions sur code au SHA `c6456f0181f36f12aed3e179a0ba024d0d1f8889` : [Windows + Ubuntu réussis](https://github.com/goldaj/jade-vtuber/actions/runs/43485778125) ; **422 tests dont 2 ignorés** observés sur Ubuntu.
- Les corrections de filtrage des tags, la sélection et la propagation d'intention, la voix/vitesse par défaut et les échanges de prosodie sur une connexion Realtime mockée sont couverts.
- Sur le SHA documentaire ultérieur `f801a09a1011a6d89d3379654ce1e3d562e4bbbd`, [CI Windows + Ubuntu réussie](https://github.com/goldaj/jade-vtuber/actions/runs/43486194055) et [scan de secrets réussi](https://github.com/goldaj/jade-vtuber/actions/runs/43486194147).
- **Ne pas attribuer ces résultats aux commits plus récents sans contrôler leurs propres checks.** Les tests ne font pas d'appels API payants.

## Ce qui N'EST PAS VÉRIFIÉ : points de décision PO

1. **L'audibilité réelle des émotions** : Realtime TTS accepte des instructions textuelles, mais aucun catalogue officiel ne garantit que la voix `shimmer` distingue les sept intentions. Tester chacune en français, sur Discord/téléphone, et retirer ou fusionner les étiquettes non distinguables.
2. **Qualité de la diction et fidélité des mots parlés** : les instructions de lecture fidèle ne sont pas une garantie fournisseur. Écouter une réponse naturelle, taquine, sérieuse et brièvement tendre, sans infantilisation.
3. **Latence/cout réels** : mesurer fin de parole → premier son, coût par tour, nombre de requêtes TTS, notamment avec `JADE_EARLY_VOICE=1`. Le tag ajoute des tokens de sortie et une attente de préfixe.
4. **Pitch +2 demi-tons** : non codé. Aucun réglage numérique natif du pitch dans cette configuration. Un traitement PCM futur pourrait ajouter des artefacts et de la latence ; ne pas l'activer sans décision et recette.
5. **Configuration et redémarrage du PC** : pas réalisés par ce chantier. GitHub vert n'est PAS équivalent à un nouveau processus Jade exécutant le code.
6. **Intention par phrase** : pas prise en charge. Le choix d'une intention par réponse est une contrainte assumée ; concevoir un protocole versionné si le besoin évolue.

## À faire ensuite par Codex (ordre conseillé)

1. Mettre à jour la copie locale en partant de `develop`, vérifier les travaux locaux non fusionnés de Terra AVANT toute opération Git ; ne pas écraser les changements locaux et ne pas modifier `main` sans accord renouvelé.
2. Vérifier le profil réellement chargé (n'afficher aucune clé), puis exécuter `poetry run python -m compileall -q src main.py` et `poetry run python -m unittest discover -s tests -v`.
3. Faire une recette contrôlée sur Discord/téléphone : comparer la même phrase avec les **sept intentions** et `shimmer`/1,25×, puis `playful` → `tender` sur deux tours et tester l'interruption.
4. Observer les coûts, latence et exactitude des mots ; recueillir l'appréciation produit avant une fusion `main` ou un déploiement définitif.
5. En cas d'écart, corriger la cause dans le module isolé et compléter les tests ciblés, sans ajouter une couche de classification ou plusieurs synthèses par défaut.

**Règle d'exploitation :** la CI prouve la cohérence logicielle simulée ; **elle ne certifie ni l'intonation, ni la qualité sonore, ni Discord en conditions réelles.** Documenter toute observation réelle séparément.
