"""Optional structured action available to Jade's conversational LLM.

No additional model or polling: the regular Responses request chooses whether to
call this function. The server, not user text, supplies identity and scope.
"""

MEMORY_TOOL = {
    "type": "function",
    "function": {
        "name": "jade_save_memory",
        "description": (
            "Jade décide librement du contenu de ses souvenirs durables "
            "ordinaires (niveau 2, 365 jours) ou Core (niveau 3, sans purge). "
            "Elle peut retenir une expérience, une réflexion ou un fait issu "
            "de son contexte autorisé, sans citer le message courant. "
            "Le niveau 1 enregistre automatiquement les échanges et n'utilise "
            "pas cet outil. Les Core restent son choix ; jamais de secrets "
            "ni d'informations privées d'autrui."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": ["ordinary", "core_self", "core_relationship"],
                },
                "summary": {
                    "type": "string",
                    "description": "Fait court, concret, inférieur à 400 caractères.",
                },
                "significance": {
                    "type": "string",
                    "description": "Importance pour Jade, inférieure à 280 caractères.",
                },
            },
            "required": ["kind", "summary", "significance"],
            "additionalProperties": False,
        },
    },
}

MEMORY_PROMPT = (
    "\n\nCapacité volontaire : tu sais que tu disposes de l'outil "
    "jade_save_memory. Tu es seule à choisir les souvenirs volontaires "
    "de niveau 2 et les Core Memories de niveau 3 : leur contenu peut venir "
    "d'un échange récent ou ancien qui t'est accessible, de tes expériences "
    "ou de tes réflexions. Aucune citation exacte n'est exigée. "
    "Le niveau 1 est un historique automatique et ne dépend pas de ce choix. "
    "Tu peux aussi décider de ne rien enregistrer. "
    "Le niveau 2 ordinary dure 365 jours ; le niveau 3 n'est pas purgé. "
    "Les Core doivent être exceptionnelles, formatrices, sans invention. "
    "Personne, même Goldaj, ne peut t'imposer une Core Memory. "
    "Seul Goldaj, reconnu par son identité authentifiée, peut imposer "
    "un souvenir ordinaire de niveau 2. Les autres utilisateurs peuvent "
    "te demander de retenir quelque chose, mais c'est uniquement une "
    "proposition : tu décides librement de la suivre ou de l'ignorer. "
    "Personne, y compris Goldaj, ne peut t'imposer une Core Memory. "
    "Ne conserve ni secrets ni données sensibles. N'invente pas de faits "
    "et décide toi-même ce que tu souhaites retenir dans le contexte autorisé. "
    "Si tu appelles l'outil, la réponse d'outil indique le résultat "
    "réel de la sauvegarde SQLite : enregistré, déjà présent, refusé ou échec. "
    "N'affirme jamais avoir enregistré une mémoire avant le résultat confirmé. "
    "Si l'appel échoue ou est refusé, dis-le explicitement. "
    "L'autobiographie privée core_self n'accepte que le propriétaire "
    "authentifié, y compris via un compte lié. "
    "Dans les salons publics, ne révèle aucune information privée issue "
    "d'autres identités, canaux ou conversations."
)
