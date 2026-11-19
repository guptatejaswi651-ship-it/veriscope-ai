import asyncio
import os
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from agents.research_agent import search, ResearchProviderError
from agents.verification_agent import verify, AnalysisProviderError
from agents.conflict_agent import find_conflicts
from agents.report_chat_agent import answer_report_question
from agents.ai_provider import provider_label
from agents.report_agent import build_report
from database import get_report, history, save

router = APIRouter(prefix="/api", tags=["research"])

class ResearchRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)

class ReportQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=2000)

class ReportAnswer(BaseModel):
    answer: str
    source_ids: list[int]

class AgentStatus(BaseModel):
    status: str
    message: str

class Source(BaseModel):
    id: int
    title: str
    url: str
    domain: str
    published_at: str | None = None
    retrieved_at: str
    snippet: str = ""

class Claim(BaseModel):
    text: str
    status: str
    explanation: str
    source_ids: list[int]

class Finding(BaseModel):
    title: str
    detail: str
    source_ids: list[int]

class Conflict(BaseModel):
    title: str
    explanation: str
    source_ids: list[int]

class ResearchReport(BaseModel):
    research_id: str
    original_question: str
    summary: str
    findings: list[Finding]
    claims: list[Claim]
    conflicts: list[Conflict]
    sources: list[Source]
    agents_status: dict[str, AgentStatus]
    limitations: list[str]
    evidence_assessment: str
    generated_at: str

@router.post("/research", response_model=ResearchReport)
async def create_research(request: ResearchRequest):
    question = request.question.strip()
    if len(question) < 3:
        raise HTTPException(status_code=422, detail="Question must contain at least 3 non-space characters.")
    tavily_key = os.getenv("TAVILY_API_KEY")
    ai_provider_name = provider_label()
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip().rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen3.5:4b").strip()
    ollama_base_url = ollama_base_url or "http://127.0.0.1:11434"
    model = model or "qwen3.5:4b"
    if not tavily_key:
        raise HTTPException(status_code=503, detail="Research is not configured: set TAVILY_API_KEY in backend/.env.")

    try:
        sources = await search(question, tavily_key)
    except ResearchProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    verification_message = None
    conflict_message = None
    analysis_result, conflicts_result = await asyncio.gather(
        verify(question, sources, ollama_base_url, model),
        find_conflicts(question, sources, ollama_base_url, model),
        return_exceptions=True,
    )
    if isinstance(analysis_result, BaseException) and not isinstance(analysis_result, AnalysisProviderError):
        raise analysis_result
    if isinstance(conflicts_result, BaseException) and not isinstance(conflicts_result, AnalysisProviderError):
        raise conflicts_result

    if isinstance(analysis_result, AnalysisProviderError):
        verification_message = f"{ai_provider_name} verification is unavailable. {analysis_result}"
        analysis = {
            "summary": "",
            "findings": [],
            "claims": [],
            "assessment": f"AI evidence assessment unavailable because {ai_provider_name} verification could not be completed.",
        }
        conflicts = []
        conflict_message = "Conflict result was not included because verification was unavailable."
    else:
        analysis = analysis_result
        if isinstance(conflicts_result, AnalysisProviderError):
            conflicts = []
            conflict_message = f"{ai_provider_name} conflict analysis is unavailable. {conflicts_result}"
        else:
            conflicts = conflicts_result

    report = build_report(
        question,
        sources,
        analysis,
        conflicts,
        str(uuid.uuid4()),
        verification_message=verification_message,
        conflict_message=conflict_message,
    )
    save(report)
    return report

@router.get("/research/{research_id}", response_model=ResearchReport)
def get_research(research_id: str):
    report = get_report(research_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Research report not found.")
    return report

@router.post("/research/{research_id}/ask", response_model=ReportAnswer)
async def ask_about_research(research_id: str, request: ReportQuestion):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question must contain at least one non-space character.")
    report = get_report(research_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Research report not found.")

    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip().rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen3.5:4b").strip()
    try:
        return await answer_report_question(
            question,
            report,
            ollama_base_url or "http://127.0.0.1:11434",
            model or "qwen3.5:4b",
        )
    except AnalysisProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

@router.get("/history")
def get_history():
    return history()
