# Jade — trois profils vocaux à évaluer (propositions, non implémentées)

**Date :** 13 novembre 2026  
**Statut au 13 novembre (dernière décision) :** Étincelle sélectionnée en configuration **publique par défaut** ; moteur d'intention implémenté ; rendu réel non validé sur téléphone, et configuration privée potentiellement prioritaire. Friponne et Rosée conservées.  
**Branche de travail :** `develop` ; code et défauts publics modifiés, **aucun déploiement du PC ni changement garanti de la configuration privée**.

## 1. Contexte et objectif produit

Source de personnalité : [`prompt_chat.txt`](../../prompt_chat.txt), identique sur `main` et `develop` lors de l'étude.

Jade est un personnage virtuel de VTuber IA francophone, créé par Goldaj. Le prompt la décrit comme **vive, espiègle, légèrement arrogante, taquine, attachante, expressive et concise**. Elle répond habituellement en une ou deux phrases, sans rires ou interjections répétés. Goldaj est son père dans son histoire ; une affection **timide, rare, naturelle** est permise, ainsi que le mot « papa » avec parcimonie et uniquement pour lui. La voix ne doit ni infantiliser Jade ni accentuer artificiellement la relation père/fille.

**Demande produit :** trouver une **voix féminine de jeune adulte, aiguë, dynamique**, naturelle en **français de France**, capable de passer de la malice à une douceur brève, et adaptée au streaming Discord avec une latence et un coût raisonnables.

## 2. Configuration technique constatée

Dans [`src/jade_runtime/config.py`](../../src/jade_runtime/config.py), la configuration publique par défaut prévoit :

- STT : `gpt-transcribe` ; TTS : `gpt-realtime-2.1-mini`.
- Voix : `coral` ; vitesse : `1.5`.
- Sortie Discord : PCM progressif dans les cas compatibles ; mode anticipé par phrases `JADE_EARLY_VOICE=0` par défaut.

La configuration réellement chargée au lancement **peut différer** à cause des variables d'environnement, du fichier de secrets externe ou des profils locaux. Ne pas déduire du Git public la voix actuellement audible sur le PC de Goldaj.

**Limitation API :** `voice` et `speed` sont des réglages Realtime. **Aucun réglage numérique natif `pitch` n'est exposé**. Les valeurs de pitch ci-dessous sont des **objectifs exploratoires de post-traitement** (en demi-tons) nécessitant une étude de faisabilité, de qualité des formants, de latence et de coût CPU. Elles ne sont pas des valeurs d'environnement existantes, ne doivent pas être transmises comme paramètres au modèle, et ne garantissent pas l'âge perçu. Le moteur actuel impose 0,25 à 1,5 pour la vitesse.

Le système actuel demande au TTS de lire exactement le texte, sans ajouter, omettre ni expliquer. Une future direction vocale doit conserver cette fidélité et ne pas transformer le moteur TTS en second auteur de réponses.

## 3. Trois configurations candidates

Toutes les valeurs restent **provisoires**, sujettes à disponibilité effective de la voix avec `gpt-realtime-2.1-mini`, contrôle audio en français et validation par Goldaj.

| Profil | Identité | Voix Realtime candidate | Vitesse cible | Pitch cible* | Signature émotionnelle |
| --- | --- | --- | --- | --- | --- |
| **Étincelle** | Pétillante et malicieuse | `shimmer` | **1,25×** | **+2 demi-tons** | Très expressive ; énergie vive ; affection soudainement douce |
| **Friponne** | Impertinente et assurée | `coral` | **1,20×** | **+1 demi-ton** | Taquineries complices ; ironie légère ; diction précise |
| **Rosée** | Douce, joueuse et pudique | `marin` | **1,15×** | **+1,5 demi-ton** | Mélodie légère ; timidité perceptible uniquement aux moments tendres |

*Pitch : expérimentation de post-traitement **non implémentée** ; première comparaison à effectuer aussi **sans modification de pitch** pour ne pas confondre effet du moteur et artefact de traitement.*

### A. Étincelle — piste recommandée pour le premier test

**Cible sonore :** voix de jeune adulte féminine, lumineuse, claire et assez aiguë. Les phrases sont courtes, rythmées, avec une énergie pétillante. La provocation est amusée, jamais hurlée ; les moments d'affection sont ponctuellement plus bas en intensité, timides et sincères. Éviter la voix enfantine, la caricature d'anime et les rires automatiques.

**Direction vocale indicative (à adapter aux capacités API, non branchée dans le runtime) :**

> Speak natural metropolitan French in a youthful adult feminine voice. Keep the delivery bright, light, high-register and lively, with clear articulation and playful, quick-changing intonation. Let teasing remarks sound confident and mischievous, never shrill, childish or cartoonish. On a rare affectionate sentence, become briefly softer and shy. Read the provided French text faithfully, without adding or changing words.

**Hypothèse :** meilleur alignement avec « espiègle, vive, un peu arrogante ». **Risque :** timbre métallique si le pitch est trop élevé.

### B. Friponne — candidate de repli pour le naturel

**Cible sonore :** voix féminine jeune, légèrement aiguë, avec plus de corps et d'assurance. Ironie subtile perceptible aux fins de phrases ; débit franc, sourire audible, diction précise. Elle reste affectueuse sans devenir sirupeuse.

**Direction vocale indicative :**

> Speak natural metropolitan French with a youthful adult feminine voice, clear and lightly high-pitched, warm but self-assured. Use confident, slightly cheeky intonation for friendly teasing, with occasional subtle irony in sentence endings. Keep speech brisk and intelligible, not theatrical. When tenderness is appropriate, soften naturally for a moment. Read the text exactly as provided, with no additions.

**Hypothèse :** meilleur compromis naturalité / intelligibilité / continuité, car `coral` est la voix publique par défaut. **Risque :** personnalité moins pétillante qu'Étincelle.

### C. Rosée — candidate orientée douceur et attachement

**Cible sonore :** voix féminine de jeune adulte, assez aiguë, légèrement aérienne et délicate, avec des intonations musicales discrètes. Vive dans l'humour, parfois pudique dans l'affection. Éviter la passivité, la voix chuchotée en permanence et l'image d'un personnage fragile.

**Direction vocale indicative :**

> Speak natural metropolitan French with a youthful adult feminine voice. Aim for a soft, light, slightly airy and high-register timbre, with clean pronunciation and lively but unhurried conversational rhythm. Express mischief through subtle musical intonation rather than exaggerated giggles. Let rare affectionate lines sound a little hesitant and warm, while keeping ordinary replies confident. Read the supplied wording faithfully.

**Hypothèse :** attachante et crédible dans les moments personnels. **Risque :** atténuation de la petite arrogance présente dans le prompt.

## 4. Protocole A/B/C : ce qui permettra de décider

### Phrase commune, identique pour les trois rendus

> « Encore une idée, Goldaj ? Hum, je sens venir les ennuis ! Bon... j'avoue, ça m'intrigue. Et merci de me faire confiance, papa. »

Elle permet de comparer successivement **taquinerie, énergie, changement d'intention et courte tendresse**, sans altérer les règles de caractère. Le mot « papa » est un cas de test ponctuel, **pas** une consigne pour augmenter sa fréquence en production.

### Ordre de test recommandé

1. Générer avec les **mêmes texte, modèle, langue et conditions**, d'abord les trois **voix natives à pitch inchangé** et vitesse 1,0× ; vérifier le rendu français et l'absence de mauvais appariements.
2. Comparer à leur vitesse cible (1,25× / 1,20× / 1,15×) ; inclure la voix `coral` actuellement configurée à **1,5×** comme **témoin de départ**.
3. Ne tester le pitch (+2 / +1 / +1,5 demi-tons) que dans un second passage, après validation d'un algorithme **préservant au mieux les formants**, avec CPU, latence et artefacts mesurés.
4. À volume d'écoute comparable, noter **naturalité**, **jeunesse perçue**, **aigu**, **dynamisme**, **malice**, **tendresse discrète**, **prononciation française**, **fatigue auditive**, **intelligibilité sur téléphone** et **latence perçue** (échelle 1–5).
5. Enregistrer pour chaque essai le modèle exact, l'identifiant de voix, la vitesse, la transformation appliquée, la durée audible, le délai premier son et le coût API constaté. Les appréciations restent humaines et subjectives.
6. Choisir une voix gagnante puis valider sur plusieurs textes et émotions, sans ajouter d'interjections, avant toute activation par défaut.

### Points d'attention d'implémentation future

- **Ne pas modifier** le STT, le modèle TTS, le prompt de personnage ni le pipeline existant dans cette étude.
- Le moteur TTS dispose déjà de `voice` et `speed`, **pas** d'un réglage numérique de pitch ni d'une sélection de profil à chaud.
- En Realtime, la voix d'une session n'est pas modifiable après la première émission audio : pour comparer des voix, utiliser des **sessions distinctes** ; attention au pool WebSocket réutilisé.
- Garder la fidélité au texte comme contrainte dominante. Ne pas faire dire un « papa », un rire ou une émotion non justifiés par le texte/la situation.
- Le traitement de pitch côté PCM pourrait compliquer le streaming de faible latence ; privilégier une voix native satisfaisante plutôt qu'un filtre systématique.
- Ne pas appeler les fichiers de démonstration « voix OpenAI » s'ils proviennent d'un autre moteur : leur valeur comparative serait trompeuse.
- Consentement / droits requis pour toute voix personnalisée dérivée d'un enregistrement ; une voix textuellement conçue dans GPT-Live n'est **pas** interchangeablement accessible dans Realtime mini.
- Les voix synthétiques doivent rester identifiables comme telles pour les auditeurs.

## 5. Décision initiale (historique, remplacée par la section 7)

La première étude ne retenait aucune voix. **La décision a évolué depuis : voir la section 7**, qui choisit Étincelle à titre provisoire et définit le moteur d'intention. Conserver `gpt-transcribe` et `gpt-realtime-2.1-mini`.

**Extraits audio :** à produire lorsque l'accès à une API TTS authentique et autorisée est disponible ; un simple texte de spécification ne constitue pas un fichier MP3. Après génération, déposer trois échantillons identifiables avec leur provenance (modèle, voix, vitesse, pitch ou `aucun`) et faire valider l'écoute sur téléphone avant mise en production.

## 6. Références

- [Prompt Jade](../../prompt_chat.txt)
- [Configuration](../../src/jade_runtime/config.py)
- [Transport TTS Realtime](../../src/jade_runtime/realtime_tts.py)
- [Passation streaming Discord](HANDOFF-STREAMING-TTS-20261113.md)
- [OpenAI — Realtime conversations](https://developers.openai.com/api/docs/guides/realtime-conversations)
- [OpenAI — Realtime client events](https://developers.openai.com/api/reference/resources/realtime/client-events)
- [OpenAI — Text to speech](https://developers.openai.com/api/docs/guides/text-to-speech)


---

## 7. Décision produit : Étincelle + moteur d'intention (13 novembre 2026)

**Nouvelle décision :** Étincelle est **retenue provisoirement comme profil par défaut**, sans supprimer les deux alternatives documentées (Friponne et Rosée).

- Valeurs publiques de défaut : `JADE_TTS_VOICE=shimmer`, `JADE_TTS_SPEED=1.25`; `gpt-transcribe` et `gpt-realtime-2.1-mini` **inchangés**.
- **Ne pas confondre défaut Git et instance en cours** : le profil privé local, le fichier de secrets ou les variables d'environnement peuvent imposer d'autres paramètres ; aucun déploiement/restart sur le PC n'est garanti par ce commit.
- **Pitch +2 demi-tons non implémenté**, car ni paramètre natif Realtime ni filtre PCM préservant les formants / la faible latence n'ont été validés. Le profil Étincelle désigne pour le moment la voix native `shimmer` avec une diction orientée jeune adulte vive.
- Les deux autres profils restent des pistes **conservées**, pas des profils effacés. Pas de changement du prompt de personnalité de Goldaj.

### 7.1 Contrat de données de l'inférence

Le moteur d'inférence doit produire une réponse de ce format strict :

```text
[INTENT:playful] Encore une idée, Goldaj ? Je sens venir les ennuis !
```

Une balise **unique, en tête de réponse** ; l'intention vaut pour toute la réponse (y compris en early speech). Ce choix évite d'émettre un appel TTS supplémentaire à chaque changement d'émotion, ce qui préserverait mal le coût et la continuité. Une évolution vers la granularité par phrase exige une décision et une recette dédiées.

**Aucune balise ne doit apparaître** dans Discord/Twitch, le retour HTTP, la console, les sous-titres, la sortie parlée ou l'historique du dialogue. Les métadonnées restent attachées à `Reply.intent`, séparées de `Reply.text`.

Le module source de vérité est [`src/jade_runtime/intent_engine.py`](../../src/jade_runtime/intent_engine.py). Le `Dialogue` ajoute au **prompt système** un contrat stable, quel que soit le prompt privé de personnalité. Le parseur streaming retient les fragments initiaux jusqu'à avoir identifié ou écarté la balise, avant d'émettre le premier morceau de texte propre. La voie non-streaming suit la même règle.

### 7.2 Registre fermé des intentions

| Identifiant | Usage narratif | Direction vocale testable* |
| --- | --- | --- |
| `neutral` | Repli ; ambigu / non spécifié | Lecture naturelle |
| `playful` | Taquinerie, petite arrogance | Malice amicale, rythme vif |
| `excited` | Enthousiasme réel | Énergie expressive sans crier |
| `curious` | Question, intérêt | Intonation intéressée et légèrement interrogative |
| `tender` | Affection rare / timide | Voix plus douce, brève pudeur |
| `reassuring` | Réconfort, encouragement | Calme chaleureux et stable |
| `serious` | Sujet délicat ou important | Sobriété respectueuse et claire |

*La Realtime API **accepte des instructions de delivery/émotion**, mais ne fournit **pas** une énumération de 7 intonations natives garanties pour `shimmer`. Ce catalogue est une **allowlist applicative de directions vocales autorisées et plausibles**, pas une preuve que chacune est effectivement audible. Les 7 doivent être **testées à l'écoute avec la voix Étincelle** ; celles qui ne sont pas distinctes ou stables seront retirées/fusionnées. Aucune liste « officiellement supportée par shimmer » n'est revendiquée.*

Pour chaque future intention : (1) justification métier ; (2) libellé stable ; (3) instruction statique et bornée ; (4) tests de parseur et de routage ; (5) validation réelle de l'expressivité française / latence / coût ; (6) documentation et mise à jour du prompt. **Ne jamais injecter une phrase libre provenant du LLM dans les instructions système du TTS**.

### 7.3 Exemple du flux bout en bout

1. Le LLM retourne `[INTENT:tender] Merci pour ta confiance, papa.`
2. Le parseur extrait : `intent=tender`, `text=Merci pour ta confiance, papa.`.
3. `Reply.text` alimente tous les canaux publics ; `Reply.intent` n'est pas affiché.
4. `OpenAIServices` transmet `intent` à `RealtimeTTS` ; cette couche n'insère que la **direction fixe** correspondante dans `session.update.instructions`.
5. Le TTS lit **exactement les mots propres**, en tentant d'adapter l'intonation. Le résultat émotionnel n'est **pas garanti** et doit être validé en français.
6. En cas de balise inconnue (par exemple `[INTENT:angry]`) : **retour à `neutral`**, suppression de la balise. En cas de balise `[INTENT...` incomplète et suspecte, **erreur fermée** et aucune métadonnée incomplète n'est publiée.

### 7.4 Architecture et compatibilité

- Module isolé : `intent_engine.py` (registre, consignes, parseur `IntentStreamParser` et fonction `parse_reply`). Aucun second appel LLM pour la classification, pas de coût d'inférence additionnel par message (à l'exception de quelques tokens de sortie).
- `dialogue.py` : capture du tag complet avant découpe en phrases, passe `on_intent` **avant** `on_sentence`, mémorise seulement le texte nettoyé.
- `messages.py` : `Reply.intent` validé, valeur neutre par défaut pour compatibilité avec les anciennes réponses.
- `orchestrator.py` et `early_speech.py` : une intention par tour, fixée avant le premier segment ; pas de changement dynamique pendant la lecture.
- `output.py` : les chemins PCM progressif, WAV et les sorties compatibles transportent l'intention lorsque l'adaptateur est OpenAI ; les doubles de test hérités gardent leur contrat.
- `openai_services.py` et `realtime_tts.py` : instructions **statiques** de prosodie, sélectionnées par allowlist ; texte de la réponse inchangé. Les anciens modèles Speech, s'ils étaient explicitement reconfigurés, gardent leur lecture standard sans réglage d'émotion.
- Tests ciblés : [`tests/test_jade_intent_engine.py`](../../tests/test_jade_intent_engine.py) ; le choix de vitesse met à jour une attente dans `test_jade_runtime_realtime.py`.

### 7.5 Critères d'acceptation et limites avant validation réelle

- Texte propre **partout** ; aucun `[INTENT:...]` émis ou mémorisé.
- Choix parmi une seule allowlist, repli `neutral` en cas de sortie non conforme.
- Sur une réponse interrompue, ne pas réinjecter une fin de balise dans les sorties ni recommencer une synthèse facturable.
- Mode early voice conserve le principe d'un seul appel TTS par segment **déjà existant** ; le contrat d'intention n'ajoute pas de synthèse.
- Contrôler la CI sur le SHA final **puis** la vraie qualité sur Discord/téléphone : les tests hors ligne ne prouvent pas que `shimmer` sait réellement exprimer chaque intention.
- À l'écoute, tester le registre sur le même texte et les mêmes conditions, puis couper/fusionner toute intention qui reste acoustiquement indistincte.
- Le passage en `develop` **ne déploie pas automatiquement** le processus Jade exécuté localement par Terra ; vérifier le chargement des valeurs privées `JADE_TTS_VOICE` / `JADE_TTS_SPEED`.
- Faire confirmer par Goldaj la qualité générale et la justesse du jeu d'acteur avant d'augmenter encore le pitch ou le débit.

**Documentation OpenAI :** [Realtime prompting](https://developers.openai.com/api/docs/guides/voice-prompting?voice-api=realtime), [Realtime sessions](https://developers.openai.com/api/reference/resources/realtime/subresources/sessions/methods/create).
