"""Ephemeral, verified Discord voice/text dialogue routing key.

Not proof of consent, access permission or a durable memory scope.
Only trusted connector code may pass it to Incoming.
"""
import hashlib
import re

_ID = re.compile(r"[1-9][0-9]{0,24}\Z")
_SESSION = re.compile(r"[A-Za-z0-9_-]{16,128}\Z")


def conversation_id(guild_id, voice_channel_id, voice_session_id, account_id):
    """Return an opaque key; a reconnect cannot reuse the prior conversation."""
    ids = (str(guild_id), str(voice_channel_id), str(account_id))
    if (not all(_ID.fullmatch(x) for x in ids)
            or not isinstance(voice_session_id, str)
            or not _SESSION.fullmatch(voice_session_id)):
        return None
    data = "\x1f".join((*ids, voice_session_id)).encode("ascii")
    return "dc-" + hashlib.sha256(data).hexdigest()[:32]
