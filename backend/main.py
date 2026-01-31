from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Any, Dict
import os
import json

# Load .env from project root (parent of backend/) so OPENAI_API_KEY / ANTHROPIC_API_KEY are set
try:
    from dotenv import load_dotenv
    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    load_dotenv(os.path.join(_root, ".env"))
except ImportError:
    pass

from .analysis import analyze_contract
from .extractors import extract_text_from_file
from .pdf_export import build_analysis_pdf

# Audit log persistence (JSONL: one JSON object per line)
_AUDIT_LOG_PATH = os.path.join(os.path.dirname(__file__), "audit_logs.jsonl")


def _persist_audit_log(audit_entry: Dict[str, Any]) -> None:
    """Append audit entry to local JSONL file."""
    try:
        with open(_AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


class AnalyzeRequest(BaseModel):
    contract_text: str
    language: Optional[str] = "english"
    business_role: Optional[str] = None


class AnalyzeResponse(BaseModel):
    result: Dict[str, Any]


app = FastAPI(
    title="India SME Contract Intelligence Engine",
    description=(
        "GenAI-powered legal assistant for Indian SMEs. "
        "Analyzes contracts, identifies risks, suggests renegotiation. Not legal advice."
    ),
    version="0.2.0",
)

# CORS: use FRONTEND_URL or allow_origins env (comma-separated), else default localhost
_cors_origins = os.environ.get("ALLOW_ORIGINS") or os.environ.get("FRONTEND_URL") or ""
if _cors_origins:
    _origins = [o.strip() for o in _cors_origins.split(",") if o.strip()]
else:
    _origins = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Optional: serve React build (set STATIC_DIR to frontend dist path for single-service deploy)
_STATIC_DIR = os.environ.get("STATIC_DIR")
if _STATIC_DIR and os.path.isdir(_STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(_STATIC_DIR, "assets")), name="assets")

    @app.get("/")
    async def root():
        index = os.path.join(_STATIC_DIR, "index.html")
        return FileResponse(index) if os.path.isfile(index) else _api_root()

    def _api_root():
        return {"message": "India SME Contract Intelligence Engine is running.", "docs": "/docs"}
else:

    @app.get("/")
    async def root():
        return {
            "message": "India SME Contract Intelligence Engine is running. "
                       "POST contract text to /analyze or upload file to /analyze/file. "
                       "POST result to /export/pdf for PDF report."
        }


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze contract from raw text. Returns 10-section structured analysis."""
    result = analyze_contract(
        contract_text=request.contract_text,
        language=request.language,
        business_role=request.business_role,
    )
    audit = result.get("10_audit_log")
    if audit:
        _persist_audit_log(audit)
    return AnalyzeResponse(result=result)


@app.post("/analyze/file", response_model=AnalyzeResponse)
async def analyze_file(
    file: UploadFile = File(...),
    language: Optional[str] = Form("english"),
    business_role: Optional[str] = Form(None),
) -> AnalyzeResponse:
    """Extract text from PDF, DOCX, or TXT and analyze. Returns same structure as /analyze."""
    content = await file.read()
    text, err = extract_text_from_file(content, file.filename or "")
    if err or not (text or "").strip():
        raise HTTPException(status_code=400, detail=err or "No text extracted from file.")
    result = analyze_contract(
        contract_text=text,
        language=language,
        business_role=business_role,
    )
    audit = result.get("10_audit_log")
    if audit:
        _persist_audit_log(audit)
    return AnalyzeResponse(result=result)


@app.get("/templates")
async def list_templates() -> Dict[str, Any]:
    """List available SME-friendly contract template names and IDs."""
    return {
        "templates": [
            {"id": "service_agreement_sme", "name": "Service Agreement (SME-Friendly)", "filename": "service_agreement_sme.txt"},
        ],
    }


@app.get("/templates/{template_id}")
async def get_template(template_id: str) -> Response:
    """Return SME-friendly contract template as plain text."""
    allowed = {"service_agreement_sme"}
    if template_id not in allowed:
        raise HTTPException(status_code=404, detail="Template not found.")
    path = os.path.join(os.path.dirname(__file__), "templates", f"{template_id}.txt")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Template file not found.")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return Response(content=content, media_type="text/plain")


class ExportPdfRequest(BaseModel):
    result: Dict[str, Any]


@app.post("/export/pdf")
async def export_pdf(payload: ExportPdfRequest) -> Response:
    """Generate PDF report from analysis result (e.g. from /analyze or /analyze/file)."""
    try:
        pdf_bytes = build_analysis_pdf(payload.result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=contract_analysis_report.pdf"},
    )

