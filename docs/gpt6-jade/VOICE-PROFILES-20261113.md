# Jade — trois profils vocaux à évaluer (propositions, non implémentées)

**Date :** 13 novembre 2026  
**Statut :** étude / hypothèses de design vocal ; **aucun profil validé, codé ou activé**.  
**Branche documentaire :** `develop` ; **aucune modification du runtime ni des valeurs en production**.

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

## 5. Décision à ce jour

**Aucun choix vocal définitif.** Ordre de préférence **à tester** : Étincelle, Friponne, Rosée. Conserver `gpt-transcribe` et `gpt-realtime-2.1-mini`. Aucune modification de code ou de configuration ne découle de cette note.

**Extraits audio :** à produire lorsque l'accès à une API TTS authentique et autorisée est disponible ; un simple texte de spécification ne constitue pas un fichier MP3. Après génération, déposer trois échantillons identifiables avec leur provenance (modèle, voix, vitesse, pitch ou `aucun`) et faire valider l'écoute sur téléphone avant mise en production.

## 6. Références

- [Prompt Jade](../../prompt_chat.txt)
- [Configuration](../../src/jade_runtime/config.py)
- [Transport TTS Realtime](../../src/jade_runtime/realtime_tts.py)
- [Passation streaming Discord](HANDOFF-STREAMING-TTS-20261113.md)
- [OpenAI — Realtime conversations](https://developers.openai.com/api/docs/guides/realtime-conversations)
- [OpenAI — Realtime client events](https://developers.openai.com/api/reference/resources/realtime/client-events)
- [OpenAI — Text to speech](https://developers.openai.com/api/docs/guides/text-to-speech)
