# -*- coding: utf-8 -*-
"""LLM 调用（OpenAI-compatible /chat/completions）+ session 复用 + mock。"""
import os
import random
import sys
import threading
import time


def _get_cache():
    """延迟导入 cache 模块（避免循环依赖）。"""
    from . import cache as _cache_mod
    return _cache_mod


_API_SEMAPHORE = threading.Semaphore(10)
_tls = threading.local()


def _get_session():
    import requests as _req
    if not hasattr(_tls, "session"):
        _tls.session = _req.Session()
    return _tls.session


def _mock_response(user: str) -> str:
    want_fig = "tikzpicture" in user
    mock_fig = (
        "\n\\begin{center}\n"
        "\\begin{tikzpicture}[scale=1.0]\n"
        "  \\draw[->] (-0.3,0) -- (3.2,0) node[right] {$x$};\n"
        "  \\draw[->] (0,-0.3) -- (0,2.6) node[above] {$y$};\n"
        "  \\draw[domain=0:3,smooth,thick,blue] plot (\\x,{0.5*\\x*\\x*0.6});\n"
        "  \\node[blue] at (2.6,2.2) {$y=f(x)$};\n"
        "\\end{tikzpicture}\n"
        "\\end{center}\n"
    ) if want_fig else ""
    if "[PROBLEM]" in user or "出" in user:
        return (
            "===ITEM===\n[PROBLEM]\n"
            "设总体 $X\\sim N(\\mu,\\sigma^2)$，$X_1,\\dots,X_n$ 为来自 $X$ 的样本，"
            "求 $\\mu$ 的矩估计量。\n"
            "[SOLUTION]\n"
            "由一阶原点矩 $E(X)=\\mu$，用样本一阶矩 $\\bar X$ 替代总体矩，得\n"
            "\\boxedans{\\hat\\mu=\\bar X}\n"
            "===ITEM===\n[PROBLEM]\n"
            "设 $X_1,\\dots,X_n$ 独立同分布于 $U(0,\\theta)$，求 $\\theta$ 的矩估计量。\n"
            "[SOLUTION]\n"
            f"{mock_fig}"
            "$E(X)=\\theta/2$，令 $\\bar X=\\theta/2$，解得\n"
            "\\boxedans{\\hat\\theta=2\\bar X}\n"
        )
    return (
        "矩估计法（method of moments）的核心思想是用样本矩替代总体矩。"
        "设总体 $k$ 阶原点矩 $E(X^k)=\\alpha_k(\\theta)$，样本 $k$ 阶原点矩 $A_k=\\frac1n\\sum_i X_i^k$，"
        "令 $\\alpha_k(\\theta)=A_k$ 并求解即得矩估计量。该法计算简便，但一般不唯一且未必有最优性质。"
        + mock_fig
    )


def call_llm(system: str, user: str, *, api_key: str, base_url: str,
             model: str, temperature: float, mock: bool) -> str:
    """调用任意 OpenAI-compatible 的 /chat/completions 接口。"""
    if mock:
        return _mock_response(user)
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "stream": False,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    last_err = None
    with _API_SEMAPHORE:
        for attempt in range(3):
            try:
                r = _get_session().post(url, json=payload, headers=headers,
                                        timeout=int(os.environ.get("COURSEWARE_HTTP_TIMEOUT", "600")))
                if 400 <= r.status_code < 500 and r.status_code != 429:
                    raise RuntimeError(
                        f"[错误] 模型 API 拒绝请求（HTTP {r.status_code}，不重试）：{r.text[:200]}"
                    )
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
            except RuntimeError:
                raise
            except Exception as e:
                last_err = e
            wait = min(2 ** attempt + random.uniform(0, 1), 60)
            time.sleep(wait)
    raise RuntimeError(f"[错误] 模型 API 调用失败（已重试 3 次）：{last_err}")


def section_call(system: str, user: str, *, args, api_key: str,
                 section: str, mode: str, tag: str = "") -> str:
    """整节生成调用，按需走缓存。"""
    use_cache = bool(getattr(args, "cache", False)) and not getattr(args, "mock", False)
    key = None
    if use_cache:
        cache_mod = _get_cache()
        key = cache_mod.cache_key(args.model, args.temperature, system, user)
        if not getattr(args, "refresh_cache", False):
            cached = cache_mod.cache_get(key)
            if cached is not None:
                print(f"{tag}[缓存] 命中「{section}」（{mode}），跳过 API 调用。", file=sys.stderr)
                return cached
    raw = call_llm(system, user, api_key=api_key, base_url=args.base_url,
                   model=args.model, temperature=args.temperature, mock=args.mock)
    if use_cache and key:
        cache_mod = _get_cache()
        cache_mod.cache_put(key, model=args.model, temperature=args.temperature,
                            section=section, mode=mode, response=raw)
    return raw
