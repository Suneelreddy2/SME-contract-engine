"""Standard SME-friendly clause templates for similarity matching (no external APIs)."""
from typing import List, Dict, Any
import re

# Standard SME-friendly clause descriptions (short) for matching
STANDARD_CLAUSE_TEMPLATES: List[Dict[str, Any]] = [
    {"id": "term_notice", "heading": "Term and termination with notice", "keywords": "term, terminate, notice, days, renewal"},
    {"id": "limitation_liability", "heading": "Limitation of liability", "keywords": "liability, limited, cap, exclude, indirect"},
    {"id": "confidentiality", "heading": "Confidentiality", "keywords": "confidential, disclose, non-disclosure, information"},
    {"id": "ip_rights", "heading": "Intellectual property", "keywords": "intellectual property, assign, license, copyright"},
    {"id": "indemnity", "heading": "Indemnity", "keywords": "indemnify, indemnity, hold harmless, claims"},
    {"id": "payment", "heading": "Payment terms", "keywords": "payment, fee, invoice, due, days"},
    {"id": "governing_law", "heading": "Governing law and jurisdiction", "keywords": "governing law, jurisdiction, courts, dispute"},
    {"id": "arbitration", "heading": "Arbitration", "keywords": "arbitration, arbitrator, arbitral"},
    {"id": "scope_services", "heading": "Scope of services / deliverables", "keywords": "scope, services, deliverables, perform"},
    {"id": "warranty", "heading": "Warranty", "keywords": "warranty, represent, warrant"},
]


def _normalize_for_similarity(s: str) -> str:
    s = re.sub(r"[^\w\s]", " ", (s or "").lower())
    return " ".join(s.split())


def clause_similarity_to_templates(clause_heading: str, clause_body: str) -> List[Dict[str, Any]]:
    """
    Match clause to standard templates by keyword overlap (no embeddings).
    Returns list of {template_id, template_heading, match_score_0_1, matched_keywords}.
    """
    combined = _normalize_for_similarity(clause_heading + " " + clause_body)
    if not combined:
        return []
    results = []
    for t in STANDARD_CLAUSE_TEMPLATES:
        keywords = _normalize_for_similarity(t["keywords"]).split()
        matched = [k for k in keywords if k in combined]
        if not matched:
            continue
        score = len(matched) / max(len(keywords), 1)
        if score >= 0.2:
            results.append({
                "template_id": t["id"],
                "template_heading": t["heading"],
                "match_score": round(min(1.0, score), 2),
                "matched_keywords": matched[:5],
            })
    results.sort(key=lambda x: -x["match_score"])
    return results[:5]
