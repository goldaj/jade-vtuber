"""Live voice selection and an offline preparation kit for Jade's own voice.

Catalogue checked against the official Live reference on 2026-11-26. Aube is a
ChatGPT voice; there is no documented public API identifier or Aube/Brise alias.
Nothing in this module creates a voice or opens a billable preview session.
"""
from __future__ import annotations

from dataclasses import dataclass
import re


BUILTIN_LIVE_VOICES = frozenset({
    "alloy", "ash", "ballad", "beacon", "bossa", "brise", "calandria", "cedar",
    "cinder", "compas", "coral", "delta", "destello", "echo", "flitz", "gleam",
    "halo", "harema", "hornero", "juni", "luciernaga", "marin", "meridian",
    "nira", "noeul", "nuri", "pearl", "quartz", "ripple", "sage", "shida",
    "shimmer", "sillage", "stone", "tempo", "verse", "vesper", "willow",
})

JADE_VOICE_PROMPT = (
    "Une voix féminine de jeune adulte, originale, francophone native, avec une "
    "prononciation française naturelle. Timbre clair, chaleureux et léger, "
    "expressif sans exagération. Une énergie vive et malicieuse pour les échanges "
    "enjoués ; une diction posée, douce et attentive pour les sujets sérieux. "
    "Rythme conversationnel souple, respirations discrètes, articulation nette. "
    "Ne pas imiter une personne réelle ni reproduire une voix existante."
)

VOICE_REVIEW_CORPUS = (
    ("salutation", "Salut, c’est Jade. Tu veux me raconter ta journée ?"),
    ("plaisanterie", "J’avais prévu une réponse très sérieuse… puis tu es arrivé."),
    ("récit", "La pluie glissait sur les vitres. Au loin, une lumière restait allumée."),
    ("sérieux", "Prends ton temps. On peut regarder ce qui te préoccupe, une étape à la fois."),
    ("phrase_longue", "Pour préparer notre prochaine conversation, je vais garder les "
     "éléments utiles, vérifier ce qui reste incertain et te laisser choisir la suite."),
    ("interruption", "Commençons par le premier point, puis nous passerons au deuxième."),
    ("reprise", "D’accord, je reprends : c’est jeudi que tu préfères, et non vendredi."),
)


@dataclass(frozen=True)
class LiveVoice:
    """The actual configured voice, never a hidden fallback or display alias."""

    name: str = "brise"
    custom_id: str = ""

    def validate(self) -> None:
        if not isinstance(self.name, str) or not isinstance(self.custom_id, str):
            raise ValueError("Live voice names and IDs must be strings")
        if self.custom_id:
            if not isinstance(self.custom_id, str) or not re.fullmatch(
                    r"[A-Za-z0-9_-]{1,128}", self.custom_id):
                raise ValueError("invalid Live custom voice identifier")
        elif self.name not in BUILTIN_LIVE_VOICES:
            if str(self.name).lower() == "aube":
                raise ValueError("Aube has no verified public Live API identifier")
            raise ValueError("unsupported Live voice; use a documented voice or a custom ID")

    def api_value(self) -> str | dict[str, str]:
        self.validate()
        return {"id": self.custom_id} if self.custom_id else self.name

    def public_status(self) -> dict:
        self.validate()
        fallback = not self.custom_id and self.name == "brise"
        return {
            "requested_prototype": "Aube",
            "aube_api_verified": False,
            "selected": "custom" if self.custom_id else self.name,
            "fallback": fallback,
            "notice": (
                "Aube n’a pas d’identifiant API confirmé. Brise est le recours "
                "technique sélectionné ; aucune équivalence entre elles n’est confirmée."
                if fallback else
                "La voix API configurée est utilisée. Aube reste une préférence "
                "de prototype dont l’accès API n’est pas confirmé."
            ),
        }


def prepare_voice_review(name: str = "Jade candidate 1", prompt: str = JADE_VOICE_PROMPT) -> dict:
    """Prepare the official prompt-to-voice JSON and repeatable listening protocol.

    The creation endpoint returns metadata, not audio. Actual listening belongs
    to the budgeted mobile Live flow after a returned voice ID is configured.
    """
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 64:
        raise ValueError("voice review name must contain between 1 and 64 characters")
    if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 2000:
        raise ValueError("voice review prompt must contain between 1 and 2000 characters")
    return {
        "status": "prepared_only",
        "voice_created": False,
        "audio_listened": False,
        "request": {
            "method": "POST", "url": "https://api.openai.com/v1/audio/voices",
            "json": {"type": "prompt", "name": name.strip(), "prompt": prompt.strip(), "model": "auto"},
        },
        "corpus": [{"scenario": scenario, "text": text} for scenario, text in VOICE_REVIEW_CORPUS],
        "review": {
            "device": "Redmi / même sortie audio et même volume pour chaque candidate",
            "criteria": ["prononciation française", "identité de Jade", "chaleur", "jeu malicieux",
                         "clarté sur phrase longue", "interruption et reprise", "confort d’écoute"],
            "record": ["identifiant voix", "prompt", "date", "candidate retenue", "décision propriétaire"],
        },
        "next_steps": [
            "Créer au plus les candidates nécessaires, avec les accès existants, sans clé nouvelle.",
            "Conserver chaque ID renvoyé ; une nouvelle session réutilise cet ID sans recréer la voix.",
            "Configurer JADE_LIVE_VOICE_ID avec l’ID choisi et fermer toute session avant de changer de voix.",
            "Effectuer les écoutes dans le parcours mobile Live avec ses budgets et contrôles d’arrêt.",
            "Ne pas confondre création de la voix et coût des sessions utilisées pour l’écouter.",
        ],
        "source": "https://developers.openai.com/api/docs/guides/custom-voices",
    }
