"""Compatibility import for the shared Jade Realtime speech adapter."""
from src.jade_runtime.realtime_tts import RealtimeTTS, RealtimeTTSError, SpokenAudio, _words

__all__ = ["RealtimeTTS", "RealtimeTTSError", "SpokenAudio"]
