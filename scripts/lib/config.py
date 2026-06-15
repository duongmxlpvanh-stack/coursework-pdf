# -*- coding: utf-8 -*-
"""环境变量 + API 供应商解析。零内部依赖，标准库 os + pathlib。"""
import os
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4-pro"

_API_KEY_NAMES = ("API_KEY", "LLM_API_KEY", "OPENAI_API_KEY", "KIMI_API_KEY", "MOONSHOT_API_KEY", "DEEPSEEK_API_KEY")
_BASE_URL_NAMES = ("BASE_URL", "LLM_BASE_URL", "OPENAI_BASE_URL")
_MODEL_NAMES = ("MODEL", "LLM_MODEL", "OPENAI_MODEL")
_TEMPERATURE_NAMES = ("TEMPERATURE", "LLM_TEMPERATURE")

_FORCED_TEMPERATURE: dict[str, float] = {
    "kimi-k2": 1.0,
}


def _first_env(env: dict, names: tuple[str, ...]) -> str:
    """按优先级在 .env 与进程环境变量中取第一个非空值。"""
    for n in names:
        v = env.get(n) or os.environ.get(n)
        if v:
            return v
    return ""


def load_env_file(explicit: str | None) -> dict:
    """按 显式路径 -> ./.env -> skill 根/.env 顺序查找并解析 .env。"""
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    candidates.append(Path.cwd() / ".env")
    candidates.append(SKILL_ROOT / ".env")
    for p in candidates:
        if p.is_file():
            data = {}
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip().strip('"').strip("'")
            return data
    return {}


def resolve_provider(args) -> str:
    """解析 LLM 供应商配置：api_key + base_url + model + temperature。

    优先级（高 -> 低）：
      - base_url / model：显式 CLI/JSON > .env > 内置默认（OpenRouter）。
      - api_key：.env/环境变量中 API_KEY > LLM_API_KEY > OPENAI_API_KEY > ...。
      - temperature：显式 > .env > 模型强制值 > 保持原值。
    解析后就地写回 args.base_url / args.model / args.temperature，返回 api_key。
    """
    if getattr(args, "base_url", None) is None:
        args.base_url = ""
    if getattr(args, "model", None) is None:
        args.model = ""
    if args.mock:
        args.base_url = args.base_url or DEFAULT_BASE_URL
        args.model = args.model or DEFAULT_MODEL
        return ""
    env = load_env_file(args.env)
    args.base_url = args.base_url or _first_env(env, _BASE_URL_NAMES) or DEFAULT_BASE_URL
    args.model = args.model or _first_env(env, _MODEL_NAMES) or DEFAULT_MODEL
    api_key = _first_env(env, _API_KEY_NAMES)
    if not api_key:
        raise RuntimeError(
            "[错误] 未找到 API key。请在 .env 中设置 API_KEY=sk-or-xxx（或 "
            "LLM_API_KEY / OPENAI_API_KEY 之一）。\n"
            "      可选：BASE_URL=... 与 MODEL=... 切换到任意 OpenAI-compatible 供应商"
            "（查找顺序：--env 指定 / ./.env / skill 根目录 /.env）。"
        )
    # temperature 解析
    if getattr(args, "temperature", 0.6) == 0.6:
        env_temp = _first_env(env, _TEMPERATURE_NAMES)
        if env_temp:
            try:
                args.temperature = float(env_temp)
            except ValueError:
                print(f"[警告] .env 中 TEMPERATURE='{env_temp}' 无法解析为浮点数，已忽略。", file=sys.stderr)
    # 模型强制 temperature
    model_lower = args.model.lower()
    for prefix, forced_val in _FORCED_TEMPERATURE.items():
        if prefix in model_lower and getattr(args, "temperature", None) != forced_val:
            print(
                f"[提示] 模型 {args.model!r} 只接受 temperature={forced_val}，已自动覆盖（原值 {args.temperature}）。",
                file=sys.stderr,
            )
            args.temperature = forced_val
            break
    return api_key
