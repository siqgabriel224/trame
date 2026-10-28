"""Snapshots SQLite verificados, com histórico e estado visível ao administrador."""

import json
import os
import secrets
import sqlite3
import threading
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

_LOCK = threading.Lock()
_STATUS_LOCK = threading.Lock()
_failures = {}
INTERVAL_SECONDS = 15 * 60
SNAPSHOTS_TO_KEEP = 96
DAILY_TO_KEEP = 30


def folder(runtime):
    configured = os.environ.get("TRAME_BACKUP_DIR", "").strip()
    return Path(configured).expanduser() if configured else runtime.DB.parent / "backups-rede"


def status(runtime):
    failure = _failures.get(str(runtime.DB.resolve()))
    if failure:
        return dict(failure)
    try:
        # Evita substituir o status enquanto uma requisição ainda está lendo.
        with _STATUS_LOCK:
            text = (folder(runtime) / "status.json").read_text(encoding="utf-8")
        state = json.loads(text)
        if not isinstance(state, dict):
            raise ValueError("Estado de backup inválido")
        return {key: state.get(key) for key in ("lastSuccess", "lastError", "checkedAt")}
    except (OSError, ValueError, TypeError):
        return {
            "lastSuccess": None,
            "lastError": "Ainda não há um backup confirmado.",
            "checkedAt": None,
        }


def _replace(source, target):
    # Antivírus e sincronizadores podem manter o destino aberto por alguns instantes.
    for attempt in range(5):
        try:
            source.replace(target)
            return
        except PermissionError as exc:
            if getattr(exc, "winerror", None) not in (5, 32, 33) or attempt == 4:
                raise
            time.sleep(0.05 * (attempt + 1))


def _record(root, state):
    temporary = root / ("status-" + secrets.token_hex(8) + ".tmp")
    try:
        temporary.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        with _STATUS_LOCK:
            _replace(temporary, root / "status.json")
    finally:
        temporary.unlink(missing_ok=True)


def _snapshot(runtime, target):
    temporary = target.with_name(target.name + "." + secrets.token_hex(8) + ".tmp")
    try:
        with closing(runtime.connect()) as src, closing(sqlite3.connect(temporary)) as dst:
            src.backup(dst)
            if dst.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise sqlite3.DatabaseError("A cópia do banco não passou na verificação.")
        _replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _managed(root, pattern, date_format):
    files = []
    for item in root.glob(pattern):
        if item.is_symlink() or not item.is_file():
            continue
        try:
            datetime.strptime(item.name, date_format)
        except ValueError:
            continue
        files.append(item)
    return sorted(files, key=lambda item: item.name, reverse=True)


def create(runtime, now=None):
    """Uma falha no backup não desfaz um salvamento já confirmado."""
    now = now or datetime.now(timezone.utc)
    root = folder(runtime)
    with _LOCK:
        previous = status(runtime)
        state = dict(previous, checkedAt=now.isoformat())
        try:
            root.mkdir(parents=True, exist_ok=True)
            daily = root / ("trame-" + now.astimezone().strftime("%Y-%m-%d") + ".sqlite3")
            snapshots = _managed(
                root, "trame-snapshot-*.sqlite3", "trame-snapshot-%Y%m%dT%H%M%S%fZ.sqlite3"
            )
            due = not snapshots or now - datetime.strptime(
                snapshots[0].name, "trame-snapshot-%Y%m%dT%H%M%S%fZ.sqlite3"
            ).replace(tzinfo=timezone.utc) >= timedelta(seconds=INTERVAL_SECONDS)
            created = False
            if not daily.exists():
                _snapshot(runtime, daily)
                created = True
            if due:
                target = root / ("trame-snapshot-" + now.strftime("%Y%m%dT%H%M%S%fZ") + ".sqlite3")
                _snapshot(runtime, target)
                created = True
            if created:
                state.update(lastSuccess=now.isoformat(), lastError=None)
                # Aplica a retenção somente depois de publicar uma cópia verificada.
                for pattern, fmt, keep in (
                    (
                        "trame-snapshot-*.sqlite3",
                        "trame-snapshot-%Y%m%dT%H%M%S%fZ.sqlite3",
                        SNAPSHOTS_TO_KEEP,
                    ),
                    ("trame-????-??-??.sqlite3", "trame-%Y-%m-%d.sqlite3", DAILY_TO_KEEP),
                ):
                    for old in _managed(root, pattern, fmt)[keep:]:
                        old.unlink()
            _record(root, state)
        except (OSError, sqlite3.Error) as exc:
            state["lastError"] = (
                "Falha ao criar ou manter o backup. Confira o destino e o espaço disponível."
            )
            print("Falha no backup:", exc, flush=True)
            try:
                _record(root, state)
            except OSError:
                pass
            # Mantém o erro em memória caso o destino também esteja indisponível.
            _failures[str(runtime.DB.resolve())] = state
            return state
        _failures.pop(str(runtime.DB.resolve()), None)
        return state
