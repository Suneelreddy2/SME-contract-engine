from typing import List, Dict, Any, Optional, Tuple
import re
from datetime import datetime

try:
    from .llm_client import normalize_hindi_to_english
except ImportError:
    def normalize_hindi_to_english(t: str) -> str:
        return t

try:
    from .nlp_utils import detect_ambiguity, extract_termination_conditions
except ImportError:
    def detect_ambiguity(_: str) -> List[Tuple[str, str]]:
        return []

    def extract_termination_conditions(_: str) -> List[str]:
        return []

try:
    from .clause_templates import clause_similarity_to_templates
except ImportError:
    def clause_similarity_to_templates(_h: str, _b: str) -> List[Dict[str, Any]]:
        return []


def normalize_language(text: str, language: Optional[str]) -> str:
    """Normalize language: if Hindi, attempt translation to English for NLP; else return as-is."""
    if not text or not text.strip():
        return text
    if (language or "").strip().lower() == "hindi":
        return normalize_hindi_to_english(text)
    return text


def detect_contract_type(text: str) -> Tuple[str, str]:
    """Heuristic India-focused contract type classification with explanation."""
    lower = text.lower()
    if any(k in lower for k in ["non-disclosure", "confidentiality agreement", "nondisclosure", "nda"]):
        return "NDA / Confidentiality Agreement", "Mentions non-disclosure / confidentiality obligations typical of NDAs."
    if any(k in lower for k in ["employment", "employee", "employer", "salary", "ctc"]):
        return "Employment Agreement", "Contains terms about employment, employer-employee relationship or salary."
    if any(k in lower for k in ["lease", "rental", "rent", "licence to use premises"]):
        return "Lease / Rental Agreement", "Refers to lease or rental of premises/property."
    if any(k in lower for k in ["partner", "partnership deed", "profit sharing"]):
        return "Partnership Deed", "Talks about partners and profit sharing like a partnership."
    if any(k in lower for k in ["supplier", "purchase order", "supply of goods", "buyer", "vendor"]):
        return "Vendor / Supplier Contract", "Talks about supply of goods, vendors or purchase orders."
    if any(k in lower for k in ["services", "service provider", "consultant", "consultancy", "agency"]):
        return "Service Agreement", "Describes one party providing services to another."
    return "Mixed / Hybrid Contract", "No single dominant type detected; appears to mix multiple elements."


def split_into_clauses(text: str) -> List[Dict[str, Any]]:
    """
    Structural parser: detects headings (numbers, roman numerals, all-caps).
    Groups sub-numbered items (e.g. 1.1, 1.2) under their parent clause as sub_clauses.
    """
    lines = [l.rstrip() for l in text.splitlines()]
    top_level = re.compile(
        r"^(\d+)[\)\.]?\s+|^(i+|v+|x+)[\)\.]?\s+|^[A-Z][A-Z0-9\s\-,]{4,}$"
    )
    sub_level = re.compile(r"^(\d+\.\d+(?:\.\d+)*)[\)\.]?\s+")

    clauses: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    current_subs: List[Dict[str, str]] = []

    def flush_current():
        nonlocal current, current_subs
        if current:
            current["sub_clauses"] = current_subs
            clauses.append(current)
        current = None
        current_subs = []

    for line in lines:
        if not line.strip():
            continue
        stripped = line.strip()
        sub_m = sub_level.match(stripped)
        top_m = top_level.match(stripped)
        if sub_m and current is not None:
            current_subs.append({"heading": stripped, "body": ""})
            continue
        if top_m:
            flush_current()
            current = {"heading": stripped, "body": ""}
            current_subs = []
        else:
            if current is None:
                current = {"heading": "Preamble", "body": stripped}
                current_subs = []
            elif current_subs:
                current_subs[-1]["body"] += ("\n" if current_subs[-1]["body"] else "") + stripped
            else:
                current["body"] += ("\n" if current["body"] else "") + stripped

    flush_current()

    for idx, c in enumerate(clauses, start=1):
        c["clause_number"] = idx
        if "sub_clauses" not in c:
            c["sub_clauses"] = []

    return clauses


def extract_entities(text: str) -> Dict[str, Any]:
    """Extract parties, dates, amounts, jurisdiction and some key attributes with regex heuristics."""
    parties: List[str] = []

    # Very rough party name detection based on common patterns
    party_patterns = [
        r"between\s+(.*?)(?:,|\sand\s|\n)",
        r"by and between\s+(.*?)(?:,|\sand\s|\n)",
        r"party\s+of\s+the\s+first\s+part\s+(.*?)(?:,|\n)",
    ]
    for pat in party_patterns:
        for m in re.finditer(pat, text, flags=re.IGNORECASE | re.DOTALL):
            name = m.group(1).strip()
            if name and name not in parties and len(name) < 200:
                parties.append(name)

    # Amounts like INR 1,00,000 or Rs. 50000
    amounts = re.findall(
        r"(?:INR|Rs\.?|Rupees)\s*[\.:]?\s*[0-9,]+(?:\.[0-9]{1,2})?",
        text,
        flags=re.IGNORECASE,
    )

    # Simple date patterns
    date_patterns = [
        r"\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b",
        r"\b\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b",
    ]
    dates: List[str] = []
    for pat in date_patterns:
        dates += re.findall(pat, text, flags=re.IGNORECASE)

    # Jurisdiction / governing law
    jurisdiction = None
    gov_law_match = re.search(
        r"laws of\s+([A-Za-z\s]+)", text, flags=re.IGNORECASE
    )
    if gov_law_match:
        jurisdiction = gov_law_match.group(1).strip()

    # Duration
    duration_match = re.search(
        r"term\s+of\s+this\s+agreement\s+shall\s+be\s+([A-Za-z0-9\s]+?)(?:\.|\n)",
        text,
        flags=re.IGNORECASE,
    )
    duration = duration_match.group(1).strip() if duration_match else None

    # Confidentiality / IP references
    confidentiality_present = bool(
        re.search(r"confidential", text, flags=re.IGNORECASE)
    )
    ip_present = bool(
        re.search(r"intellectual property|ip rights|copyright|trademark|patent",
                  text, flags=re.IGNORECASE)
    )
    termination_conditions = extract_termination_conditions(text)

    return {
        "parties": parties,
        "dates_and_duration": {
            "dates_raw": dates,
            "duration_text": duration,
        },
        "financials": {
            "amounts_mentions": amounts,
        },
        "jurisdiction_or_governing_law": jurisdiction,
        "termination_conditions": termination_conditions,
        "flags": {
            "confidentiality_clause_present": confidentiality_present,
            "ip_clause_present": ip_present,
        },
    }


def classify_clause_intent(text: str) -> str:
    lower = text.lower()
    if any(k in lower for k in ["shall not", "must not", "prohibited", "no party shall"]):
        return "PROHIBITION"
    if any(k in lower for k in ["shall", "must", "agrees to", "undertakes to"]):
        return "OBLIGATION"
    if any(k in lower for k in ["may", "entitled to", "reserves the right"]):
        return "RIGHT"
    if any(k in lower for k in ["subject to", "provided that", "if ", "in the event that"]):
        return "CONDITIONAL"
    return "INFORMATIONAL"


def business_impact(intent: str, text: str) -> str:
    if intent == "OBLIGATION":
        return "Specifies something a party is required to do; missing this may lead to breach."
    if intent == "RIGHT":
        return "Gives a party a choice or benefit they can exercise."
    if intent == "PROHIBITION":
        return "Restricts or stops a party from doing something; breach can trigger penalties or termination."
    if intent == "CONDITIONAL":
        return "Describes what happens only if certain conditions or events occur."
    return "Explains background, definitions, or general information without direct action."


def clause_risk_level(text: str, intent: str) -> Tuple[str, List[str]]:
    """
    Assign LOW / MEDIUM / HIGH risk and collect machine-readable flags
    based on simple keyword rules tailored for Indian SME concerns.
    """
    lower = text.lower()
    flags: List[str] = []
    risk = "LOW"

    # Termination / lock-in
    if "lock-in" in lower or "lock in" in lower or "non-cancellable" in lower:
        risk = "HIGH"
        flags.append("lock_in_or_non_cancellable")

    if "auto-renew" in lower or "automatically renew" in lower:
        risk = max(risk, "MEDIUM", key=["LOW", "MEDIUM", "HIGH"].index)
        flags.append("auto_renewal")

    # Indemnity
    if "indemnify" in lower or "indemnity" in lower:
        flags.append("indemnity")
        if "unlimited" in lower or "all claims" in lower:
            risk = "HIGH"
        else:
            risk = max(risk, "MEDIUM", key=["LOW", "MEDIUM", "HIGH"].index)

    # Limitation of liability
    if "unlimited liability" in lower or "without any limitation" in lower:
        flags.append("unlimited_liability")
        risk = "HIGH"
    if "limitation of liability" in lower or "liability shall be limited" in lower:
        flags.append("limitation_of_liability")

    # IP transfer / broad license
    if "assign all intellectual property" in lower or "hereby assigns" in lower and "intellectual property" in lower:
        flags.append("ip_assignment")
        risk = max(risk, "MEDIUM", key=["LOW", "MEDIUM", "HIGH"].index)

    # Non-compete / exclusivity
    if "non-compete" in lower or "non compete" in lower or "exclusive" in lower and "territory" in lower:
        flags.append("non_compete_or_exclusivity")
        risk = max(risk, "MEDIUM", key=["LOW", "MEDIUM", "HIGH"].index)

    # Payment / penalties
    if "penalty" in lower or "liquidated damages" in lower or "fine" in lower:
        flags.append("penalties_or_liquidated_damages")
        risk = max(risk, "MEDIUM", key=["LOW", "MEDIUM", "HIGH"].index)

    if "interest" in lower and "late payment" in lower:
        flags.append("late_payment_interest")

    # One-sided termination
    if "may terminate" in lower and "other party may not" not in lower:
        flags.append("unilateral_termination")
        risk = max(risk, "MEDIUM", key=["LOW", "MEDIUM", "HIGH"].index)

    # Confidentiality / data
    if "confidential" in lower or "non-disclosure" in lower:
        flags.append("confidentiality")

    # Arbitration & jurisdiction
    if "arbitration" in lower or "arbitral" in lower or "arbitrator" in lower:
        flags.append("arbitration_and_jurisdiction")
        risk = max(risk, "MEDIUM", key=["LOW", "MEDIUM", "HIGH"].index)

    # Heuristic bump: prohibitions and indemnities get at least MEDIUM
    if intent in ["PROHIBITION"] and risk == "LOW":
        risk = "MEDIUM"

    return risk, flags


def renegotiation_suggestion_for_clause(flags: List[str], text: str) -> Optional[str]:
    """Return a concrete, SME-friendly renegotiation suggestion based on detected flags."""
    if not flags:
        return None

    suggestions = []

    if "lock_in_or_non_cancellable" in flags:
        suggestions.append(
            "Replace strict lock-in with the ability for either party to terminate for convenience "
            "with 30 days' notice and payment only for work actually done."
        )
    if "auto_renewal" in flags:
        suggestions.append(
            "Change auto-renewal to renewal only with written confirmation, or allow either party to opt out "
            "by giving prior written notice (for example, 30 days before renewal)."
        )
    if "indemnity" in flags:
        suggestions.append(
            "Limit indemnity to direct third-party claims caused by proven breach or gross negligence, and cap the "
            "indemnity amount to a reasonable multiple of the total fees paid."
        )
    if "unlimited_liability" in flags:
        suggestions.append(
            "Cap total liability to 6–12 months of fees paid under the agreement, except for confidentiality breach "
            "and willful misconduct."
        )
    if "ip_assignment" in flags:
        suggestions.append(
            "Clarify that only project-specific deliverables are assigned and the service provider keeps all tools, "
            "templates and background IP, while giving the client a license to use them as embedded in the deliverables."
        )
    if "non_compete_or_exclusivity" in flags:
        suggestions.append(
            "Narrow any non-compete or exclusivity to specific customers, products or territory, and limit the duration "
            "to a reasonable period (for example, 6–12 months)."
        )
    if "penalties_or_liquidated_damages" in flags:
        suggestions.append(
            "Replace strict penalties with reasonable, pre-agreed service credits or a capped amount, and ensure any "
            "liquidated damages reflect a genuine pre-estimate of loss."
        )
    if "unilateral_termination" in flags:
        suggestions.append(
            "Allow both parties to terminate for material breach (with a cure period) and for convenience with notice, "
            "rather than only one side having this right."
        )
    if "arbitration_and_jurisdiction" in flags:
        suggestions.append(
            "Ensure arbitration seat and governing law are in India (e.g. Indian Arbitration Act) and venue is "
            "practical for both parties; consider mutual consent for arbitrator appointment."
        )

    return " ".join(suggestions) if suggestions else None


def contract_level_risk_score(clause_risks: List[str]) -> int:
    """
    Simple composite score:
    LOW = 1, MEDIUM = 3, HIGH = 6, averaged and scaled to 0–100.
    """
    if not clause_risks:
        return 0
    weights = {"LOW": 1, "MEDIUM": 3, "HIGH": 6}
    total = sum(weights.get(r, 1) for r in clause_risks)
    avg = total / len(clause_risks)
    score = int(min(100, max(0, (avg / 6.0) * 100)))
    return score


def analyze_contract(
    contract_text: str,
    language: Optional[str] = None,
    business_role: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Main orchestration entrypoint implementing the 11-step workflow and
    returning the output in the exact sections requested.
    """
    normalized = normalize_language(contract_text, language)

    # STEP 1: Contract Type Classification
    contract_type, type_explanation = detect_contract_type(normalized)

    # STEP 2: Structural Parsing
    clauses = split_into_clauses(normalized)
    structured_json = {
        "clauses": [
            {
                "clause_number": c["clause_number"],
                "heading": c["heading"],
                "body": c["body"],
                "sub_clauses": c.get("sub_clauses", []),
            }
            for c in clauses
        ]
    }

    # STEP 3: Entity & Attribute Extraction
    entities = extract_entities(normalized)

    # Ambiguity detection (contract-level)
    ambiguity_findings = detect_ambiguity(normalized)

    # STEP 4 & 5: Clause Intent and Risk
    clause_explanations: List[Dict[str, Any]] = []
    risk_flags: List[Dict[str, Any]] = []
    clause_risk_levels: List[str] = []

    for c in clauses:
        full_text = (c["heading"] + "\n" + c["body"]).strip()
        intent = classify_clause_intent(full_text)
        impact = business_impact(intent, full_text)
        risk_level, flags = clause_risk_level(full_text, intent)
        clause_risk_levels.append(risk_level)

        template_matches = clause_similarity_to_templates(c["heading"], c["body"])
        clause_explanations.append(
            {
                "clause_number": c["clause_number"],
                "heading": c["heading"],
                "intent": intent,
                "business_impact": impact,
                "text_preview": full_text[:500],
                "template_matches": template_matches,
            }
        )

        risk_flags.append(
            {
                "clause_number": c["clause_number"],
                "heading": c["heading"],
                "risk_level": risk_level,
                "flags": flags,
                "justification": "Heuristic India-SME oriented scoring based on presence of lock-in, indemnity, "
                                 "liability, IP, non-compete, penalties and unilateral rights.",
            }
        )

    # STEP 6 & 7: Compliance, Fairness, Renegotiation
    renegotiations: List[Dict[str, Any]] = []
    fairness_flags: List[Dict[str, Any]] = []

    for rf in risk_flags:
        clause_flags = rf["flags"]
        risk_level = rf["risk_level"]
        if risk_level in ["MEDIUM", "HIGH"]:
            suggestion = renegotiation_suggestion_for_clause(clause_flags, "")
            if suggestion:
                renegotiations.append(
                    {
                        "clause_number": rf["clause_number"],
                        "heading": rf["heading"],
                        "risk_level": risk_level,
                        "suggested_change": suggestion,
                        "why_it_helps": "Reduces one-sided exposure and aligns with commonly negotiated positions for "
                                        "Indian SMEs.",
                    }
                )

        if clause_flags:
            fairness_flags.append(
                {
                    "clause_number": rf["clause_number"],
                    "heading": rf["heading"],
                    "one_sided_or_risky_for_sme": True,
                    "flags": clause_flags,
                }
            )

    # STEP 8: Contract-Level Risk Assessment
    composite_score = contract_level_risk_score(clause_risk_levels)
    if composite_score <= 30:
        risk_interpretation = "Safe"
    elif composite_score <= 60:
        risk_interpretation = "Needs review"
    else:
        risk_interpretation = "High risk"

    clause_risk_table = [
        {
            "clause_number": rf["clause_number"],
            "heading": rf["heading"],
            "risk_level": rf["risk_level"],
            "flags": rf["flags"],
        }
        for rf in risk_flags
    ]

    # STEP 9: Plain-Language Business Summary
    biggest_risk_clauses = sorted(
        [rf for rf in risk_flags if rf["risk_level"] == "HIGH"],
        key=lambda x: x["clause_number"],
    )
    summary_biggest_risks = [
        f"Clause {rf['clause_number']} ('{rf['heading']}') has high risk indicators: {', '.join(rf['flags']) or 'general exposure'}."
        for rf in biggest_risk_clauses
    ]

    key_obligations = [
        f"Clause {c['clause_number']} ('{c['heading']}') defines obligations or important actions."
        for c in clause_explanations
        if c["intent"] in ["OBLIGATION", "PROHIBITION"]
    ][:10]

    executive_summary = {
        "overview": (
            f"This appears to be a {contract_type} drafted in an Indian business context. "
            f"The analysis focuses on commercial balance, lock-ins, indemnity, IP, termination, "
            f"and other points that matter to SMEs, without using any specific legal statutes."
        ),
        "key_obligations_to_note": key_obligations,
        "biggest_risks_in_simple_terms": summary_biggest_risks,
        "what_to_negotiate_before_signing": [
            r["suggested_change"] for r in renegotiations
        ][:10],
    }

    # STEP 10: SME Template & Best Practices (generic guidance)
    best_practices = {
        "recommendations": [
            "Ensure mutual termination rights with reasonable notice (for example, 30 days) instead of strict lock-ins.",
            "Cap total liability to a multiple of the annual contract value, with limited exceptions.",
            "Avoid very broad IP assignments; prefer assignment of project-specific deliverables and retention of tools and background IP.",
            "Tighten any non-compete or exclusivity clauses to specific customers, products, or territories and limit duration.",
            "Replace heavy penalties with realistic service credits or capped liquidated damages.",
            "Clearly document payment terms, late payment interest, and milestone acceptance in simple language.",
        ],
        "clauses_to_add_or_strengthen": [
            "Mutual limitation of liability with a clear cap.",
            "Mutual confidentiality obligations with reasonable exclusions.",
            "Mutual termination for convenience and for material breach with cure period.",
            "Dispute resolution clause with Indian governing law and a practical city jurisdiction.",
        ],
    }

    # STEP 11: Audit Log
    timestamp = datetime.utcnow().isoformat() + "Z"
    audit_log = {
        "timestamp_utc": timestamp,
        "actions": [
            "received_input",
            "normalized_language",
            "classified_contract_type",
            "parsed_structure",
            "extracted_entities",
            "ambiguity_detection",
            "clause_template_matching",
            "classified_clause_intents",
            "assigned_clause_risks",
            "generated_renegotiation_suggestions",
            "computed_contract_level_risk_score",
            "generated_executive_summary",
            "compiled_best_practices",
        ],
        "risk_flags_summary": fairness_flags,
        "meta": {
            "jurisdiction_scope": "India (generic contractual practice, no statutes)",
            "business_role_input": business_role,
        },
    }

    # Assemble final response in the requested 10-part format
    result: Dict[str, Any] = {
        "1_contract_type_and_overview": {
            "contract_type": contract_type,
            "explanation": type_explanation,
        },
        "2_structured_clause_extraction_json": structured_json,
        "3_entity_and_attribute_extraction": entities,
        "4_clause_by_clause_explanation_table": clause_explanations,
        "5_risk_analysis_and_flags": {
            "clause_risk_table": clause_risk_table,
            "fairness_and_sme_flags": fairness_flags,
            "ambiguity_flags": [{"phrase": p, "reason": r} for p, r in ambiguity_findings],
        },
        "6_renegotiation_suggestions": renegotiations,
        "7_contract_risk_score_summary": {
            "composite_risk_score_0_to_100": composite_score,
            "interpretation": risk_interpretation,
        },
        "8_executive_business_summary": executive_summary,
        "9_sme_template_and_best_practices": best_practices,
        "10_audit_log": audit_log,
    }

    return result

