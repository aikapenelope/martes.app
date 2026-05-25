"""Tests para _tar_filter() y _restore_filter() — funciones puras de backup/restore.

Estas funciones son las más críticas en el sistema: si fallan, los backups
incluyen archivos que causan 'torn restore' en Hermes o el restore aborta.

No requieren Docker ni PostgreSQL — son funciones puras sobre TarInfo.
"""

import tarfile
from pathlib import Path

import pytest

# Importar las funciones y constantes directamente (no el módulo completo
# para evitar el import side-effect de docker/psycopg al cargar write_ops)
from src.tools.write_ops import (
    _BACKUP_EXCLUDE_DIRS,
    _BACKUP_EXCLUDE_NAMES,
    _BACKUP_EXCLUDE_SUFFIXES,
    _tar_filter,
    _restore_filter,
)


def make_tarinfo(name: str, size: int = 100) -> tarfile.TarInfo:
    """Helper: crea un TarInfo con el nombre dado."""
    t = tarfile.TarInfo(name=name)
    t.size = size
    return t


class TestTarFilter:
    """_tar_filter: excluye archivos estériles de Hermes antes de crear el backup."""

    def test_normal_file_passes(self):
        """Archivos normales pasan el filtro sin cambios."""
        ti = make_tarinfo("t001/.env")
        assert _tar_filter(ti) is ti

    def test_state_db_passes(self):
        """state.db es de Hermes pero sí debe incluirse en el backup."""
        ti = make_tarinfo("t001/state.db")
        assert _tar_filter(ti) is ti

    def test_gateway_pid_excluded(self):
        """gateway.pid nunca va en el backup — causa torn restore."""
        ti = make_tarinfo("t001/gateway.pid")
        assert _tar_filter(ti) is None

    def test_cron_pid_excluded(self):
        ti = make_tarinfo("t001/cron.pid")
        assert _tar_filter(ti) is None

    def test_db_wal_excluded(self):
        """WAL sidecar de SQLite — junto al .db produce torn restore."""
        ti = make_tarinfo("t001/state.db-wal")
        assert _tar_filter(ti) is None

    def test_db_shm_excluded(self):
        ti = make_tarinfo("t001/state.db-shm")
        assert _tar_filter(ti) is None

    def test_db_journal_excluded(self):
        ti = make_tarinfo("t001/state.db-journal")
        assert _tar_filter(ti) is None

    def test_pyc_excluded(self):
        ti = make_tarinfo("t001/skills/foo/__pycache__/bar.pyc")
        assert _tar_filter(ti) is None

    def test_pycache_dir_excluded(self):
        """Directorio __pycache__ completo excluido."""
        ti = make_tarinfo("t001/skills/__pycache__")
        assert _tar_filter(ti) is None

    def test_checkpoints_dir_excluded(self):
        ti = make_tarinfo("t001/checkpoints/foo.pt")
        assert _tar_filter(ti) is None

    def test_cache_dir_excluded(self):
        ti = make_tarinfo("t001/.cache/pip/wheels/foo.whl")
        assert _tar_filter(ti) is None

    def test_archive_v0_excluded(self):
        """Caché de uv con symlinks absolutos — aborta restore en Python 3.12+."""
        ti = make_tarinfo("t001/.cache/archive-v0/lib/foo.so")
        assert _tar_filter(ti) is None

    def test_soul_md_passes(self):
        ti = make_tarinfo("t001/SOUL.md")
        assert _tar_filter(ti) is ti

    def test_wiki_passes(self):
        ti = make_tarinfo("t001/wiki/catalogo.md")
        assert _tar_filter(ti) is ti

    def test_skills_pass(self):
        ti = make_tarinfo("t001/skills/airtable/SKILL.md")
        assert _tar_filter(ti) is ti

    @pytest.mark.parametrize("name", list(_BACKUP_EXCLUDE_NAMES))
    def test_all_excluded_names(self, name: str):
        """Todos los nombres en _BACKUP_EXCLUDE_NAMES son excluidos."""
        ti = make_tarinfo(f"t001/{name}")
        assert _tar_filter(ti) is None

    @pytest.mark.parametrize("suffix", list(_BACKUP_EXCLUDE_SUFFIXES))
    def test_all_excluded_suffixes(self, suffix: str):
        """Todos los sufijos en _BACKUP_EXCLUDE_SUFFIXES son excluidos."""
        ti = make_tarinfo(f"t001/state.db{suffix}")
        assert _tar_filter(ti) is None

    @pytest.mark.parametrize("dirname", list(_BACKUP_EXCLUDE_DIRS))
    def test_all_excluded_dirs(self, dirname: str):
        """Todos los directorios en _BACKUP_EXCLUDE_DIRS son excluidos."""
        ti = make_tarinfo(f"t001/{dirname}/file.txt")
        assert _tar_filter(ti) is None


class TestRestoreFilter:
    """_restore_filter: omite symlinks absolutos de uv en lugar de abortar el restore."""

    def test_normal_file_passes(self, tmp_path: Path):
        """Archivos normales pasan sin ser None."""
        ti = make_tarinfo("tenant/.env")
        result = _restore_filter(ti, str(tmp_path))
        # data_filter devuelve una copia del TarInfo, no el mismo objeto
        assert result is not None

    def test_directory_passes(self, tmp_path: Path):
        ti = tarfile.TarInfo(name="tenant/wiki")
        ti.type = tarfile.DIRTYPE
        result = _restore_filter(ti, str(tmp_path))
        assert result is not None

    def test_absolute_symlink_omitted(self, tmp_path: Path):
        """Symlinks con target absoluto (uv cache) son omitidos, no abortan."""
        ti = tarfile.TarInfo(name="t001/.cache/archive-v0/lib/foo.so")
        ti.type = tarfile.SYMTYPE
        ti.linkname = "/usr/lib/x86_64-linux-gnu/libfoo.so.2"  # target absoluto
        result = _restore_filter(ti, str(tmp_path))
        # Debe devolver None (omitir) en lugar de lanzar FilterError
        assert result is None

    def test_relative_symlink_passes(self, tmp_path: Path):
        """Symlinks relativos (normales) pasan el filtro."""
        ti = tarfile.TarInfo(name="t001/skills/airtable/current")
        ti.type = tarfile.SYMTYPE
        ti.linkname = "../v2/airtable"  # target relativo — OK
        # Puede pasar o fallar según tarfile.data_filter — lo importante
        # es que no lanza FilterError sin manejo
        try:
            _restore_filter(ti, str(tmp_path))
        except Exception as e:
            pytest.fail(f"_restore_filter lanzó {type(e).__name__}: {e}")
