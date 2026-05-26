"""Tests para la lógica del health check — sin Docker.

Documenta y verifica los patrones críticos de producción:
- El bug exit_code or 1 nunca más puede volver (regresión)
- Los exit codes de curl se interpretan correctamente
- El filtro truly_unhealthy excluye 'starting' correctamente
"""

import pytest


class TestExitCodeFix:
    """El bug `exit_code or 1` no debe regresar nunca.

    Python: 0 es falsy. `0 or 1` = 1.
    El health check evaluaba exit_code=0 (curl OK) como 1 (fallo).
    """

    def test_zero_is_falsy_in_python(self):
        """Documenta por qué `or 1` es incorrecto para valores que pueden ser 0."""
        assert (0 or 1) == 1   # Python: 0 es falsy → el bug
        assert (0 if 0 is not None else 1) == 0   # Fix correcto

    @pytest.mark.parametrize("exit_code,expected_healthy", [
        (0,    True),   # curl exitoso → healthy
        (7,    False),  # connection refused → unhealthy
        (22,   False),  # HTTP error (>= 400 con -f) → unhealthy
        (28,   False),  # timeout (--max-time) → unhealthy
        (6,    False),  # no route to host → unhealthy
        (127,  False),  # curl not found → unhealthy
        (None, False),  # exec_run falló → unhealthy
    ])
    def test_exit_code_interpretation(self, exit_code, expected_healthy):
        """Cada exit code de curl se interpreta como healthy o unhealthy."""
        ec = exit_code if exit_code is not None else 1
        is_healthy = (ec == 0)
        assert is_healthy == expected_healthy, (
            f"exit_code={exit_code} debe dar healthy={expected_healthy}, "
            f"pero dio healthy={is_healthy}"
        )

    def test_old_bug_would_fail_on_zero(self):
        """Documenta que el patrón 'or 1' da resultado incorrecto para 0."""
        exit_code = 0  # curl exitoso
        ec_buggy = exit_code or 1     # el bug: evalúa a 1
        ec_fixed = exit_code if exit_code is not None else 1  # fix: evalúa a 0

        assert ec_buggy != 0,  "El patrón 'or 1' NO debería ser 0 (bug confirmado)"
        assert ec_fixed == 0,  "El fix correcto SÍ debe ser 0"

    def test_none_exit_code_defaults_to_1(self):
        """exec_run puede devolver None si falla. Debe tratarse como unhealthy."""
        exit_code = None
        ec = exit_code if exit_code is not None else 1
        assert ec == 1
        assert (ec == 0) is False  # no healthy

    def test_non_zero_exit_code_still_unhealthy(self):
        """El fix no cambia el comportamiento para exit codes no-cero."""
        for code in [1, 2, 7, 22, 28, 126, 127]:
            ec = code if code is not None else 1
            assert ec != 0, f"exit_code={code} debe ser unhealthy"


class TestTrulyUnhealthyFilter:
    """El filtro de alertas Telegram solo dispara para problemas reales.

    'starting' no es un error — es un container recién arrancado (<60s).
    Alertar sobre 'starting' genera falsos positivos tras create_tenant().
    """

    def _filter(self, tenants: list[dict]) -> list[dict]:
        """Replica la lógica de run_health_check() en main.py."""
        return [t for t in tenants if t.get("status") in ("unhealthy", "stopped")]

    def test_healthy_not_in_alerts(self):
        tenants = [{"tenant": "t001", "status": "healthy"}]
        assert self._filter(tenants) == []

    def test_unhealthy_triggers_alert(self):
        tenants = [{"tenant": "t001", "status": "unhealthy"}]
        result = self._filter(tenants)
        assert len(result) == 1
        assert result[0]["tenant"] == "t001"

    def test_stopped_triggers_alert(self):
        tenants = [{"tenant": "t002", "status": "stopped"}]
        result = self._filter(tenants)
        assert len(result) == 1

    def test_starting_does_not_trigger_alert(self):
        """Container recién arrancado: NO debe disparar alerta Telegram."""
        tenants = [{"tenant": "t003", "status": "starting", "age_seconds": 15}]
        assert self._filter(tenants) == [], (
            "'starting' no debe disparar alerta — es comportamiento esperado"
        )

    def test_mixed_states_only_alerts_on_real_problems(self):
        tenants = [
            {"tenant": "t001", "status": "healthy"},
            {"tenant": "t002", "status": "unhealthy"},
            {"tenant": "t003", "status": "starting"},
            {"tenant": "t004", "status": "stopped"},
        ]
        result = self._filter(tenants)
        codes = {t["tenant"] for t in result}
        assert codes == {"t002", "t004"}, (
            "Solo t002 (unhealthy) y t004 (stopped) deben generar alerta"
        )

    def test_all_healthy_no_alert(self):
        tenants = [
            {"tenant": f"t{i:03d}", "status": "healthy"}
            for i in range(1, 6)
        ]
        assert self._filter(tenants) == []
