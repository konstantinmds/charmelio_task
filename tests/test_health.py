"""Tests for health endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


class TestLivenessEndpoint:
    """Tests for /health liveness endpoint."""

    def test_health_check_returns_ok(self):
        """Liveness endpoint returns 200 with status ok."""
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}


class TestReadinessEndpoint:
    """Tests for /health/ready readiness endpoint."""

    def test_readiness_all_ok(self, mock_db_session):
        """Readiness returns 200 when all dependencies are available."""
        mock_minio = MagicMock()
        mock_minio.bucket_exists.return_value = True
        mock_temporal = MagicMock()

        with patch("app.routes.health.AsyncSessionLocal", return_value=mock_db_session):
            with TestClient(app, raise_server_exceptions=False) as client:
                app.state.minio = mock_minio
                app.state.temporal = mock_temporal

                response = client.get("/health/ready")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "ok"

    def test_readiness_db_failure(self, mock_db_session):
        """Readiness returns 503 when database is unavailable."""
        mock_db_session.execute = AsyncMock(side_effect=Exception("Connection refused"))
        mock_minio = MagicMock()
        mock_temporal = MagicMock()

        with patch("app.routes.health.AsyncSessionLocal", return_value=mock_db_session):
            with TestClient(app, raise_server_exceptions=False) as client:
                app.state.minio = mock_minio
                app.state.temporal = mock_temporal

                response = client.get("/health/ready")

                assert response.status_code == 503
                assert "error" in response.json()["checks"]["database"]

    def test_readiness_storage_not_configured(self, mock_db_session):
        """Readiness returns 503 when storage is not configured."""
        mock_temporal = MagicMock()

        with patch("app.routes.health.AsyncSessionLocal", return_value=mock_db_session):
            with TestClient(app, raise_server_exceptions=False) as client:
                app.state.minio = None
                app.state.temporal = mock_temporal

                response = client.get("/health/ready")

                assert response.status_code == 503
                assert response.json()["checks"]["storage"] == "not configured"

    def test_readiness_temporal_not_connected(self, mock_db_session):
        """Readiness returns 503 when Temporal is not connected."""
        mock_minio = MagicMock()

        with patch("app.routes.health.AsyncSessionLocal", return_value=mock_db_session):
            with TestClient(app, raise_server_exceptions=False) as client:
                app.state.minio = mock_minio
                app.state.temporal = None

                response = client.get("/health/ready")

                assert response.status_code == 503
                assert response.json()["checks"]["temporal"] == "not connected"
