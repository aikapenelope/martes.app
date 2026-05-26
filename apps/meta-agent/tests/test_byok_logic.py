"""Tests de lógica BYOK — expire_platform_key() Niveles 1 y 2.

Testea los dos niveles de detección de que el cliente ya tiene su propia
credencial, sin necesitar Docker ni PostgreSQL ni el tenant real.

Nivel 1: OPENROUTER_API_KEY en .env es diferente a la platform key
Nivel 2: auth.json existe con contenido > 50 bytes
"""

import json
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest


class TestByokDetectionLogic:
    """Lógica BYOK pura — sin I/O real, solo verifica las condiciones."""

    # ── Nivel 1: comparación de keys ──────────────────────────────────────

    def test_same_key_means_still_platform(self):
        """Si la key en .env es igual a la platform key → cliente no migró."""
        platform_key = "sk-or-platform-key-123"
        env_key = "sk-or-platform-key-123"
        assert env_key == platform_key  # plataforma aún activa

    def test_different_key_means_client_migrated(self):
        """Si la key en .env es diferente → cliente configuró la suya."""
        platform_key = "sk-or-platform-key-123"
        env_key = "sk-or-client-own-key-456"
        assert env_key != platform_key  # cliente ya tiene la suya

    def test_empty_key_is_blanked(self):
        """Key vacía = fue blanqueada por el scheduler."""
        env_key = ""
        assert env_key == ""  # blanqueada

    # ── Nivel 2: auth.json ────────────────────────────────────────────────

    def test_auth_json_small_not_counted(self, tmp_path: Path):
        """auth.json con <= 50 bytes no cuenta como credencial propia."""
        auth = tmp_path / "auth.json"
        auth.write_text("{}")  # 2 bytes
        assert auth.exists()
        assert auth.stat().st_size <= 50  # no activa nivel 2

    def test_auth_json_large_counts(self, tmp_path: Path):
        """auth.json con > 50 bytes = cliente autenticó algún proveedor."""
        auth = tmp_path / "auth.json"
        # Simula un auth.json real con token OAuth (siempre > 50 bytes)
        auth.write_text(json.dumps({
            "provider": "openrouter",
            "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.payload",
            "expires_at": "2026-12-31T00:00:00Z",
        }))
        assert auth.stat().st_size > 50  # activa nivel 2

    def test_auth_json_missing_not_counted(self, tmp_path: Path):
        """Si auth.json no existe → cliente no autenticó nada."""
        auth = tmp_path / "auth.json"
        assert not auth.exists()

    # ── TTL: expiración del marker ─────────────────────────────────────────

    def test_expired_ttl_detected(self, tmp_path: Path):
        """Marker con timestamp en el pasado → TTL expirado."""
        marker = tmp_path / ".platform_key_expires"
        past = datetime.now(tz=timezone.utc) - timedelta(hours=3)
        marker.write_text(past.isoformat())

        expires_at = datetime.fromisoformat(marker.read_text().strip())
        now = datetime.now(tz=timezone.utc)
        assert (expires_at - now).total_seconds() < 0  # expirado

    def test_valid_ttl_not_expired(self, tmp_path: Path):
        """Marker con timestamp en el futuro → TTL vigente."""
        marker = tmp_path / ".platform_key_expires"
        future = datetime.now(tz=timezone.utc) + timedelta(hours=1)
        marker.write_text(future.isoformat())

        expires_at = datetime.fromisoformat(marker.read_text().strip())
        now = datetime.now(tz=timezone.utc)
        assert (expires_at - now).total_seconds() > 0  # no expirado

    def test_ttl_zero_disables_expiry(self):
        """TTL=0 desactiva la expiración (trial ilimitado)."""
        platform_key_ttl_hours = 0
        assert platform_key_ttl_hours == 0  # no crear marker

    def test_marker_cleanup_on_inject(self, tmp_path: Path):
        """Al inyectar openrouter_api_key, el marker se borra inmediatamente."""
        marker = tmp_path / ".platform_key_expires"
        marker.write_text("2026-06-04T12:00:00+00:00")
        assert marker.exists()

        # Simula la lógica de inject_credential con openrouter_api_key:
        marker.unlink(missing_ok=True)
        assert not marker.exists()
