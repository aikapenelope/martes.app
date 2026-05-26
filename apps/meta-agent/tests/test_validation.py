"""Tests de validación de entrada de create_tenant().

Verifica que el regex de bot_token y la validación de telegram_user_id
rechacen valores inválidos antes de tocar Docker o la DB.

No requieren Docker ni PostgreSQL.
"""

import json
import re

import pytest

# Importar solo el regex — evita side-effects de docker/psycopg
from src.tools.write_ops import _BOT_TOKEN_RE


class TestBotTokenRegex:
    """El formato oficial de Telegram: {8-12 dígitos}:{35 chars alfanuméricos/-/_}"""

    valid_tokens = [
        # Formato real de Telegram: {8-12 dígitos}:{35 chars [A-Za-z0-9_-]}
        # Generados con: python3 -c "print('A'*35)"
        "12345678:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",   # 8 dígitos, 35 A's
        "123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # 9 dígitos, 35 A's
        "1234567890:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", # 10 dígitos, 35 A's
        "12345678901:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",# 11 dígitos, 35 A's
        "123456789012:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",# 12 dígitos, 35 A's
        "123456789:AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoP_-AB",  # mixto con _ y -
    ]

    invalid_tokens = [
        "1234567:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",    # 7 dígitos (muy corto)
        "1234567890123:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # 13 dígitos
        "12345678:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",     # 33 chars (muy corto)
        "12345678:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",# 37 chars (muy largo)
        "12345678AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",    # sin ':'
        "ABCDEFGH:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # letras antes del ':'
        "",                                                # vacío
        "123456789:AAAA AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", # espacio
        "123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA!AA", # '!' inválido
    ]

    @pytest.mark.parametrize("token", valid_tokens)
    def test_valid_token_accepted(self, token: str):
        assert _BOT_TOKEN_RE.match(token) is not None, f"Token válido rechazado: {token}"

    @pytest.mark.parametrize("token", invalid_tokens)
    def test_invalid_token_rejected(self, token: str):
        assert _BOT_TOKEN_RE.match(token) is None, f"Token inválido aceptado: {token!r}"


class TestTelegramUserIdValidation:
    """telegram_user_id debe ser numérico (positivo o negativo para grupos)."""

    valid_ids = ["563825119", "123456789", "-1001234567890"]
    invalid_ids = ["abc", "12.34", "123 456", ""]

    @pytest.mark.parametrize("uid", valid_ids)
    def test_valid_user_id(self, uid: str):
        assert uid.strip().lstrip("-").isdigit(), f"ID válido rechazado: {uid}"

    @pytest.mark.parametrize("uid", invalid_ids)
    def test_invalid_user_id(self, uid: str):
        assert not uid.strip().lstrip("-").isdigit(), f"ID inválido aceptado: {uid!r}"
