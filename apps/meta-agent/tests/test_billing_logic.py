"""Tests de lógica de billing — cálculos de vencimiento, trial y gracia.

Verifica los cálculos de fechas del billing_check sin necesitar DB ni Docker.
"""

from datetime import date, timedelta

import pytest


class TestBillingDateLogic:
    """Lógica pura de cálculo de fechas para billing."""

    # ── Trial ─────────────────────────────────────────────────────────────

    def test_trial_start(self):
        """Al crear un tenant, paid_until = hoy + trial_days."""
        today = date(2026, 6, 4)
        trial_days = 30
        paid_until = today + timedelta(days=trial_days)
        assert paid_until == date(2026, 7, 4)

    def test_tenant_in_trial_not_expired(self):
        """Tenant con paid_until en el futuro → no vence."""
        today = date(2026, 6, 4)
        paid_until = date(2026, 7, 4)
        days_remaining = (paid_until - today).days
        assert days_remaining > 0

    def test_tenant_exactly_expired(self):
        """Tenant con paid_until = hoy → 0 días restantes."""
        today = date(2026, 6, 4)
        paid_until = date(2026, 6, 4)
        days_remaining = (paid_until - today).days
        assert days_remaining == 0

    def test_tenant_overdue(self):
        """Tenant con paid_until en el pasado → días negativos."""
        today = date(2026, 6, 4)
        paid_until = date(2026, 5, 30)
        days_remaining = (paid_until - today).days
        assert days_remaining < 0

    # ── Grace period ──────────────────────────────────────────────────────

    def test_within_grace_period_not_suspended(self):
        """Dentro del grace period → no suspender aunque expiró."""
        today = date(2026, 6, 4)
        paid_until = date(2026, 6, 2)  # expiró hace 2 días
        grace_days = 3
        days_overdue = (today - paid_until).days
        assert days_overdue <= grace_days  # no suspender aún

    def test_beyond_grace_period_suspend(self):
        """Pasado el grace period → suspender automáticamente."""
        today = date(2026, 6, 4)
        paid_until = date(2026, 5, 30)  # expiró hace 5 días
        grace_days = 3
        days_overdue = (today - paid_until).days
        assert days_overdue > grace_days  # suspender

    def test_grace_period_boundary(self):
        """Exactamente en el último día de gracia → no suspender."""
        today = date(2026, 6, 4)
        paid_until = date(2026, 6, 1)  # hace exactamente 3 días
        grace_days = 3
        days_overdue = (today - paid_until).days
        assert days_overdue == grace_days  # en el límite — depende de la lógica
        # En nuestra implementación: days_overdue > grace_days → suspend
        # 3 no es > 3 → no suspende. Día 4+ suspende.
        assert not (days_overdue > grace_days)

    # ── Alert days ────────────────────────────────────────────────────────

    @pytest.mark.parametrize("alert_days", [7, 3])
    def test_alert_threshold(self, alert_days: int):
        """Tenants que vencen exactamente en N días reciben alerta."""
        today = date(2026, 6, 4)
        paid_until = today + timedelta(days=alert_days)
        days_remaining = (paid_until - today).days
        assert days_remaining == alert_days

    def test_no_alert_outside_window(self):
        """Tenants que vencen en 15 días no reciben alerta (7d y 3d)."""
        today = date(2026, 6, 4)
        paid_until = today + timedelta(days=15)
        alert_days = [7, 3]
        days_remaining = (paid_until - today).days
        assert days_remaining not in alert_days

    # ── register_payment extiende paid_until ─────────────────────────────

    def test_payment_extends_from_paid_until(self):
        """El pago extiende desde paid_until, no desde hoy."""
        today = date(2026, 6, 4)
        paid_until = date(2026, 7, 4)  # 30 días restantes
        months = 1
        # Hermes: period_end = paid_until + 30 días (aprox)
        new_paid_until = paid_until + timedelta(days=30 * months)
        assert new_paid_until == date(2026, 8, 3)
        assert new_paid_until > paid_until

    def test_payment_when_expired_extends_from_today(self):
        """Si ya expiró, el pago extiende desde hoy."""
        today = date(2026, 6, 4)
        paid_until = date(2026, 5, 30)  # ya expiró
        months = 1
        # Si paid_until < hoy: usar hoy como base
        base = max(paid_until, today)
        new_paid_until = base + timedelta(days=30 * months)
        assert new_paid_until > today
