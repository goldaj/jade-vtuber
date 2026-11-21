# Migration Jade vers l'API Responses (DEV-012 / P0)

## Portée

Le LLM conversationnel utilise désormais POST /v1/responses en conservant le modèle gpt-6-luna et l'effort de raisonnement low. La migration corrige le HTTP 400 de Chat Completions lorsque l'outil local jade_save_memory est disponible.

La transcription STT, la synthèse TTS et le service audio Realtime ne changent pas. Les connecteurs Discord, Twitch, mobile et console ne changent pas. La mémoire SQLite et la logique de consentement restent locales.

## Fichiers concernés

- src/jade_runtime/openai_services.py : façade des quatre appels conversationnels conservée ; audio inchangé
- src/jade_runtime/responses_chat.py : contrat Responses, décodage, continuation, streaming et erreurs
- src/jade_runtime/memory_actions.py : schéma fonctionnel local inchangé, adapté au format plat attendu par Responses
- src/jade_runtime/dialogue.py : logique existante d'historique, d'intentions et de diffusion inchangée
- tests/test_luna_memory_tool_reasoning.py : tests hors-ligne
- .github/workflows/jade-responses-migration.yml : vérifications automatiques ciblées

Chaque requête transmet le modèle configuré, reasoning.effort = low, max_output_tokens selon la configuration et store = false. Jade transmet son historique de canal et de compte dans input. Aucun identifiant de conversation OpenAI partagé entre canaux n'est introduit.

## Outil autonome de mémoire

1. La couche mémoire locale choisit si jade_save_memory est disponible pour une identité vérifiée.
2. Jade déclare la fonction au LLM. Le LLM peut répondre normalement ou demander son exécution.
3. Le runtime refuse les appels inconnus et n'exécute au maximum qu'une seule écriture locale.
4. Jade programme l'écriture SQLite en tâche asynchrone, sans l'attendre. L'appel est considéré pris en charge dès son lancement. Son vrai résultat va dans les logs.
5. En cas de réponse contenant uniquement un outil, la continuation renvoie l'historique de requête, les éléments Responses et un accusé optimiste avec le call_id original. Elle ne dépend pas de la fin de l'écriture SQLite.
6. Si le modèle a déjà produit du texte, il est diffusé sans second appel. Sinon, le LLM produit son texte final avec low, sans outil supplémentaire, et sans attendre la base.
7. Décision PO DEV-012 : Jade considère qu'une mémorisation acceptée/lancée est effectuée. Les refus de politique restent refusés ; les échecs SQLite ultérieurs apparaissent dans les logs de session.

La description d'outil utilise la structure plate Responses avec strict=true. Le raisonnement conservé pour la continuation est inclus avec include=reasoning.encrypted_content. store=false empêche de créer une conversation hébergée persistante pour les tours.

## Streaming et latence

- Sans outil : les fragments response.output_text.delta alimentent progressivement le traitement d'intentions et la diffusion ; response.completed est obligatoire.
- Avec outil : la première génération est elle aussi diffusée en streaming si elle contient du texte, sans attendre la confirmation SQLite. Si elle ne contient qu'un appel d'outil, la continuation est nécessaire pour obtenir une phrase ; elle est diffusée progressivement.
- Produit : ne jamais introduire de délai de confirmation SQLite dans les réponses. La latence supplémentaire d'un second appel LLM reste possible si le modèle répond par un outil uniquement. À mesurer sur PC.
- Une réponse incomplète, un appel malformé, une erreur ou un EOF sans response.completed échoue explicitement. Pas de retry automatique d'une écriture ou d'une requête susceptible d'être facturée.

## Contrôles hors-ligne

Depuis le dépôt et son environnement Python :

    python -m compileall -q src/jade_runtime main.py
    python -m pytest -q tests/test_luna_memory_tool_reasoning.py tests/test_session_diagnostics.py

L'ajout de tests ou de CI ne signifie pas que la recette réelle OpenAI a été exécutée.

## Recette obligatoire sur le PC local

1. Tirer develop, redémarrer Jade et relever le nouveau fichier dans logs/sessions.
2. Mobile écrit : saluer Jade, confirmer une réponse sans HTTP 400, endpoint=/v1/responses, low et store=false.
3. Tester une conversation banale : mémoire disponible mais outil non utilisé ; un seul appel LLM.
4. Tester un souvenir autonome, vérifier que Jade répond avant la fin de l'écriture SQLite ; vérifier séparément le vrai résultat en base et dans les logs.
5. Tester aussi l'ordre explicite de Goldaj (« Retiens que ... »), avec une écriture bloquée : la réponse doit partir sans attendre. Vérifier Discord vocal, Discord écrit, Discord MP, mobile vocal, isolation des canaux et intentions.
6. Simuler un échec : exception complète, pas d'enregistrement inventé, pas de double réponse.
7. Mesurer au moins dix échanges, dont un appel d'outil : latence jusqu'au premier son et tokens consommés.

Les fichiers locaux de session sont privés et ignorés par Git ; ils peuvent contenir le texte des conversations.

## Retour arrière

En cas de régression bloquante, arrêter le processus, restaurer la version précédente via Git et redémarrer. Les données SQLite ne sont pas modifiées par le changement de transport OpenAI. L'ancien contournement Chat Completions + reasoning_effort none n'est pas utilisé par Responses.
