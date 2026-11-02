from src.utility.private_config import environ

# You're Twitch Token
TWITCH_TOKEN = str(environ("TWITCH_TOKEN", ""))
# Your TWITCH Channel Name
TWITCH_CHANNEL = str(environ("TWITCH_CHANNEL", ""))
# Your OpenAI API Key
OPENAI_API_KEY = str(environ("OPENAI_API_KEY", ""))
# Your BOT_NAME, example = Neuro-sama
BOT_NAME = str(environ("BOT_NAME", ""))
# Your ELEVENLABS_API_KEY, example = AAAAA
ELEVENLABS_API_KEY = str(environ("ELEVENLABS_API_KEY", ""))
# Your ELEVENLABS_VOICE_ID, example = BBBBB
ELEVENLABS_VOICE_ID = str(environ("ELEVENLABS_VOICE_ID", ""))
# Your ELEVENLABS_WEBSOCKET_URL, example = ws://localhost:7580
ELEVENLABS_WEBSOCKET_URL = str(environ("ELEVENLABS_WEBSOCKET_URL", ""))
TWITCH_CLIENT_ID = str(environ("TWITCH_CLIENT_ID", ""))
# twitch client secret to get token
TWITCH_CLIENT_SECRET = str(environ("TWITCH_CLIENT_SECRET", ""))
# twitch refresh token when needed
TWITCH_REFRESH_TOKEN = str(environ("TWITCH_REFRESH_TOKEN", ""))
# Your token discord to connect to discord server
DISCORD_TOKEN = str(environ("DISCORD_TOKEN", ""))
# Discord guild id
DISCORD_GUILD = int(environ("DISCORD_GUILD", "0") or 0)
# Discord voice channel id
DISCORD_VOICE_CHANNEL = int(environ("DISCORD_VOICE_CHANNEL", "0") or 0)
