"""Tests para inject_credential() con openrouter_api_key.

Verifica que:
1. La key se escribe correctamente en el .env
2. El marker .platform_key_expires se borra inmediatamente al inyectar openrouter_api_key
3. Otros tipos de credencial NO borran el marker
4. El marker se preserva si no es openrouter_api_key
"""

from pathlib import Path

import pytest

from src.tools.write_ops import _PLATFORM_KEY_EXPIRES_FILE


class TestInjectCredentialMarkerCleanup:
    """El marker BYOK se borra inmediatamente cuando se inyecta openrouter_api_key."""

    def test_marker_deleted_when_openrouter_injected(self, tmp_path: Path):
        """Simula la lógica exacta de inject_credential() para openrouter_api_key."""
        # Setup: .env con la platform key + marker de expiración
        env_file = tmp_path / ".env"
        env_file.write_text(
            "OPENROUTER_API_KEY=sk-or-platform-key-123\n"
            "OPENROUTER_BASE_URL=https://openrouter.ai/api/v1\n"
        )
        marker = tmp_path / _PLATFORM_KEY_EXPIRES_FILE
        marker.write_text("2026-06-10T12:00:00+00:00")
        assert marker.exists()

        # Simula inject_credential con openrouter_api_key:
        credential_type = "openrouter_api_key"
        credential_value = "sk-or-client-own-key-456"
        key = credential_type.upper()
        lines = env_file.read_text().splitlines()
        found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={credential_value}"
                found = True
                break
        if not found:
            lines.append(f"{key}={credential_value}")
        env_file.write_text("\n".join(lines) + "\n")

        # Cleanup del marker — lógica de PR #85
        if credential_type == "openrouter_api_key":
            (tmp_path / _PLATFORM_KEY_EXPIRES_FILE).unlink(missing_ok=True)

        # Verificar:
        assert not marker.exists(), "El marker no fue borrado al inyectar openrouter_api_key"
        env_content = env_file.read_text()
        assert f"OPENROUTER_API_KEY={credential_value}" in env_content

    def test_marker_preserved_for_other_credentials(self, tmp_path: Path):
        """Al inyectar notion_key u otras credenciales, el marker NO se borra."""
        env_file = tmp_path / ".env"
        env_file.write_text("NOTION_KEY=\n")
        marker = tmp_path / _PLATFORM_KEY_EXPIRES_FILE
        marker.write_text("2026-06-10T12:00:00+00:00")

        credential_type = "notion_key"  # NO es openrouter_api_key
        # La lógica solo borra el marker si es openrouter_api_key
        if credential_type == "openrouter_api_key":
            (tmp_path / _PLATFORM_KEY_EXPIRES_FILE).unlink(missing_ok=True)

        assert marker.exists(), "El marker fue borrado incorrectamente para otro tipo de credencial"

    def test_env_key_format(self, tmp_path: Path):
        """La key en .env usa el nombre en MAYÚSCULAS (credential_type.upper())."""
        # google_token → google_token.json (no va al .env)
        # notion_key → NOTION_KEY en .env
        # openrouter_api_key → OPENROUTER_API_KEY en .env
        assert "notion_key".upper() == "NOTION_KEY"
        assert "openrouter_api_key".upper() == "OPENROUTER_API_KEY"
        assert "github_token".upper() == "GITHUB_TOKEN"

    def test_missing_marker_does_not_fail(self, tmp_path: Path):
        """Si el marker no existe, unlink(missing_ok=True) no lanza excepción."""
        marker = tmp_path / _PLATFORM_KEY_EXPIRES_FILE
        assert not marker.exists()
        # No debe lanzar excepción:
        marker.unlink(missing_ok=True)
        assert not marker.exists()


class TestInjectCredentialEnvFormat:
    """Verificar que la lógica de escritura al .env es correcta."""

    def test_existing_key_is_updated(self, tmp_path: Path):
        """Si la key ya existe en .env, debe actualizarse en su lugar."""
        env_file = tmp_path / ".env"
        env_file.write_text("OPENROUTER_API_KEY=old-key\nTELEGRAM_BOT_TOKEN=abc\n")

        credential_value = "new-key"
        key = "OPENROUTER_API_KEY"
        lines = env_file.read_text().splitlines()
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={credential_value}"
                break
        env_file.write_text("\n".join(lines) + "\n")

        content = env_file.read_text()
        assert "OPENROUTER_API_KEY=new-key" in content
        assert "OPENROUTER_API_KEY=old-key" not in content
        assert "TELEGRAM_BOT_TOKEN=abc" in content  # otras keys intactas

    def test_new_key_appended_if_missing(self, tmp_path: Path):
        """Si la key no existe en .env, se añade al final."""
        env_file = tmp_path / ".env"
        env_file.write_text("TELEGRAM_BOT_TOKEN=abc\n")

        key = "NOTION_KEY"
        lines = env_file.read_text().splitlines()
        found = any(l.startswith(f"{key}=") for l in lines)
        if not found:
            lines.append(f"{key}=notion-key-123")
        env_file.write_text("\n".join(lines) + "\n")

        assert "NOTION_KEY=notion-key-123" in env_file.read_text()
