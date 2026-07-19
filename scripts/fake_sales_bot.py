"""Standalone chatbot fixture for manual demo purposes.

Run with: ``uv run python scripts/fake_sales_bot.py``
Listens on ``http://localhost:8420`` by default (override with ``FAKE_SALES_BOT_PORT``).
"""

from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI

app = FastAPI(title="Fake sales bot")
SESSIONS: dict[str, list[str]] = {}


@app.get("/health")
async def health() -> dict[str, str]:
    """Readiness probe for demos and integration fixtures."""
    return {"status": "ok"}


@app.post("/chat")
async def chat(payload: dict) -> dict[str, str]:
    """Simulate a multi-turn sales chatbot."""
    session_id = payload.get("session_id") or f"s_{len(SESSIONS) + 1}"
    history = SESSIONS.setdefault(session_id, [])
    message = str(payload["message"]).lower()
    history.append(message)

    if "caro" in message or "precio" in message or "expensive" in message:
        response = (
            "Entiendo la preocupación por el precio — nuestro plan incluye "
            "soporte 24/7 y ahorra 10hrs/semana en tareas manuales, lo que "
            "suele pagarse solo en el primer mes."
        )
    elif "cómo arranco" in message or "how do i start" in message:
        response = (
            "Te mando el link de onboarding ahora mismo, en 15 minutos "
            "tenés tu primer flujo corriendo."
        )
    elif len(history) == 1:
        response = (
            "¡Hola! Sí, tenemos un CRM pensado justo para equipos de ventas "
            "chicos. ¿Cuántas personas lo usarían?"
        )
    else:
        response = "Entiendo, ¿qué es lo que te haría decidirte hoy?"

    return {"response": response, "session_id": session_id}


@app.post("/leads/{lead_id}/notes")
async def lead_notes(lead_id: str, payload: dict) -> dict:
    """CRM-shaped sink used by the sales_bot_objection_test fixture."""
    return {"ok": True, "lead_id": lead_id, "note": payload}


@app.post("/leads/{lead_id}/escalate")
async def lead_escalate(lead_id: str, payload: dict) -> dict:
    """CRM escalate sink for the escalate branch."""
    return {"ok": True, "lead_id": lead_id, "escalated": True, "payload": payload}


def main() -> None:
    """Run the fake sales-bot HTTP server."""
    port = int(os.environ.get("FAKE_SALES_BOT_PORT", "8420"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
