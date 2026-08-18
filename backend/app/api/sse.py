"""Utilitaires de sérialisation SSE.

Ce module transforme les événements applicatifs en messages
Server-Sent Events compatibles avec les clients HTTP.
"""

from __future__ import annotations


# Sérialisation


def format_sse_event(
    *,
    event: str,
    data: str
) -> str:
    """Construit un événement Server-Sent Events."""
    return (
        f"event: {event}\n"
        f"data: {data}\n\n"
    )