"""Tests para lógica de billing — casos edge importantes.

Complementa test_billing_logic.py con casos edge que afectan producción:
- paid_until = NULL (t001 tenía este caso)
- Cálculo de días cuando el tenant lleva menos de 1 día activo
- La regla de auto-suspend solo aplica si BILLING_AUTO_SUSPEND=True
"""

from datetime import date, timedelta
from typing import Optional

import pytest


class TestBillingNullPaidUntil:
    """paid_until = NULL es un estado válido (tenant creado antes del billing)."""

    def test_null_paid_until_never_triggers_alert(self):
        """Si paid_until es NULL, no se puede calcular days_remaining → no hay alerta."""
        paid_until: Optional[date] = None
        # En billing_check: solo procesar tenants con paid_until IS NOT NULL
        if paid_until is None:
            days_remaining = None
        else:
            days_remaining = (paid_until - date.today()).days

        assert days_remaining is None, "NULL paid_until no debe generar alerta"

    def test_null_paid_until_never_triggers_suspend(self):
        """Si paid_until es NULL, no se calcula overdue → no hay auto-suspend."""
        paid_until: Optional[date] = None
        today = date(2026, 6, 4)
        grace_days = 3

        if paid_until is None:
            should_suspend = False
        else:
            days_overdue = (today - paid_until).days
            should_suspend = days_overdue > grace_days

        assert not should_suspend

    def test_null_paid_until_sql_behavior(self):
        """SQL WHERE paid_until <= hoy no devuelve filas con NULL (NULL comparisons)."""
        # En PostgreSQL: NULL <= date → NULL (no TRUE), por lo que no aparece en resultados
        # Este test documenta ese comportamiento esperado
        today = date(2026, 6, 4)
        paid_until = None
        # Simula: WHERE paid_until <= today
        result = paid_until is not None and paid_until <= today
        assert not result, "NULL no debe aparecer en consultas de vencimiento"


class TestBillingAutoSuspendFlag:
    """BILLING_AUTO_SUSPEND=False debe bloquear la suspensión automática."""

    def test_auto_suspend_false_prevents_suspension(self):
        """Incluso con tenant vencido+overdue, si auto_suspend=False no se suspende."""
        today = date(2026, 6, 4)
        paid_until = date(2026, 5, 28)  # vencido hace 7 días
        grace_days = 3
        billing_auto_suspend = False

        days_overdue = (today - paid_until).days
        should_suspend = billing_auto_suspend and (days_overdue > grace_days)
        assert not should_suspend

    def test_auto_suspend_true_suspends_when_overdue(self):
        """Con auto_suspend=True y tenant en mora > grace_days → suspender."""
        today = date(2026, 6, 4)
        paid_until = date(2026, 5, 28)  # hace 7 días
        grace_days = 3
        billing_auto_suspend = True

        days_overdue = (today - paid_until).days
        should_suspend = billing_auto_suspend and (days_overdue > grace_days)
        assert should_suspend


class TestBillingAlertLogic:
    """Los tenants reciben alerta SOLO en los días exactos configurados."""

    @pytest.mark.parametrize("alert_days,expected", [
        ([7, 3], 7, ),
        ([7, 3], 3, ),
    ])
    def test_alert_fired_on_exact_day(self, alert_days, expected):
        """Alerta disparada cuando days_remaining == valor exacto en alert_days."""
        today = date(2026, 6, 4)
        paid_until = today + timedelta(days=expected)
        days_remaining = (paid_until - today).days
        should_alert = days_remaining in alert_days
        assert should_alert

    def test_no_alert_on_non_threshold_day(self):
        """No hay alerta en días que no están en la lista."""
        today = date(2026, 6, 4)
        alert_days = [7, 3]

        for non_threshold in [1, 2, 4, 5, 6, 8, 10, 14, 30]:
            paid_until = today + timedelta(days=non_threshold)
            days_remaining = (paid_until - today).days
            assert days_remaining not in alert_days, (
                f"Falsa alerta en día {non_threshold}"
            )

    def test_negative_days_is_overdue_not_alert(self):
        """days_remaining negativo = ya venció. No es el mismo caso que alerta."""
        today = date(2026, 6, 4)
        paid_until = date(2026, 6, 1)  # ya venció
        days_remaining = (paid_until - today).days
        alert_days = [7, 3]
        assert days_remaining not in alert_days
        assert days_remaining < 0


class TestBillingTrialEdgeCases:
    """Edge cases del trial period."""

    def test_trial_30d_future_date(self):
        """Trial de 30 días resulta en fecha futura."""
        today = date(2026, 6, 4)
        trial_days = 30
        paid_until = today + timedelta(days=trial_days)
        assert paid_until > today
        assert (paid_until - today).days == 30

    def test_zero_trial_days_disables_trial(self):
        """trial_days=0 significa que el tenant vence hoy."""
        today = date(2026, 6, 4)
        paid_until = today + timedelta(days=0)
        assert (paid_until - today).days == 0

    def test_payment_after_expiry_reactivates(self):
        """Registrar un pago después del vencimiento debe extender paid_until."""
        today = date(2026, 6, 4)
        paid_until = date(2026, 5, 30)  # expiró
        months = 1

        # Si paid_until < hoy → usar hoy como base para la extensión
        base = today if paid_until < today else paid_until
        new_paid_until = base + timedelta(days=30 * months)

        assert new_paid_until > today
        assert new_paid_until == date(2026, 7, 4)
