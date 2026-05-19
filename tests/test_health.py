"""Tests fonctionnels de l'endpoint /health.

Test garanti fonctionnel dès le clone — sert de point de départ pour ajouter
les tests de /predict (à la charge de l'apprenant).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_200() -> None:
    """L'endpoint /health doit répondre 200 OK avec le modèle chargé."""
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["model_loaded"] is True


def test_health_response_schema() -> None:
    """Le schéma de la réponse doit respecter HealthResponse."""
    with TestClient(app) as client:
        response = client.get("/health")
        body = response.json()
        assert set(body.keys()) == {"status", "model_loaded"}
        assert isinstance(body["status"], str)
        assert isinstance(body["model_loaded"], bool)