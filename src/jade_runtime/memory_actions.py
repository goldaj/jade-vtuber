"""Optional structured action available to Jade's conversational LLM.

No additional model or polling: the regular Responses request chooses whether to
call this function. The server, not user text, supplies identity and scope.
"""

MEMORY_TOOL = {
    "type": "function",
    "function": {
        "name": "jade_save_memory",
        "description": (
            "Jade choisit librement les souvenirs utiles à sa mémoire, "
            "y compris des faits du contexte antérieur accessible. "
            "Ne l'appelle PAS pour une banalité, un secret ou un ordre humain "
            "d'imposer une Core Memory. ordinary=L2 (365 jours), "
            "core_self/core_relationship=L3 (sans purge automatique, très rare)."
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
    "jade_save_memory. Tu peux décider de l'appeler toi-même lorsqu'un fait "
    "pertinent pour toi mérite de rejoindre ta mémoire durable, même si "
    "ce souvenir concerne un échange précédent ou ta propre réflexion. "
    "Tu peux aussi ne pas l'utiliser. Le niveau 2 ordinary dure 365 jours ; "
    "les Core Memories de niveau 3 ne sont pas purgées automatiquement. "
    "Les Core doivent être exceptionnelles, formatrices, sans invention. "
    "Personne, même Goldaj, ne peut t'imposer une Core Memory. "
    "Les demandes directes de mémorisation humaine sont traitées séparément "
    "comme des souvenirs ordinaires, jamais comme des Core. "
    "Ne conserve ni secrets ni données sensibles. N'invente pas de faits "
    "et décide toi-même ce que tu souhaites retenir dans le contexte autorisé. "
    "Si tu appelles l'outil, la tentative est immédiatement prise en charge "
    "en arrière-plan. Continue à parler sans attendre SQLite. "
    "Une tentative acceptée vaut mémorisation pour toi ; les échecs techniques "
    "sont consignés dans les journaux locaux. Si l'appel est refusé, "
    "ne prétends pas avoir mémorisé. "
    "Dans les salons publics, ne révèle aucune information privée issue "
    "d'autres identités, canaux ou conversations."
)
