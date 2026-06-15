# -*- coding: utf-8 -*-
"""分节缓存。按 (model, temperature, system, user) 哈希缓存每节响应。"""
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = SKILL_ROOT / ".sectioncache"


def cache_key(model: str, temperature: float, system: str, user: str) -> str:
    h = hashlib.sha256()
    h.update(f"{model}\x00{temperature}\x00".encode("utf-8"))
    h.update(system.encode("utf-8"))
    h.update(b"\x00")
    h.update(user.encode("utf-8"))
    return h.hexdigest()


def cache_get(key: str) -> str | None:
    p = CACHE_DIR / f"{key}.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))["response"]
    except Exception:
        return None


def cache_put(key: str, *, model: str, temperature: float, section: str,
              mode: str, response: str) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (CACHE_DIR / f"{key}.json").write_text(json.dumps({
            "model": model, "temperature": temperature, "section": section,
            "mode": mode, "ts": _dt.datetime.now().isoformat(timespec="seconds"),
            "response": response,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as e:
        print(f"[缓存] 写入失败（忽略）：{e}", file=sys.stderr)
