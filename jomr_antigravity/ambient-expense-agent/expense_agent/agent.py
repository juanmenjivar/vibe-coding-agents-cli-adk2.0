# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import json
import re
from typing import Any

from pydantic import BaseModel, Field
from google.genai import types
from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.workflow import Workflow
from google.adk.events.event import Event
from google.adk.agents.context import Context
from google.adk.events.request_input import RequestInput
from google.adk.apps import App

from .config import CONFIG

# Pydantic models for structured output and validation
class Expense(BaseModel):
    amount: float
    submitter: str
    category: str
    description: str
    date: str

class RiskAssessment(BaseModel):
    risk_level: str = Field(description="The evaluated risk level: Low, Medium, or High")
    justification: str = Field(description="Detailed explanation/justification for the risk level")
    findings: list[str] = Field(default_factory=list, description="Specific risk findings or anomalies identified")

# 1. Parse Expense Node
def parse_expense(ctx: Context, node_input: Any) -> Event | None:
    """Parses incoming JSON events (Pub/Sub base64 or raw JSON) and routes based on amount threshold."""
    if ctx.resume_inputs:
        # Skip parsing if we are resuming from a human interrupt
        return None
    raw_str = ""
    if isinstance(node_input, types.Content):
        if node_input.parts:
            raw_str = node_input.parts[0].text
    elif isinstance(node_input, str):
        raw_str = node_input

    data_dict = {}
    if raw_str:
        try:
            data_dict = json.loads(raw_str)
        except Exception:
            pass
    elif isinstance(node_input, dict):
        data_dict = node_input

    # Normalize Pub/Sub event structure if present
    if "message" in data_dict and isinstance(data_dict["message"], dict):
        msg = data_dict["message"]
        data_val = msg.get("data", msg)
    elif "data" in data_dict:
        data_val = data_dict["data"]
    else:
        data_val = data_dict

    # Decode base64 if needed
    if isinstance(data_val, str):
        try:
            decoded = base64.b64decode(data_val).decode('utf-8')
            data_val = json.loads(decoded)
        except Exception:
            try:
                data_val = json.loads(data_val)
            except Exception:
                pass

    if not isinstance(data_val, dict):
        raise ValueError(f"Could not parse valid JSON or dictionary from input: {node_input}")

    # Map fields to Expense schema
    expense = Expense(
        amount=float(data_val.get("amount", 0.0)),
        submitter=str(data_val.get("submitter", "Unknown")),
        category=str(data_val.get("category", "General")),
        description=str(data_val.get("description", "")),
        date=str(data_val.get("date", ""))
    )

    # Route dynamically in Python code based on config threshold
    if expense.amount < CONFIG.THRESHOLD:
        return Event(
            output=expense.model_dump(),
            route="auto_approve",
            state={"expense": expense.model_dump()}
        )
    else:
        return Event(
            output=expense.model_dump(),
            route="review_expense",
            state={"expense": expense.model_dump()}
        )

# 2. Auto Approve Node
def auto_approve(node_input: dict) -> dict:
    """Automatically approves expenses under the threshold."""
    return {
        "status": "Approved",
        "method": "Auto-Approved",
        "expense": node_input,
        "risk_assessment": {
            "risk_level": "None",
            "justification": "Amount is below the review threshold.",
            "findings": []
        }
    }

# 3. LLM Risk Reviewer Agent
risk_reviewer = LlmAgent(
    name="risk_reviewer",
    model=Gemini(
        model=CONFIG.MODEL_NAME,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are an expense compliance reviewer. Review the provided expense details and perform a "
        "risk assessment. Classify the risk level as Low, Medium, or High, provide a clear justification, "
        "and list any specific findings (such as vagueness, non-business categories, or unusual amounts)."
    ),
    output_schema=RiskAssessment,
)

# 3.5 Security Checkpoint Node
def security_checkpoint(ctx: Context, node_input: dict) -> Event:
    """Scrubs PII and checks for prompt injection in the expense description."""
    description = node_input.get("description", "")
    category = node_input.get("category", "General")
    
    # 1. PII Scrubbing
    # SSN Regex (matches XXX-XX-XXXX)
    ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'
    # Credit Card Regex (matches typical 16 digit numbers or groups of 4 separated by space/dash)
    cc_pattern = r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b'
    
    redacted = False
    new_desc = description
    if re.search(ssn_pattern, new_desc):
        new_desc = re.sub(ssn_pattern, "[SSN_REDACTED]", new_desc)
        redacted = True
    if re.search(cc_pattern, new_desc):
        new_desc = re.sub(cc_pattern, "[CREDIT_CARD_REDACTED]", new_desc)
        redacted = True
        
    cleaned_expense = node_input.copy()
    cleaned_expense["description"] = new_desc
    
    # Record redacted categories if PII was scrubbed
    redacted_categories = ctx.state.get("redacted_categories", [])
    if redacted and category not in redacted_categories:
        redacted_categories.append(category)
        
    state_delta = {
        "expense": cleaned_expense,
        "redacted_categories": redacted_categories
    }
    
    # 2. Prompt Injection Defense
    injection_keywords = [
        "ignore previous instructions",
        "ignore the rules",
        "bypass review",
        "auto-approve",
        "bypass the rules",
        "system override",
        "override rules",
        "approve automatically",
        "you are now an auto-approver"
    ]
    
    injection_detected = False
    for keyword in injection_keywords:
        if keyword in description.lower():
            injection_detected = True
            break
            
    if injection_detected:
        state_delta["security_flag"] = True
        # Create a mock RiskAssessment structure to bypass the LLM and go straight to human
        injection_assessment = {
            "risk_level": "High",
            "justification": "[SECURITY ALERT] Prompt injection attempt detected in the expense description.",
            "findings": [
                "Prompt injection attempt detected in description",
                f"Suspicious phrase keyword match in: '{description}'"
            ]
        }
        return Event(
            output=injection_assessment,
            route="injection_detected",
            state=state_delta
        )
        
    return Event(
        output=cleaned_expense,
        route="clean",
        state=state_delta
    )

# 4. Human Approval Node (review_agent)
async def review_agent(ctx: Context, node_input: dict):
    """Pauses workflow to request human decision on reviewed expenses."""
    expense = ctx.state.get("expense", {})
    
    if not ctx.resume_inputs:
        msg = (
            f"[ALERT] Human approval required for expense of ${expense.get('amount')} submitted by {expense.get('submitter')}.\n\n"
            f"Risk Assessment Findings:\n"
            f"- Risk Level: {node_input.get('risk_level')}\n"
            f"- Justification: {node_input.get('justification')}\n"
            f"- Specific Findings: {', '.join(node_input.get('findings', []))}\n\n"
            f"Please respond with 'Approved' or 'Rejected'."
        )
        yield RequestInput(
            interrupt_id="human_decision",
            message=msg
        )
        return

    decision = ctx.resume_inputs.get("human_decision", "Rejected")
    yield Event(
        output={
            "status": decision,
            "method": "Human Review",
            "expense": expense,
            "risk_assessment": node_input
        }
    )

# 5. Record Outcome Node
def record_outcome(ctx: Context, node_input: dict | str):
    """Logs the final outcome and emits a UI content event."""
    if isinstance(node_input, str):
        status = node_input
        method = "Human Review"
    elif isinstance(node_input, dict):
        if "status" in node_input:
            status = node_input.get("status")
            method = node_input.get("method")
        else:
            status = node_input.get("human_decision", "Rejected")
            method = "Human Review"
    else:
        status = "Rejected"
        method = "Human Review"

    expense = ctx.state.get("expense", {})
    amount = expense.get("amount", 0.0)
    submitter = expense.get("submitter", "Unknown")
    redacted_categories = ctx.state.get("redacted_categories", [])
    security_flag = ctx.state.get("security_flag", False)

    summary_lines = [
        f"[SUCCESS] Expense process complete.",
        f"- Submitter: {submitter}",
        f"- Amount: ${amount}",
        f"- Status: {status} (via {method})"
    ]
    if redacted_categories:
        summary_lines.append(f"- Redacted Categories (PII Scrubbed): {', '.join(redacted_categories)}")
    if security_flag:
        summary_lines.append("- [SECURITY ALERT] This transaction was flagged for a prompt injection attempt!")

    summary_text = "\n".join(summary_lines)

    yield Event(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=summary_text)]
        )
    )
    yield Event(output=node_input)

# Graph Workflow Construction
expense_workflow = Workflow(
    name="expense_workflow",
    edges=[
        ("START", parse_expense),
        (parse_expense, {
            "auto_approve": auto_approve,
            "review_expense": security_checkpoint,
        }),
        (security_checkpoint, {
            "clean": risk_reviewer,
            "injection_detected": review_agent,
        }),
        (risk_reviewer, review_agent),
        (review_agent, record_outcome),
        (auto_approve, record_outcome),
    ]
)

app = App(
    root_agent=expense_workflow,
    name="expense_agent",
)
