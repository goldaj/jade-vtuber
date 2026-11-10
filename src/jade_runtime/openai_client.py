"""One OpenAI client policy for the runtime and distributable demo."""
from .config import Settings


def isolated_openai_client(settings: Settings, *, http_client=None):
    """Use the supplied key and OpenAI endpoint, without ambient SDK headers.

    The pinned SDK can inherit OPENAI_CUSTOM_HEADERS, including Authorization.
    A fixed property prevents those values reaching REST and Realtime. System
    proxy/TLS configuration remains the HTTP library's usual behavior.
    """
    from openai import AsyncOpenAI

    class JadeOpenAI(AsyncOpenAI):
        @property
        def default_headers(self):
            return {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": self.user_agent,
            }

    options = {
        "api_key": settings.api_key,
        "timeout": settings.timeout_seconds,
        "max_retries": 0,
        "base_url": "https://api.openai.com/v1",
        "organization": "",
        "project": "",
        "admin_api_key": "",
        "webhook_secret": "",
    }
    if http_client is not None:
        options["http_client"] = http_client
    return JadeOpenAI(**options)
