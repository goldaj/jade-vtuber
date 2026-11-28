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

# The owner auditioned these session instructions with the already saved voice.
PETILLANTE_SESSION_PROMPT = (
    "Voix féminine jeune très aigüe pour son âge, façon personnage de manga, "
    "mais en français de France, avec une diction naturelle et des fins de phrase bien audibles. "
    "Registre très haut, timbre clair, avec un léger sourire qui s’entend au détour d’une phrase. "
    "Débit vif mais souple, comme une streameuse qui réagit sur le moment. Une petite pause "
    "avant une pique, une intonation qui monte de surprise puis retombe. Elle sonne sûre d’elle, "
    "malicieuse et proche de son interlocuteur. Garde une articulation nette, des respirations "
    "discrètes et une énergie crédible sur une conversation entière."
)

# Friponne's voice design, with delivery paced separately at session startup.
FRIPONNE_SESSION_PROMPT = (
    "Neutral accent. approximately 20s. feminine voice. bright timbre. smooth vocal texture. "
    "very high pitch. moderate loudness. fast speech rate. high distinctiveness.\n"
    "Jeune femme adulte, locutrice native du français de France. Accent naturel de Paris et de sa région. "
    "Registre parlé très aigu, timbre fin, brillant et sonore. Le sourire donne aux voyelles un éclat "
    "légèrement nasal. Elle parle tout près du micro, à volume ordinaire. Dans le feu du jeu, elle part "
    "vite, rebondit vers l’aigu sur le mot qui la surprend et lance ses répliques avec malice. "
    "Même dans un aparté, sa voix reste haute et sa diction francilienne."
)

FRIPONNE_PACE_PROMPT = (
    "Parle le plus vite possible dès le premier mot et jusqu’au dernier. "
    "C’est ton débit habituel à chaque réponse, même pour une salutation, un aparté ou une réponse longue. "
    "Tu vas en mode \"rap god\". "
    "Enchaîne les mots et les phrases avec très peu de pauses. "
    "Garde cette vitesse sur toutes tes expressions et intentions. "
    "Fais passer l’émotion par le timbre, le volume et la mélodie de la voix."
)

LIVE_VOICE_STYLE_PROMPTS = {
    "petillante": PETILLANTE_SESSION_PROMPT,
    "friponne": FRIPONNE_SESSION_PROMPT,
}

LIVE_DELIVERY_PROMPT = (
    "Par défaut, parle légèrement plus vite qu'en conversation ordinaire, avec des pauses "
    "brèves, une articulation nette et des fins de phrase audibles. Fais entendre l'intention "
    "par le rythme et la mélodie : enjouée, laisse entendre un sourire malicieux ; enthousiaste, "
    "donne de l'élan sans hausser le volume ; curieuse, marque un intérêt vif et une légère "
    "montée sur les questions ; tendre, adoucis brièvement le timbre ; rassurante, ralentis "
    "légèrement avec une cadence stable ; sérieuse, parle d'un ton posé et précis ; "
    "triste, adoucis le timbre avec un rythme légèrement ralenti et des fins de phrase "
    "descendantes, sans sanglots ni chuchotements ; en colère, marque des accents fermes "
    "et une articulation plus incisive, sans crier ni changer d'identité vocale. "
    "Exprime l'émotion de ta réponse : évoquer la tristesse ou la colère de quelqu'un "
    "ne t'impose pas cette émotion ; pour réconforter, garde une intention rassurante. "
    "Pour les échanges neutres, garde une diction conversationnelle naturelle."
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
    to the mobile Live flow after a returned voice ID is configured.
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
            "Effectuer les écoutes dans le parcours mobile Live avec ses contrôles d’arrêt.",
            "Ne pas confondre création de la voix et coût des sessions utilisées pour l’écouter.",
        ],
        "source": "https://developers.openai.com/api/docs/guides/custom-voices",
    }
