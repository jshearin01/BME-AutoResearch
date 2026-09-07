"""LLM client with stub fallback so the harness runs with zero API keys.

Providers: stub | anthropic | openai | ollama
All agents call generate() — swap provider via LLM_PROVIDER env.
"""

import httpx
from app.shared.config import settings

SYSTEM_SAFETY = (
    "You are a biomedical engineering research assistant. Research prototype only, "
    "not a medical device. Flag implantable, invasive, sterile, diagnostic, or "
    "dosing claims for human review. Never claim FDA clearance."
)


async def generate(prompt: str, system: str = SYSTEM_SAFETY, max_tokens: int = 1500) -> str:
    provider = settings.LLM_PROVIDER.lower()
    if provider == "anthropic" and settings.ANTHROPIC_API_KEY:
        return await _anthropic(prompt, system, max_tokens)
    if provider == "openai" and settings.OPENAI_API_KEY:
        return await _openai(prompt, system, max_tokens)
    if provider == "ollama":
        return await _ollama(prompt, system)
    return _stub(prompt)


def _stub(prompt: str) -> str:
    # Deterministic offline template so UI + tests work without keys.
    return (
        "[STUB — set LLM_PROVIDER + API key for real output]\n"
        f"Request summary: {prompt[:600]}\n\n"
        "1. Need: restate problem + users + constraints\n"
        "2. Evidence: search PubMed/Semantic Scholar, note 3-5 citations\n"
        "3. Concepts: 3 options scored on safety / printability / cost\n"
        "4. Spec: dimensions, loads, materials, tolerances\n"
        "5. Next gate: what needs human approval before CAD."
    )


async def _anthropic(prompt: str, system: str, max_tokens: int) -> str:
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": settings.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
            json={"model": settings.ANTHROPIC_MODEL, "max_tokens": max_tokens,
                  "system": system, "messages": [{"role": "user", "content": prompt}]},
        )
        r.raise_for_status()
        return r.json()["content"][0]["text"]


async def _openai(prompt: str, system: str, max_tokens: int) -> str:
    base = settings.OPENAI_BASE_URL.rstrip("/")
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
            json={"model": settings.OPENAI_MODEL,
                  "messages": [{"role": "system", "content": system},
                               {"role": "user", "content": prompt}],
                  "max_tokens": max_tokens},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def _ollama(prompt: str, system: str) -> str:
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={"model": settings.OLLAMA_MODEL,
                  "prompt": f"{system}\n\n{prompt}", "stream": False},
        )
        r.raise_for_status()
        return r.json().get("response", "")
