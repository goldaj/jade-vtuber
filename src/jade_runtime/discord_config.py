"""Single operator switch for every Discord transport.

Change DISCORD_ENABLED and restart Jade. True enables the selected Discord
transports with automatic monthly Live/classic routing; False disables Discord
entirely, including when --all-channels or --discord is requested. Mobile does
not read this switch. Historical private Discord enable flags are ignored.
"""

DISCORD_ENABLED = True


def is_discord_enabled() -> bool:
    if type(DISCORD_ENABLED) is not bool:
        raise ValueError("DISCORD_ENABLED must be True or False")
    return DISCORD_ENABLED


def selected_discord_channels(enabled: bool, text: bool, voice: bool) -> tuple[bool, bool]:
    """Apply the master switch without enabling an unrequested transport."""
    if type(enabled) is not bool:
        raise ValueError("Discord enable switch must be boolean")
    return bool(enabled and text), bool(enabled and voice)
