"""Event-driven spontaneous turns; no periodic model wake-ups."""
import asyncio
from datetime import datetime
import logging
import re
import time
from .paris_clock import paris_date

from .messages import Incoming

LOG=logging.getLogger("jade.initiatives")


class InitiativeScheduler:
    def __init__(self, guard, *, daily_usd=0, monthly_usd=0,
                 quote_usd="0.10",cooldown_seconds=1200,clock=time.monotonic):
        self.guard=guard
        self.daily_usd,self.monthly_usd=daily_usd,monthly_usd
        self.quote_usd=quote_usd
        self.cooldown_seconds,self.clock=cooldown_seconds,clock
        self._last={}
        # Waiting for a HUMAN reaction: no self-follow-up while unanswered.
        self._awaiting_reply = {}
        self._room_epoch = {}

    async def voice_join(self, member, before, after, *, channel_id,
                         own_bot_id=None, voice_session_id=""):
        dest=getattr(after,"channel",None)
        previous=getattr(before,"channel",None)
        user_id=getattr(member,"id",None)
        if (self.guard is None or dest is None or dest == previous
                or getattr(dest,"id",None)!=channel_id
                or getattr(member,"bot",True) or type(user_id) is not int
                or user_id<=0 or user_id==own_bot_id):
            return None
        guild=getattr(dest,"guild",None)
        if guild is None or type(getattr(guild,"id",None)) is not int:
            return None
        channel=str(channel_id)
        if channel in self._awaiting_reply:
            return None  # No self-follow-up until a human reacts or the room empties.
        if self.clock()-self._last.get(channel,float("-inf")) < self.cooldown_seconds:
            return None
        day=paris_date().isoformat()
        event_id=(f"join:{guild.id}:{channel}:{user_id}:{day}:"
                  f"{self._room_epoch.get(channel, 0)}")
        try:
            allowed=await asyncio.to_thread(
                self.guard.reserve,"initiative",event_id,
                quote_usd=self.quote_usd,daily_usd=self.daily_usd,
                monthly_usd=self.monthly_usd)
        except asyncio.CancelledError:
            raise
        except Exception:
            LOG.warning("Initiative budget unavailable")
            return None
        if not allowed:
            return None
        self._last[channel]=self.clock()
        self._awaiting_reply[channel] = self.clock()
        members = getattr(dest, "members", None)
        audible = (isinstance(members, (list, tuple))
                   and any(getattr(p, "id", None) == user_id
                           and getattr(p, "bot", True) is False for p in members)
                   and isinstance(voice_session_id, str)
                   and re.fullmatch(r"[A-Za-z0-9_-]{16,128}", voice_session_id))
        return Incoming(
            platform="discord_voice" if audible else "discord",
            author="Événement système Jade",
            text=("Une personne vient d'entrer dans ton salon vocal Discord. "
                  "Tu peux proposer un salut bref à l\u0027oral dans CE salon "
                  "sans aucun souvenir privé ni prétendre connaître l'arrivant."),
            channel=channel,message_id="jade-initiative-"+str(user_id)+"-"+day,
            speaker_id=user_id if audible else None,
            voice_session_id=voice_session_id if audible else "",
            system_initiative=True, force_reply=True)

    def human_replied(self, channel: str, *, verified: bool = True) -> bool:
        """A real human interaction ends the unanswered initiative.

        Called only by authenticated Discord text or accepted Discord STT,
        never by bot messages or the synthetic initiative itself.
        """
        if not verified or channel not in self._awaiting_reply:
            return False
        self._awaiting_reply.pop(channel, None)
        return True

    def waiting_for_reply(self, channel: str) -> bool:
        return channel in self._awaiting_reply

    def room_emptied(self, channel: str) -> None:
        """A future distinct visit is a new event, not a self-follow-up."""
        self._awaiting_reply.pop(channel, None)
        self._last.pop(channel, None)
        self._room_epoch[channel] = self._room_epoch.get(channel, 0) + 1
