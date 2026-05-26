"""Tests para get_tenant_config() y get_tenant_env_keys() — herramientas de diagnóstico.

Verifican que:
1. get_tenant_env_keys() NUNCA devuelve valores, solo claves + booleano 'set'
2. get_tenant_config() lee config.yaml y gateway_state.json correctamente
3. Ambas herramientas son robustas ante archivos faltantes o malformados
4. Los indicadores de summary son correctos (has_openrouter_key, etc.)

Ref: docs/11-AUDITORIA-PLATAFORMA-GAPS.md §4.1
"""

import json
from pathlib import Path


class TestGetTenantEnvKeys:
    """get_tenant_env_keys() — solo claves, nunca valores."""

    def _build_tenant_dir(self, tmp_path: Path) -> Path:
        """Helper: crea estructura mínima de tenant en tmp_path."""
        tenant_dir = tmp_path / "t001"
        tenant_dir.mkdir()
        return tenant_dir

    def test_never_returns_values(self, tmp_path: Path):
        """El campo 'key' de cada entrada no debe contener el valor real.

        Invariante de seguridad: el Diagnosticador no debe poder leer
        OPENROUTER_API_KEY ni TELEGRAM_BOT_TOKEN aunque quiera.
        """
        from unittest.mock import patch

        tenant_dir = self._build_tenant_dir(tmp_path)
        env_file = tenant_dir / ".env"
        env_file.write_text(
            "OPENROUTER_API_KEY=sk-or-super-secret-key\n"
            "TELEGRAM_BOT_TOKEN=999999999:ABCDEF123456\n"
        )

        with patch("src.tools.read_ops.settings") as mock_settings:
            mock_settings.tenants_base_path = str(tmp_path)
            from src.tools.read_ops import get_tenant_env_keys
            result = json.loads(get_tenant_env_keys("t001"))

        # Verificar que ningún valor secreto aparece en la respuesta
        result_str = json.dumps(result)
        assert "sk-or-super-secret-key" not in result_str, (
            "El valor de OPENROUTER_API_KEY NO debe aparecer en la respuesta"
        )
        assert "ABCDEF123456" not in result_str, (
            "El valor de TELEGRAM_BOT_TOKEN NO debe aparecer en la respuesta"
        )

    def test_set_true_for_non_empty_value(self, tmp_path: Path):
        """Una key con valor no vacío debe tener set=True."""
        from unittest.mock import patch

        tenant_dir = self._build_tenant_dir(tmp_path)
        (tenant_dir / ".env").write_text("OPENROUTER_API_KEY=sk-or-xxx\n")

        with patch("src.tools.read_ops.settings") as mock_settings:
            mock_settings.tenants_base_path = str(tmp_path)
            from src.tools.read_ops import get_tenant_env_keys
            result = json.loads(get_tenant_env_keys("t001"))

        key_entry = next(k for k in result["keys"] if k["key"] == "OPENROUTER_API_KEY")
        assert key_entry["set"] is True

    def test_set_false_for_empty_value(self, tmp_path: Path):
        """Una key con valor vacío debe tener set=False."""
        from unittest.mock import patch

        tenant_dir = self._build_tenant_dir(tmp_path)
        (tenant_dir / ".env").write_text("OPENROUTER_API_KEY=\n")

        with patch("src.tools.read_ops.settings") as mock_settings:
            mock_settings.tenants_base_path = str(tmp_path)
            from src.tools.read_ops import get_tenant_env_keys
            result = json.loads(get_tenant_env_keys("t001"))

        key_entry = next(k for k in result["keys"] if k["key"] == "OPENROUTER_API_KEY")
        assert key_entry["set"] is False

    def test_comments_and_empty_lines_ignored(self, tmp_path: Path):
        """Líneas de comentario (#) y vacías no se incluyen en keys."""
        from unittest.mock import patch

        tenant_dir = self._build_tenant_dir(tmp_path)
        (tenant_dir / ".env").write_text(
            "# esto es un comentario\n"
            "\n"
            "TELEGRAM_BOT_TOKEN=abc\n"
        )

        with patch("src.tools.read_ops.settings") as mock_settings:
            mock_settings.tenants_base_path = str(tmp_path)
            from src.tools.read_ops import get_tenant_env_keys
            result = json.loads(get_tenant_env_keys("t001"))

        assert result["keys_count"] == 1
        assert result["keys"][0]["key"] == "TELEGRAM_BOT_TOKEN"

    def test_summary_has_openrouter_key_true(self, tmp_path: Path):
        """summary.has_openrouter_key=True cuando OPENROUTER_API_KEY está seteado."""
        from unittest.mock import patch

        tenant_dir = self._build_tenant_dir(tmp_path)
        (tenant_dir / ".env").write_text("OPENROUTER_API_KEY=sk-or-123\n")

        with patch("src.tools.read_ops.settings") as mock_settings:
            mock_settings.tenants_base_path = str(tmp_path)
            from src.tools.read_ops import get_tenant_env_keys
            result = json.loads(get_tenant_env_keys("t001"))

        assert result["summary"]["has_openrouter_key"] is True

    def test_summary_has_openrouter_key_false_when_empty(self, tmp_path: Path):
        """summary.has_openrouter_key=False cuando OPENROUTER_API_KEY está vacío."""
        from unittest.mock import patch

        tenant_dir = self._build_tenant_dir(tmp_path)
        (tenant_dir / ".env").write_text("OPENROUTER_API_KEY=\n")

        with patch("src.tools.read_ops.settings") as mock_settings:
            mock_settings.tenants_base_path = str(tmp_path)
            from src.tools.read_ops import get_tenant_env_keys
            result = json.loads(get_tenant_env_keys("t001"))

        assert result["summary"]["has_openrouter_key"] is False

    def test_missing_env_returns_env_exists_false(self, tmp_path: Path):
        """Si .env no existe, env_exists=False (no es un error crítico)."""
        from unittest.mock import patch

        self._build_tenant_dir(tmp_path)  # tenant dir sin .env

        with patch("src.tools.read_ops.settings") as mock_settings:
            mock_settings.tenants_base_path = str(tmp_path)
            from src.tools.read_ops import get_tenant_env_keys
            result = json.loads(get_tenant_env_keys("t001"))

        assert result["env_exists"] is False
        assert "error" not in result

    def test_nonexistent_tenant_returns_error(self, tmp_path: Path):
        """Si el directorio del tenant no existe, devuelve error."""
        from unittest.mock import patch

        with patch("src.tools.read_ops.settings") as mock_settings:
            mock_settings.tenants_base_path = str(tmp_path)
            from src.tools.read_ops import get_tenant_env_keys
            result = json.loads(get_tenant_env_keys("t999"))

        assert "error" in result


class TestGetTenantConfig:
    """get_tenant_config() — lee config.yaml, gateway_state.json, skills, cron."""

    def _build_tenant_dir(self, tmp_path: Path) -> Path:
        tenant_dir = tmp_path / "t001"
        tenant_dir.mkdir()
        return tenant_dir

    def test_reads_model_from_config_yaml(self, tmp_path: Path):
        """El modelo activo se lee de config.yaml → model.default."""
        from unittest.mock import patch

        tenant_dir = self._build_tenant_dir(tmp_path)
        (tenant_dir / "config.yaml").write_text(
            "model:\n  default: deepseek/deepseek-v4-flash\n"
        )

        with patch("src.tools.read_ops.settings") as mock_settings:
            mock_settings.tenants_base_path = str(tmp_path)
            from src.tools.read_ops import get_tenant_config
            result = json.loads(get_tenant_config("t001"))

        assert result["config"]["model"] == "deepseek/deepseek-v4-flash"

    def test_reads_platforms_from_gateway_state(self, tmp_path: Path):
        """Las plataformas activas se leen de gateway_state.json → platforms."""
        from unittest.mock import patch

        tenant_dir = self._build_tenant_dir(tmp_path)
        (tenant_dir / "gateway_state.json").write_text(
            '{"platforms": {"telegram": {}, "discord": {}}, "version": "v0.14.0"}'
        )

        with patch("src.tools.read_ops.settings") as mock_settings:
            mock_settings.tenants_base_path = str(tmp_path)
            from src.tools.read_ops import get_tenant_config
            result = json.loads(get_tenant_config("t001"))

        assert "telegram" in result["gateway_state"]["platforms"]
        assert "discord" in result["gateway_state"]["platforms"]
        assert result["gateway_state"]["version"] == "v0.14.0"

    def test_counts_installed_skills(self, tmp_path: Path):
        """skills_count refleja los subdirectorios en skills/."""
        from unittest.mock import patch

        tenant_dir = self._build_tenant_dir(tmp_path)
        skills_dir = tenant_dir / "skills"
        skills_dir.mkdir()
        (skills_dir / "notion").mkdir()
        (skills_dir / "airtable").mkdir()

        with patch("src.tools.read_ops.settings") as mock_settings:
            mock_settings.tenants_base_path = str(tmp_path)
            from src.tools.read_ops import get_tenant_config
            result = json.loads(get_tenant_config("t001"))

        assert result["skills_count"] == 2
        assert "notion" in result["skills_installed"]
        assert "airtable" in result["skills_installed"]

    def test_counts_cron_jobs(self, tmp_path: Path):
        """cron_jobs refleja el número de jobs en cron/jobs.json."""
        from unittest.mock import patch

        tenant_dir = self._build_tenant_dir(tmp_path)
        cron_dir = tenant_dir / "cron"
        cron_dir.mkdir()
        (cron_dir / "jobs.json").write_text(
            '[{"id": 1, "expr": "0 9 * * *"}, {"id": 2, "expr": "0 18 * * *"}]'
        )

        with patch("src.tools.read_ops.settings") as mock_settings:
            mock_settings.tenants_base_path = str(tmp_path)
            from src.tools.read_ops import get_tenant_config
            result = json.loads(get_tenant_config("t001"))

        assert result["cron_jobs"] == 2

    def test_missing_files_return_none_not_error(self, tmp_path: Path):
        """Si config.yaml o gateway_state.json no existen, retorna None, no error."""
        from unittest.mock import patch

        self._build_tenant_dir(tmp_path)

        with patch("src.tools.read_ops.settings") as mock_settings:
            mock_settings.tenants_base_path = str(tmp_path)
            from src.tools.read_ops import get_tenant_config
            result = json.loads(get_tenant_config("t001"))

        assert "error" not in result
        assert result["config"] is None
        assert result["gateway_state"] is None
        assert result["skills_count"] == 0
        assert result["cron_jobs"] == 0

    def test_nonexistent_tenant_returns_error(self, tmp_path: Path):
        """Si el directorio del tenant no existe, devuelve error."""
        from unittest.mock import patch

        with patch("src.tools.read_ops.settings") as mock_settings:
            mock_settings.tenants_base_path = str(tmp_path)
            from src.tools.read_ops import get_tenant_config
            result = json.loads(get_tenant_config("t999"))

        assert "error" in result
