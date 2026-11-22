"""Conservative, transport-grounded group addressee signals.

No LLM call. Never infer cross-channel context, identity or permission from a
nickname. A reply to another person stays theirs unless Jade is explicitly
addressed. Subject snippets remain from the current authorized channel only.
"""
from __future__ import annotations

import re


def addressed_to_other(message, *, own_user_id=None, bot_name="Jade") -> bool:
    text = getattr(message, "content", "")
    if not isinstance(text, str) or not text.strip():
        return False
    if getattr(message, "guild", None) is None:
        return False
    named = bool(re.search(r"(?<!\w)" + re.escape(bot_name) + r"(?!\w)",
                           text, re.IGNORECASE))
    mentions = getattr(message, "mentions", ()) or ()
    own_mentioned = own_user_id is not None and any(
        getattr(user, "id", None) == own_user_id for user in mentions)
    # A direct call to Jade overrides a third-party mention.
    if named or own_mentioned:
        return False
    if any(type(getattr(user, "id", None)) is int
           and getattr(user, "id") != own_user_id for user in mentions):
        return True
    reference = getattr(message, "reference", None)
    resolved = getattr(reference, "resolved", None)
    author_id = getattr(getattr(resolved, "author", None), "id", None)
    return (type(author_id) is int and author_id > 0
            and author_id != own_user_id)


def local_group_context(message, selected, *, max_chars=600) -> str:
    """The same channel's bounded text, not another person's private history."""
    if getattr(message, "guild", None) is None:
        return ""
    recent = getattr(selected, "context", ()) or ()
    lines = [str(x)[:240] for x in recent[-4:] if isinstance(x, str)]
    return "\n".join(lines)[-max_chars:]
