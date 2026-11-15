# Réglage du LLM, conservation des conversations et participation - develop (2026-11-15)

Ce document décrit le code de `develop`, pas une recette matérielle validée.

## 1. Modèle de dialogue

- Par défaut : `gpt-6-luna`, variable `JADE_LLM_MODEL`.
- Effort transmis à **chaque appel Chat Completions**, streaming inclus : `reasoning_effort="low"`; variable `JADE_LLM_REASONING_EFFORT` (défaut `low`). L'ancien niveau était *implicite*, donc `medium` par défaut de Luna.
- Plafond : `max_completion_tokens=320`; variable `JADE_MAX_COMPLETION_TOKENS` (défaut `320`). Ancien plafond : `160`.
- Les tokens internes de raisonnement sont comptés dans le plafond : ce n'est **pas** une cible de longueur de la réponse visible. La longueur habituelle demeure guidée par `prompt_chat.txt`.
- L'API est appelée via `src/jade_runtime/openai_services.py`. Ce changement touche aussi les appels de l'arbitre et du curateur, qui partagent le backend.
- Le modèle est configurable ; si un modèle non compatible avec `reasoning_effort` est choisi, adapter les paramètres explicitement au lieu de masquer l'erreur.
- Tarifs Luna Standard indicatifs (2026-11-15) : entrée $0,10/M tokens et sortie $0,50/M tokens, hors voix/STT/TTS. 160 tokens sortants coûtent au maximum $0,000080 ; 320 tokens $0,000160. Les coûts d'entrée et des autres appels sont supplémentaires ; le raisonnement à effort inférieur peut réduire la consommation réelle mais ne change pas le prix unitaire.
- **Prompt de personnalité non modifié. Prompt d'intention non modifié.** Les candidats V1/V2/V3 résident dans [PROPOSITIONS-PERSONNALITE-20261115.md](PROPOSITIONS-PERSONNALITE-20261115.md) et ne sont pas branchés.

## 2. Historique intégral, sans résumé systématique

- `JADE_HISTORY_LIMIT` passe par défaut de **24 à 48 messages** récents en RAM, incluant les deux rôles.
- `MemoryStore` SQLite `SCHEMA_VERSION=3` introduit `conversation_turns`, stockant l'entrée et la réponse **en texte complet** avec source, scope, horodatage et ID du message ; jamais la balise `[INTENT]` dans la réponse.
- Ce journal est **opt-in par identité authentifiée**, intégré au consentement de mémoire existant. Activer `JADE_MEMORY_ENABLED=1` et un chemin privé absolu `JADE_MEMORY_DB_PATH`, puis demander `!jade-memoire activer` sur un transport vérifié. La curation `JADE_MEMORY_CURATOR_ENABLED` n'est PAS nécessaire pour conserver le texte.
- Les identités non vérifiées et non consentantes ne sont pas archivées en SQLite par cette fonction. Le local HTTP et la console non authentifiée restent sans journal individuel opt-in. Les contextes publics sont séparés par `scope`, et le micro et mobile authentifiés de Goldaj partagent `person`.
- À l'ouverture d'une session en RAM, les **24 derniers échanges complets** (48 messages) sont restaurés depuis SQLite (ou moins selon `JADE_HISTORY_LIMIT`), sans résumé ni seconde requête LLM. Les échanges plus anciens restent dans SQLite mais ne sont pas réinjectés tous à chaque requête pour éviter coût et congestion du contexte.
- La suppression via `!jade-memoire oublier` retire le profil et supprime ses conversations enregistrées grâce à la clé étrangère `ON DELETE CASCADE` ; les caches RAM du runtime ne sont pas encore effacés en direct par cette commande et expirent normalement : **limite à corriger lors d'une prochaine passe**.
- Les tours interrompus avant remise de la réponse ne sont pas archivés comme des réussites. L'archivage intervient après tentative de livraison réussie dans le runtime, sans accusé de lecture distant garanti sur chaque plateforme.
- Les conversations ne sont jamais automatiquement résumées. Le journal peut croître : sauvegarde privée, rotation et quota de stockage devront être décidés en exploitation. Les exports de souvenirs existants ne prétendent pas automatiquement exporter les nouveaux transcrits.
- Les sources persistées contiennent potentiellement des données privées : fichier SQLite uniquement sur le PC, hors Git, autorisations locales restrictives recommandées. Les copies de sauvegarde nécessitent la même protection.

## 3. Tête-à-tête et groupes par support

**Règle :** lorsqu'un seul interlocuteur humain est effectivement connu dans la conversation, Jade répond à tous les messages éligibles ; en groupe, elle participe à hauteur d'un **tirage aléatoire de 30 %** sur les messages admissibles, en gardant les exceptions de commande/adressage direct et les limites propres à chaque connecteur.

| Support | Détection du tête-à-tête | Groupe |
| --- | --- | --- |
| Micro PC | Goldaj seul par définition | Sans objet |
| PWA mobile privée | Goldaj authentifié seul | Sans objet |
| HTTP local | Session individuelle authentifiée | Sans objet |
| Discord écrit | Auteurs non-bots uniques **observés** dans les 10 dernières minutes sur le canal ; ID Discord | 30 % des interventions spontanées admissibles ; cooldown 180 s ; mentions, réponses directes et suivis restent prioritaires |
| Twitch IRC | Chateurs actifs **observés** dans les 10 dernières minutes ; ID Twitch ou pseudonyme transport | 30 % via `JADE_RANDOM_REPLY_RATE` ; adressage direct prioritaire |
| Discord vocal | Membres humains du salon vocal **vus dans l'état Discord** à l'instant du tour STT | 30 % via `ConversationTurnDecider`, sauf adressage explicite / suivi ; état inconnu traité comme groupe, pas comme tête-à-tête |

**Limites importantes :**
- Twitch IRC ne donne pas une liste exhaustive des spectateurs, et Discord texte ne prouve pas qu'une autre personne silencieuse écoute. La règle solo vaut pour les **participants actifs observés**, pas pour les lurkers.
- Le tirage de 30 % n'est pas un classifieur sémantique : il ne mesure pas la pertinence. Le cooldown Discord reste important pour éviter le spam.
- La connexion vocale continue d'écouter les personnes audibles sans filtrage par participant ; le comptage sert uniquement à choisir la fréquence des **réponses**.
- Les transcriptions vides, commandes mute et situations invalides restent traitées par le système de garde existant.
- Les réglages `JADE_DISCORD_TEXT_AUTO_RATE` et `JADE_RANDOM_REPLY_RATE` peuvent être personnalisés indépendamment ; leurs valeurs par défaut valent 0,30.

## 4. Deux réactions par intention : plan seulement, rien de branché

Conserver sans modification `intent_engine.py`, les sept labels `neutral / playful / excited / curious / tender / reassuring / serious`, et le tag `[INTENT:label]`.

**Contrat futur souhaité :**
- Pour **chaque intention**, prévoir au moins deux variantes textuelles et deux réactions 2D distinctes, coordonnées mais non figées dans un seul binôme. Une intention sert d'information de haut niveau, pas d'obligation d'insérer une réplique stéréotypée.
- Construire un registre de métadonnées séparé, par exemple `intent_variants.json` dans les assets, avec pour chaque intention `text_style: [A,B]` et `motion_asset: [A,B]`, ainsi qu'un repli sur l'état neutre.
- Choisir une variante par session avec alternance souple et mémoire de la dernière utilisée ; **aucune requête supplémentaire au LLM** juste pour choisir. Ne pas alterner de manière mécanique si le contexte impose une réaction sobre.
- Les deux réactions textuelles doivent être des **directions de jeu** ou de style, pas des textes copiés/collés ou du texte imposé, afin d'éviter les tics verbaux.
- Les animations r20/r21 doivent disposer de vrais assets valides, mappings et tests d'intégration avant branchement. Une animation manquante doit déclencher un fallback sans bloquer la parole.
- **Aucune nouvelle animation créée, aucun asset Live2D remplacé, aucune variante activée actuellement.** Il faudra un chantier dédié après validation du prompt et du modèle graphique.

## 5. Vérifications attendues

`python -m unittest discover -s tests -v` ; `python -m compileall -q src main.py` ; préflight ; tests du journal avec opt-in, doublons, suppression, réhydratation, séparation des canaux ; tests de participation solo/groupe et de seuils de cooldown ; puis essais physiques séparés sur PC Windows, Discord écrit/vocal, Twitch et Android.

Le jeu de tests local additionnel est `tests/test_persona_runtime_20261115.py`. Sa présence dans Git n'est pas en soi une preuve que les tests CI ou les scénarios physiques ont réussi.
