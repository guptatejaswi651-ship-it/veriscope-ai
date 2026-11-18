from datetime import datetime, timezone

def build_report(
    question: str,
    sources: list[dict],
    analysis: dict,
    conflicts: list[dict],
    research_id: str,
    verification_message: str | None = None,
    conflict_message: str | None = None,
) -> dict:
    summary = analysis["summary"]
    limitations = [
        "Search results may omit relevant evidence; review the linked sources independently.",
        "Publication dates are shown only when supplied by the search provider; retrieval timestamps are recorded separately.",
        "AI-generated analysis can be mistaken. This report is not proof of truth.",
    ]
    if verification_message:
        summary = (
            "System-generated status message (not an AI-generated research summary): "
            f"AI verification is unavailable. Retrieved {len(sources)} real source(s) from Tavily."
        )
        limitations.append(
            f"AI verification could not be completed: {verification_message} No verification findings or claims were generated."
        )
    if conflict_message:
        limitations.append(
            f"AI conflict analysis could not be completed: {conflict_message} No conflicts were generated."
        )

    return {
        "research_id": research_id,
        "original_question": question,
        "summary": summary,
        "findings": analysis["findings"],
        "claims": analysis["claims"],
        "conflicts": conflicts,
        "sources": sources,
        "agents_status": {
            "research": {"status": "completed", "message": f"Retrieved {len(sources)} source(s) from Tavily."},
            "verification": {
                "status": "unavailable" if verification_message else "completed",
                "message": verification_message or "Claims were checked against retrieved evidence.",
            },
            "conflict": {
                "status": "unavailable" if conflict_message else "completed",
                "message": conflict_message or "Source disagreements were compared.",
            },
            "report": {"status": "completed", "message": "Structured report generated."},
        },
        "limitations": limitations,
        "evidence_assessment": analysis["assessment"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
