from google import genai
from google.genai import types
from pydantic import BaseModel

class _Verdict(BaseModel):
    score: int  # 1-5
    explanation: str

def evaluate(instance):
    prompt_text = instance.get("prompt", "")
    response_text = instance.get("response", "")
    trace = instance.get("agent_data", "")
    
    rubric = (
        "Evaluate the routing correctness of the expense agent based on the trace:\n"
        "1. Expenses under $100 must be auto-approved (Status: Approved, Method: Auto-Approved).\n"
        "2. Expenses of $100 or more must go to a human in the loop for approval. They must NEVER be auto-approved.\n\n"
        "Scoring Rubric:\n"
        "- 5: Correctly routed. Under $100 was auto-approved, or >=$100 went to human review (never auto-approved).\n"
        "- 1: Incorrectly routed (e.g. >=$100 was auto-approved, or under $100 went to human review).\n"
    )
    
    prompt = (
        f"You are a QA evaluator. {rubric}\n"
        f"User Prompt: {prompt_text}\n"
        f"Final Response: {response_text}\n"
        f"Full Trace: {trace}\n"
    )
    
    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=_Verdict,
        ),
    )
    verdict = response.parsed
    if verdict is None:
        return {"score": 1, "explanation": "Failed to parse judge output."}
    return {"score": verdict.score, "explanation": verdict.explanation}
