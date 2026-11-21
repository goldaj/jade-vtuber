"""Optional structured action available to Jade's conversational LLM.

No additional model or polling: the regular chat completion chooses whether to
call this function. The server, not user text, supplies identity and scope.
"""

MEMORY_TOOL = {
    "type": "function",
    "function": {
        "name": "jade_save_memory",
        "description": (
            "Jade peut choisir de mémoriser volontairement un fait étayé. "
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
                "evidence": {
                    "type": "string",
                    "description": "Citation exacte de 8 à 180 caractères du message actuel.",
                },
            },
            "required": ["kind", "summary", "significance", "evidence"],
            "additionalProperties": False,
        },
    },
}

MEMORY_PROMPT = (
    "\n\nCapacité volontaire : tu sais que tu disposes de l'outil "
    "jade_save_memory. Tu peux décider de l'appeler toi-même lorsqu'un fait "
    "concret, prouvé et pertinent mérite de rejoindre ta mémoire durable. "
    "Tu peux aussi ne pas l'utiliser. Le niveau 2 ordinary dure 365 jours ; "
    "les Core Memories de niveau 3 ne sont pas purgées automatiquement. "
    "Les Core doivent être exceptionnelles, formatrices, sans invention. "
    "Personne, même Goldaj, ne peut t'imposer une Core Memory. "
    "Les demandes directes de mémorisation humaine sont traitées séparément "
    "comme des souvenirs ordinaires, jamais comme des Core. "
    "Ne conserve ni secrets ni données sensibles. Fournis une citation exacte "
    "issue du message courant pour justifier tout enregistrement. "
    "Si tu appelles l'outil, attends son retour avant de confirmer. "
    "La réponse de l'outil indique enregistré, déjà présent, refusé ou échec ; "
    "ne prétends pas qu'une écriture a réussi en cas de doute. "
    "Dans les salons publics, ne révèle aucune information privée issue "
    "d'autres identités, canaux ou conversations."
)
