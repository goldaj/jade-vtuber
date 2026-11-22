"""NEW-20: bounded, deterministic explanations of delivery/runtime failures.

No provider calls, no exception strings, no sensitive identifiers in user text.
These messages describe attempts, never claim successful delivery or recovery.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass(frozen=True)
class Incident:
    code: str
    message: str
    retryable: bool = True

    def payload(self) -> dict:
        return {"incident_code": self.code, "message": self.message,
                "retryable": self.retryable}


_TIMEOUT = Incident(
    "timeout",
    "Jade n'a pas pu terminer cette demande à temps. La réponse n'a pas été confirmée.")
_BUSY = Incident(
    "busy",
    "Jade traite déjà trop de demandes. Celle-ci n'a pas été prise en charge.")
_CONNECTION = Incident(
    "connection",
    "La connexion nécessaire à cette réponse est momentanément indisponible.")
_PERMISSION = Incident(
    "permission",
    "Cette action n'a pas pu être réalisée avec les autorisations actuelles.",
    retryable=False)
_PROVIDER_LIMIT = Incident(
    "provider_limit",
    "Le service nécessaire a temporairement limité les requêtes de Jade.")
_UNAVAILABLE = Incident(
    "unavailable",
    "Jade n'a pas pu terminer cette demande. Le service est momentanément indisponible.")


def explain_incident(error: BaseException) -> Incident:
    """Classify by trusted type/status only. Do not reveal error messages."""
    if isinstance(error, (TimeoutError, asyncio.TimeoutError)):
        return _TIMEOUT
    if isinstance(error, asyncio.QueueFull):
        return _BUSY
    if isinstance(error, PermissionError):
        return _PERMISSION
    if isinstance(error, ConnectionError):
        return _CONNECTION

    # SDK error classes differ across supported versions. Status is safer
    # than supplier-specific messages and requires no network or dependencies.
    status = getattr(error, "status_code", None)
    if type(status) is int:
        if status == 429:
            return _PROVIDER_LIMIT
        if status in (401, 403):
            return _PERMISSION
        if status in (408, 504):
            return _TIMEOUT
        if 500 <= status <= 599:
            return _UNAVAILABLE
    return _UNAVAILABLE


def incident_for_client(error: BaseException) -> dict:
    """Append stable public fields without breaking legacy JSON error codes."""
    return explain_incident(error).payload()
