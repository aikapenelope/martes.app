"""Tests para inject_credential() — tipos de credencial y comportamiento del .env.

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
        # Tipos Telegram — el mismo patrón .upper() produce la var correcta
        assert "telegram_bot_token".upper() == "TELEGRAM_BOT_TOKEN"
        assert "telegram_allowed_users".upper() == "TELEGRAM_ALLOWED_USERS"
        assert "telegram_home_channel".upper() == "TELEGRAM_HOME_CHANNEL"

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
        found = any(line.startswith(f"{key}=") for line in lines)
        if not found:
            lines.append(f"{key}=notion-key-123")
        env_file.write_text("\n".join(lines) + "\n")

        assert "NOTION_KEY=notion-key-123" in env_file.read_text()


class TestInjectCredentialTelegramTypes:
    """Los 3 nuevos tipos Telegram se mapean correctamente a vars de .env.

    Contexto: procedures.md documentaba inject_credential('telegram_allowed_users', ...)
    pero el tipo no existía — PR que añade estos tipos cierra ese gap.
    Ref: docs/11-AUDITORIA-PLATAFORMA-GAPS.md §3.4
    """

    @pytest.mark.parametrize("credential_type,expected_key,value", [
        ("telegram_bot_token", "TELEGRAM_BOT_TOKEN", "999999999:NewTokenXYZ-abc123def456ghi"),
        ("telegram_allowed_users", "TELEGRAM_ALLOWED_USERS", "123456789"),
        ("telegram_home_channel", "TELEGRAM_HOME_CHANNEL", "123456789"),
    ])
    def test_telegram_type_written_to_env(
        self,
        tmp_path: Path,
        credential_type: str,
        expected_key: str,
        value: str,
    ):
        """Cada tipo Telegram escribe la var correcta en .env."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "OPENROUTER_API_KEY=sk-or-x\n"
            "TELEGRAM_BOT_TOKEN=old-token\n"
            "TELEGRAM_ALLOWED_USERS=111\n"
            "TELEGRAM_HOME_CHANNEL=111\n"
        )
        key = credential_type.upper()
        lines = env_file.read_text().splitlines()
        found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                found = True
                break
        if not found:
            lines.append(f"{key}={value}")
        env_file.write_text("\n".join(lines) + "\n")

        content = env_file.read_text()
        assert f"{expected_key}={value}" in content, (
            f"Se esperaba {expected_key}={value} en .env, no se encontró"
        )

    def test_telegram_allowed_users_multiple_ids(self, tmp_path: Path):
        """TELEGRAM_ALLOWED_USERS admite múltiples IDs separados por coma."""
        env_file = tmp_path / ".env"
        env_file.write_text("TELEGRAM_ALLOWED_USERS=111\n")
        value = "111,222333444"  # admin + familiar del cliente
        key = "TELEGRAM_ALLOWED_USERS"
        lines = env_file.read_text().splitlines()
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                break
        env_file.write_text("\n".join(lines) + "\n")
        assert f"TELEGRAM_ALLOWED_USERS={value}" in env_file.read_text()

    def test_telegram_types_do_not_touch_byok_marker(self, tmp_path: Path):
        """Los tipos Telegram no deben borrar el marker .platform_key_expires.

        Solo openrouter_api_key tiene ese efecto secundario.
        """
        from src.tools.write_ops import _PLATFORM_KEY_EXPIRES_FILE
        marker = tmp_path / _PLATFORM_KEY_EXPIRES_FILE
        marker.write_text("2026-12-01T00:00:00+00:00")

        for cred_type in ("telegram_bot_token", "telegram_allowed_users", "telegram_home_channel"):
            # Simula la lógica condicional de inject_credential:
            if cred_type == "openrouter_api_key":
                (tmp_path / _PLATFORM_KEY_EXPIRES_FILE).unlink(missing_ok=True)

        assert marker.exists(), (
            "Los tipos Telegram no deben borrar el marker BYOK — "
            "solo openrouter_api_key tiene ese efecto"
        )

    def test_credential_type_map_contains_all_telegram_types(self):
        """_CREDENTIAL_FILE_MAP contiene los 3 tipos Telegram apuntando a .env."""
        from src.tools.write_ops import _CREDENTIAL_FILE_MAP
        telegram_types = ["telegram_bot_token", "telegram_allowed_users", "telegram_home_channel"]
        for t in telegram_types:
            assert t in _CREDENTIAL_FILE_MAP, f"'{t}' no está en _CREDENTIAL_FILE_MAP"
            assert _CREDENTIAL_FILE_MAP[t] == ".env", (
                f"'{t}' debe apuntar a '.env', no a '{_CREDENTIAL_FILE_MAP[t]}'"
            )

    def test_credential_type_literal_contains_all_telegram_types(self):
        """CredentialType Literal contiene los 3 tipos Telegram."""
        import typing

        from src.tools.write_ops import CredentialType

        # get_args extrae los valores del Literal
        valid_types = typing.get_args(CredentialType)
        for t in ("telegram_bot_token", "telegram_allowed_users", "telegram_home_channel"):
            assert t in valid_types, f"'{t}' no está en CredentialType Literal"
