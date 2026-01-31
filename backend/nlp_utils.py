"""NLP preprocessing (spaCy/NLTK) and ambiguity detection for contract text."""
from typing import List, Tuple
import re

_nlp = None
_nltk_ready = False


def _get_nlp():
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            try:
                import spacy
                spacy.cli.download("en_core_web_sm")
                _nlp = spacy.load("en_core_web_sm")
            except Exception:
                _nlp = False
    return _nlp if _nlp else None


def _ensure_nltk():
    global _nltk_ready
    if _nltk_ready:
        return
    try:
        import nltk
        for name in ("punkt", "punkt_tab", "wordnet", "stopwords"):
            try:
                nltk.download(name, quiet=True)
            except Exception:
                pass
        _nltk_ready = True
    except Exception:
        pass


def preprocess_text(text: str) -> str:
    """Normalize whitespace and basic cleanup. Optionally use spaCy for sentence boundary."""
    if not text or not text.strip():
        return text
    text = re.sub(r"\s+", " ", text).strip()
    return text


def get_sentences(text: str) -> List[str]:
    """Split into sentences using spaCy if available, else NLTK, else simple regex."""
    nlp = _get_nlp()
    if nlp:
        doc = nlp(text[:100000])
        return [s.text.strip() for s in doc.sents if s.text.strip()]
    _ensure_nltk()
    try:
        from nltk.tokenize import sent_tokenize
        return [s.strip() for s in sent_tokenize(text[:100000]) if s.strip()]
    except Exception:
        pass
    # Fallback: split on sentence-ending punctuation
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def detect_ambiguity(text: str) -> List[Tuple[str, str]]:
    """
    Heuristic ambiguity detection: vague terms, multiple interpretations.
    Returns list of (phrase_or_pattern, reason).
    """
    findings: List[Tuple[str, str]] = []
    lower = text.lower()
    # Vague time
    for m in re.finditer(r"\b(reasonable|appropriate|timely|as soon as practicable|forthwith)\s+(time|period|notice|manner)\b", lower, re.IGNORECASE):
        findings.append((m.group(0), "Vague time or standard; 'reasonable' or 'appropriate' may be interpreted differently."))
    for m in re.finditer(r"\b(reasonable|best)\s+efforts?\b", lower, re.IGNORECASE):
        findings.append((m.group(0), "Obligation level unclear; 'reasonable efforts' vs 'best efforts' have different legal weight."))
    # Undefined terms
    for m in re.finditer(r"\b(material|substantial|significant)\s+(breach|default|change|delay)\b", lower, re.IGNORECASE):
        findings.append((m.group(0), "Threshold not defined; 'material' or 'substantial' is subjective without a definition."))
    # Scope unclear
    if "including but not limited to" in lower or "including without limitation" in lower:
        findings.append(("including but not limited to / including without limitation", "Scope may be broader than expected; list is non-exhaustive."))
    if "and/or" in lower:
        findings.append(("and/or", "Ambiguous whether one or both apply; can cause dispute."))
    # Pronoun/ref ambiguity
    if re.search(r"\b(it|this|that|such)\s+(shall|will|may)\b", lower):
        findings.append(("it/this/that + shall/will/may", "Reference may be unclear; which obligation is referred to?"))
    return findings[:15]


def extract_termination_conditions(text: str) -> List[str]:
    """Simple extraction of termination-related phrases for entity layer."""
    found = []
    lower = text.lower()
    patterns = [
        r"terminat(?:e|ion)\s+(?:for\s+cause|without\s+cause|for\s+convenience|upon\s+\d+\s+days?\s+notice)",
        r"(\d+)\s+days?\s+(?:prior\s+)?written\s+notice",
        r"material\s+breach(?:\s+and\s+(?:failure\s+to\s+)?cure)?",
        r"either\s+party\s+may\s+terminate",
    ]
    for p in patterns:
        for m in re.finditer(p, lower, re.IGNORECASE):
            found.append(m.group(0).strip())
    return list(dict.fromkeys(found))[:10]
