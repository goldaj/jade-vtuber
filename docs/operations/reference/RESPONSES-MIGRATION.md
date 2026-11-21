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
4. Le résultat de l'exécution est renvoyé sous forme de function_call_output avec le call_id original.
5. La continuation renvoie l'historique de requête, tous les éléments Responses issus du premier appel, y compris les éléments de raisonnement chiffrés, et les résultats des fonctions.
6. Le LLM produit son texte final avec low, sans outil supplémentaire ; pas de boucle d'appels.
7. Le LLM ne doit annoncer un succès qu'après confirmation locale.

La description d'outil utilise la structure plate Responses avec strict=true. Le raisonnement conservé pour la continuation est inclus avec include=reasoning.encrypted_content. store=false empêche de créer une conversation hébergée persistante pour les tours.

## Streaming et latence

- Sans outil : les fragments response.output_text.delta alimentent progressivement le traitement d'intentions et la diffusion ; response.completed est obligatoire.
- Avec outil : la première génération est entièrement validée AVANT la diffusion d'une phrase, pour éviter de promettre une mémoire sauvegardée avant son écriture. La continuation éventuelle est diffusée en streaming.
- Limite assumée : délai au premier son potentiellement supérieur pour les flux vocaux avec outil disponible, même inutilisé. À mesurer par recette sur PC.
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
4. Discuter d'un fait méritant éventuellement un souvenir, vérifier l'exécution réelle et le résultat rapporté au modèle.
5. Vérifier Discord vocal, Discord écrit, Discord MP, mobile vocal, isolation des canaux et diffusion correcte des intentions.
6. Simuler un échec : exception complète, pas d'enregistrement inventé, pas de double réponse.
7. Mesurer au moins dix échanges, dont un appel d'outil : latence jusqu'au premier son et tokens consommés.

Les fichiers locaux de session sont privés et ignorés par Git ; ils peuvent contenir le texte des conversations.

## Retour arrière

En cas de régression bloquante, arrêter le processus, restaurer la version précédente via Git et redémarrer. Les données SQLite ne sont pas modifiées par le changement de transport OpenAI. L'ancien contournement Chat Completions + reasoning_effort none n'est pas utilisé par Responses.
