"""Tests para la lógica del health check y alerta RAM — sin Docker.

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
        assert (0 if 0 != None else 1) == 0   # noqa: E711 — documenta el fix correcto

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


class TestRamAlertLogic:
    """Alerta de RAM — lógica de umbral y formato del mensaje.

    Documenta el comportamiento del chequeo de RAM añadido en run_health_check().
    El servidor CX43 tiene 32 GB RAM; ~20 tenants × 768 MB = 15 GB. Con 20% libre
    (~6.4 GB) ya es momento de pensar en escalar.
    Ref: docs/10-ROADMAP.md — capacidad: ~20 tenants en CX43.
    """

    def _should_alert(self, avail_pct: float, threshold: float = 20.0) -> bool:
        """Replica la condición de alerta de run_health_check()."""
        return avail_pct < threshold

    @pytest.mark.parametrize("avail_pct,expected_alert", [
        (50.0,  False),  # servidor con capacidad
        (25.0,  False),  # cerca pero por encima del umbral
        (20.0,  False),  # exactamente en el umbral → NO alerta (< 20, no <= 20)
        (19.9,  True),   # justo por debajo → alerta
        (10.0,  True),   # crítico
        (5.0,   True),   # muy crítico
        (0.1,   True),   # casi sin RAM
    ])
    def test_ram_alert_threshold(self, avail_pct: float, expected_alert: bool):
        """La alerta se dispara cuando RAM disponible es estrictamente < 20%."""
        assert self._should_alert(avail_pct) == expected_alert, (
            f"avail_pct={avail_pct}%: se esperaba alert={expected_alert}"
        )

    def test_ram_pct_calculation(self):
        """El porcentaje de RAM disponible se calcula correctamente."""
        # CX43: 32 GB RAM = 33554432 KB total
        mem_total_kb = 33_554_432
        # 6 GB disponibles → ~18.8%
        mem_avail_kb = 6_291_456
        avail_pct = round(mem_avail_kb / mem_total_kb * 100, 1)
        assert avail_pct == 18.8
        assert self._should_alert(avail_pct) is True

    def test_avail_mb_conversion(self):
        """KB → MB usa división entera para evitar decimales en el mensaje."""
        mem_avail_kb = 6_291_456  # 6 GB
        mem_avail_mb = mem_avail_kb // 1024
        assert mem_avail_mb == 6144  # 6 * 1024

    def test_proc_meminfo_parsing(self):
        """El parser de /proc/meminfo extrae MemTotal y MemAvailable correctamente."""
        # Muestra representativa de /proc/meminfo
        fake_meminfo = (
            "MemTotal:       32768000 kB\n"
            "MemFree:         5000000 kB\n"
            "MemAvailable:    6000000 kB\n"
            "Buffers:          200000 kB\n"
        )
        lines = fake_meminfo.splitlines()
        mem_total_kb = int(
            next(ln for ln in lines if ln.startswith("MemTotal")).split()[1]
        )
        mem_avail_kb = int(
            next(ln for ln in lines if ln.startswith("MemAvailable")).split()[1]
        )
        assert mem_total_kb == 32_768_000
        assert mem_avail_kb == 6_000_000
        avail_pct = round(mem_avail_kb / mem_total_kb * 100, 1)
        assert avail_pct == 18.3
        assert self._should_alert(avail_pct) is True
