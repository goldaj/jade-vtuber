# Jade — configuration Low/320, mémoire conversationnelle et participation
Date : 2026-11-15. Branche : `develop`. État : implémentation logicielle, validation réelle en attente.

## Décisions actées
- Dialogue : modèle par défaut `gpt-6-luna`, effort explicite `low`, `max_completion_tokens=320` sur Chat Completions classique **et streaming**. Variables privées `JADE_LLM_MODEL`, `JADE_LLM_REASONING_EFFORT`, `JADE_MAX_COMPLETION_TOKENS` prévalent sur les valeurs par défaut ; vérifier le fichier privé du PC avant de conclure aux paramètres effectifs.
- Prompt actif : `prompt_chat.txt` remplacé **exactement** par le texte validé par Goldaj dans la conversation du 15 novembre ; ne pas le retoucher sans accord explicite.
- Prompt d'intention `src/jade_runtime/intent_engine.py` : inchangé, toujours `[INTENT:...]` ajouté par `Dialogue`.
- Limite d'historique volatile : 48 **messages** récents par session (`JADE_HISTORY_LIMIT`).
- Journal SQLite : table `conversation_turns`, `PRAGMA user_version=3`, conversation complète non résumée pour les **identités vérifiées ayant activé volontairement la mémoire**. Enregistrement après la remise de la réponse, pas des tours abandonnés, pas des messages passifs des autres participants. Pas de TTL pour ces échanges ; suppression via l'effacement du profil de mémoire. Les souvenirs synthétiques existants restent distincts et leur curation est facultative.
- À la première ouverture d'une session volatile, restaurer jusqu'aux 24 derniers tours complets (48 messages) depuis la SQLite si profil activé et même périmètre de confidentialité. Le reste demeure archivé en SQL, **pas injecté dans le modèle**. Ne jamais prétendre que le contexte LLM est infini. Aucune compression/résumé des tours réinjectés.
- Identifiants micro désormais uniques par démarrage afin d'éviter collisions d'historique.

## Politique de participation
- Micro PC, PWA privée et HTTP local : échanges directs donc réponse obligatoire (sauf erreurs, commandes de silence spécifiques, filtre de longueur, saturation, connexion).
- Discord texte : un seul humain **ayant participé au salon dans les 10 dernières minutes**, Jade comprise comme second participant -> réponse à tous ses messages éligibles. Plusieurs humains ayant participé -> 30 % des interventions spontanées éligibles, délai de refroidissement inchangé, suivi de conversation également échantillonné. Interpellation explicite / DM -> réponse directe, même en groupe. Les messages > 1200 caractères restent écartés dans `Dialogue`; les bots ne sont pas comptés comme des humains.
- Twitch : le connecteur IRC observe les auteurs actifs sur 10 minutes, pas les spectateurs muets. Un seul auteur actif -> réponse obligatoire ; plusieurs auteurs actifs -> échantillonnage à 30 % par `Dialogue` (sauf interpellation explicite), limitation d'envoi IRC inchangée. Pas de véritable chiffre d'assistance disponible par IRC.
- Discord vocal : compter les humains visibles parmi les membres du salon vocal. Un seul humain -> décision de réponse systématique sur un tour vocal valide ; plusieurs humains -> échantillonnage 30 % pour les tours non directement adressés. Interpellation explicite « Jade » et contexte de suivi vocal continuent d'être privilégiés ; règles de silence, interruption et protection anti-écho maintenues. Lorsque la liste des membres est inconnue, **ne pas affirmer que le salon est un tête-à-tête**.
- Ces probabilités s'appliquent **aux tours admissibles**, pas au trafic global : silence, sons incompréhensibles, restrictions de longueur, débit, délais, files saturées ou échecs techniques peuvent réduire les réponses livrées.

## Évolution artistique planifiée seulement
- `neutral`, `playful`, `excited`, `curious`, `tender`, `reassuring`, `serious` : chaque intention prévoit **deux réactions alternatives** (A/B) dans le futur catalogue expressif, soit 14 emplacements conceptuels.
- Prévoir la séparation entre intention de voix, réaction 2D, sélection sans répétition, compatibilité des ressources, fallback si un asset manque, et synchronisation avec la voix. Ne pas modifier le format du tag `[INTENT:...]`.
- **Aucune nouvelle animation 2D et aucun sélecteur de variantes implémentés** dans cette livraison ; le document sert de contrat futur, pas de preuve d'animations fonctionnelles.

## Coût / contexte
- Tarif GPT-6 Luna Standard en contexte court au 2026-11-15 : 0,10 $/million de tokens d'entrée, 0,50 $/million en sortie, entrée cachée 0,01 $/million (sous réserve de mise à jour). 160 tokens de sortie maximum = 0,00008 $ ; 320 = 0,00016 $ de sortie par appel si le plafond est effectivement atteint. Le raisonnement interne consomme le même budget de sortie et le niveau `low` ne garantit ni une baisse systématique du coût total ni 320 tokens de texte visible. Les tarifs STT/TTS et les éventuels appels d'arbitrage ou de curation sont distincts.
- La persistance de l'historique accroît les tokens d'entrée dans les conversations longues : coût et latence doivent être mesurés en pratique.

## Tests et limites
- Tests hors ligne ajoutés dans `tests/test_personality_runtime_20261115.py` pour les paramètres, l'appel standard/stream, l'historique exact et effaçable, l'injection de l'historique, le solo texte Discord et le solo vocal.
- **Ces tests n'ont pas pu être exécutés depuis le connecteur GitHub** : ils constituent une couverture à lancer par CI/Poetry sur un clone ou PC. Ne pas annoncer un succès de tests non observé. Commandes : `poetry run python -m unittest discover -s tests -v` et `poetry run python main.py --preflight`.
- Vérifier en réel : API OpenAI Luna low/320, interaction sur toutes les plateformes, nombre de présents Discord vocal et sessions multiples, délais/cooldowns, conservation et effacement SQLite, historique après redémarrage, absence de fuite entre profils, charge et TTS.
- Les configurations privées `JADE_LLM_REASONING_EFFORT`, `JADE_MAX_COMPLETION_TOKENS`, `JADE_RANDOM_REPLY_RATE` et `JADE_DISCORD_TEXT_AUTO_RATE` peuvent écraser les valeurs par défaut ; seul le PC de déploiement prouve l'effectivité réelle.
- Des journaux console préexistants peuvent contenir le texte des tours sélectionnés. Protéger leur stockage indépendamment de la SQLite, et ne jamais les committer.
