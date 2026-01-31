"""Optional LLM client for legal reasoning and Hindi→English normalization. Uses Claude or GPT-4 if API keys are set."""
import os
from typing import Optional


def _call_openai(prompt: str, system: str, max_tokens: int = 1500) -> Optional[str]:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        r = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
        )
        if r.choices and r.choices[0].message.content:
            return r.choices[0].message.content.strip()
    except Exception:
        pass
    return None


def _call_anthropic(prompt: str, system: str, max_tokens: int = 1500) -> Optional[str]:
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        r = client.messages.create(
            model=os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        if r.content and len(r.content) > 0 and hasattr(r.content[0], "text"):
            return r.content[0].text.strip()
    except Exception:
        pass
    return None


def normalize_hindi_to_english(text: str) -> str:
    """If Hindi (or mixed) contract text is provided, attempt translation to English for NLP. Falls back to original if no LLM."""
    if not text or not text.strip():
        return text
    # Prefer Claude, then GPT-4
    if os.environ.get("ANTHROPIC_API_KEY"):
        out = _call_anthropic(
            f"Translate the following contract text to English. Preserve structure (clause numbers, headings). Output only the English translation.\n\n{text[:30000]}",
            "You are a legal translator. Output only the translated English text, no commentary.",
            max_tokens=4000,
        )
        if out:
            return out
    if os.environ.get("OPENAI_API_KEY"):
        out = _call_openai(
            f"Translate the following contract text to English. Preserve structure (clause numbers, headings). Output only the English translation.\n\n{text[:30000]}",
            "You are a legal translator. Output only the translated English text, no commentary.",
            max_tokens=4000,
        )
        if out:
            return out
    return text


def enhance_explanation_with_llm(clause_heading: str, clause_text: str, intent: str, business_role: Optional[str]) -> Optional[str]:
    """Optional: one-sentence plain-language explanation for a clause. Returns None if no LLM or on failure."""
    role = business_role or "SME"
    system = "You are a legal advisor for Indian SMEs. Explain contract clauses in one short, simple business sentence. No legal jargon. No statutes or case names."
    prompt = f"Contract clause heading: {clause_heading}\nClause text (excerpt): {clause_text[:800]}\nDetected intent: {intent}. Audience: {role}. Give one sentence plain-language explanation only."
    if os.environ.get("ANTHROPIC_API_KEY"):
        out = _call_anthropic(prompt, system, max_tokens=150)
        if out:
            return out
    if os.environ.get("OPENAI_API_KEY"):
        out = _call_openai(prompt, system, max_tokens=150)
        if out:
            return out
    return None
