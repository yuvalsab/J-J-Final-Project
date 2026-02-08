import os
import json
import time
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional

from llama_cpp import Llama

_MODEL: Optional[Llama] = None


def _dump_llm_raw(text: str, tag: str) -> None:
    try:
        root = Path(__file__).resolve().parents[1]
        d = root / "logs" / "llm_raw"
        d.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        (d / f"{tag}_{ts}.txt").write_text(text or "", encoding="utf-8")
    except Exception:
        pass


def _get_model() -> Llama:
    global _MODEL
    if _MODEL is not None:
        return _MODEL

    gguf = (os.getenv("LLAMA_GGUF_PATH") or "").strip()
    if not gguf:
        raise RuntimeError("LLAMA_GGUF_PATH is missing. Set it in .env to your .gguf file path.")

    n_ctx = int(os.getenv("LLAMA_N_CTX") or "16384")
    n_threads = int(os.getenv("LLAMA_THREADS") or "11")
    n_gpu_layers = int(os.getenv("LLAMA_GPU_LAYERS") or "0")

    _MODEL = Llama(
        model_path=gguf,
        n_ctx=n_ctx,
        n_threads=n_threads,
        n_gpu_layers=n_gpu_layers,
        logits_all=False,
        embedding=False,
        verbose=False,
    )
    return _MODEL


def _force_json_prompt(prompt: str) -> str:
    guard = (
        "Return ONLY a single valid JSON object. "
        "No markdown. No code fences. No explanations. "
        "If uncertain, still return JSON with low confidence and NEEDS_HUMAN_REVIEW.\n"
    )
    return guard + prompt


def llama3(
    prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 1200,
    top_p: float = 0.95,
    stop: Optional[list[str]] = None,
    retries: int = 2,
    tag: str = "analyze",
) -> str:
    llm = _get_model()
    last_err = None

    p = _force_json_prompt(prompt)

    for attempt in range(retries + 1):
        try:
            out = llm(
                p,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                stop=stop,
                echo=False,
            )
            text = out["choices"][0]["text"] if out and out.get("choices") else ""
            _dump_llm_raw(text, tag)
            return text
        except Exception as e:
            last_err = e
            time.sleep(min(1.5 * (attempt + 1), 5.0))

    raise last_err if last_err else RuntimeError("llama3 failed with unknown error")


async def llama3_async(*args, **kwargs) -> str:
    return await asyncio.to_thread(llama3, *args, **kwargs)
