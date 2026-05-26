"""Tests adicionales para backup/restore — gaps de seguridad y constantes.

Cubre:
- Path traversal attacks en _restore_filter()
- _RESTORE_STALE_FILES: archivos que se deben borrar post-restore
- _RESTORE_SECRET_FILES: archivos que deben tener chmod 600 post-restore
- Consistencia entre _BACKUP_EXCLUDE_NAMES y _RESTORE_STALE_FILES
"""

import os
import stat
import tarfile
from pathlib import Path

import pytest

from src.tools.write_ops import (
    _BACKUP_EXCLUDE_NAMES,
    _RESTORE_SECRET_FILES,
    _RESTORE_STALE_FILES,
    _restore_filter,
)


class TestRestoreFilterSecurity:
    """_restore_filter debe bloquear path traversal — no debe extraer fuera de dest_path."""

    def test_path_traversal_blocked(self, tmp_path: Path):
        """Un backup malicioso con '../../etc/crontab' no debe pasar el filtro."""
        ti = tarfile.TarInfo(name="../../etc/crontab")
        result = _restore_filter(ti, str(tmp_path))
        # data_filter debe rechazarlo (None) o reescribir la ruta.
        # En cualquier caso NO debe devolver un TarInfo que apunte fuera de dest.
        if result is not None:
            # Si lo acepta, el nombre debe estar saneado (sin '..'):
            assert ".." not in result.name, (
                f"Path traversal no fue bloqueado: {result.name}"
            )

    def test_absolute_path_blocked(self, tmp_path: Path):
        """Rutas absolutas en el archivo tar deben ser bloqueadas o saneadas."""
        ti = tarfile.TarInfo(name="/etc/crontab")
        result = _restore_filter(ti, str(tmp_path))
        if result is not None:
            assert not result.name.startswith("/"), (
                f"Ruta absoluta no fue bloqueada: {result.name}"
            )

    def test_normal_path_accepted(self, tmp_path: Path):
        """Ruta relativa normal dentro del destino: debe pasar."""
        ti = tarfile.TarInfo(name="tenant/data.json")
        result = _restore_filter(ti, str(tmp_path))
        assert result is not None

    def test_absolute_symlink_returns_none(self, tmp_path: Path):
        """Symlink absoluto (caché de uv) → None, sin FilterError."""
        ti = tarfile.TarInfo(name="tenant/.cache/archive-v0/lib.so")
        ti.type = tarfile.SYMTYPE
        ti.linkname = "/usr/lib/x86_64-linux-gnu/libstdc++.so.6"
        result = _restore_filter(ti, str(tmp_path))
        assert result is None


class TestRestoreConstants:
    """_RESTORE_STALE_FILES y _RESTORE_SECRET_FILES — integridad de las constantes."""

    def test_stale_files_subset_of_exclude_names(self):
        """Los archivos estériles post-restore (pid, lock) deben estar
        también en _BACKUP_EXCLUDE_NAMES para que nunca entren al backup."""
        pid_lock_files = {f for f in _RESTORE_STALE_FILES if f.endswith((".pid", ".lock"))}
        for f in pid_lock_files:
            assert f in _BACKUP_EXCLUDE_NAMES, (
                f"'{f}' está en _RESTORE_STALE_FILES pero no en _BACKUP_EXCLUDE_NAMES. "
                "Si entra en el backup y se restaura, puede causar problemas de inicio."
            )

    def test_secret_files_have_sensitive_names(self):
        """Los archivos en _RESTORE_SECRET_FILES son los que contienen credenciales."""
        sensitive = {".env", "auth.json", "state.db"}
        for f in _RESTORE_SECRET_FILES:
            assert f in sensitive, f"'{f}' no parece ser un archivo sensible esperado."

    def test_secret_files_chmod_600_simulation(self, tmp_path: Path):
        """Simula el proceso de chmod 600 post-restore sobre los archivos sensibles."""
        for fname in _RESTORE_SECRET_FILES:
            path = tmp_path / fname
            path.write_text("secret content")
            path.chmod(0o644)  # arrancar con permisos abiertos
            # Aplicar el mismo patrón que restore_tenant_from_backup():
            path.chmod(0o600)
            mode = stat.S_IMODE(path.stat().st_mode)
            assert mode == 0o600, (
                f"chmod 600 falló en '{fname}': modo actual = {oct(mode)}"
            )

    def test_env_in_secret_files(self):
        """.env DEBE estar en _RESTORE_SECRET_FILES — contiene tokens y API keys."""
        assert ".env" in _RESTORE_SECRET_FILES

    def test_auth_json_in_secret_files(self):
        """auth.json DEBE estar en _RESTORE_SECRET_FILES — contiene OAuth tokens."""
        assert "auth.json" in _RESTORE_SECRET_FILES

    def test_state_db_in_secret_files(self):
        """state.db DEBE estar en _RESTORE_SECRET_FILES — contiene historial de sesiones."""
        assert "state.db" in _RESTORE_SECRET_FILES

    def test_stale_files_not_empty(self):
        """Debe haber al menos gateway.pid y cron.pid en stale files."""
        assert "gateway.pid" in _RESTORE_STALE_FILES
        assert "cron.pid" in _RESTORE_STALE_FILES
