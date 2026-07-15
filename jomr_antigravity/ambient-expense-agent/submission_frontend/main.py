import os
import json
import logging
import asyncio
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

import google.auth
import google.auth.transport.requests
import httpx
import datetime
from google.cloud import aiplatform_v1

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Manager Dashboard Service")

# Read GCP Project, Location and Agent Runtime ID
PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("PROJECT_ID") or os.environ.get("GCP_PROJECT")
# Strip projects/ prefix if automatically prepended to avoid double prefixing in client libraries if they are used elsewhere
if PROJECT and PROJECT.startswith("projects/"):
    PROJECT = PROJECT[len("projects/"):]

AGENT_RUNTIME_ID = os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ID") or os.environ.get("AGENT_RUNTIME_ID")
LOCATION = os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_LOCATION") or os.environ.get("GOOGLE_CLOUD_LOCATION") or os.environ.get("LOCATION", "us-east1")

# Request Model for action
class ActionRequest(BaseModel):
    interrupt_id: str
    approved: bool
    user_id: str

class SimpleFunctionCall:
    def __init__(self, name, id, args):
        self.name = name
        self.id = id
        self.args = args or {}

class SimpleFunctionResponse:
    def __init__(self, name, id):
        self.name = name
        self.id = id

class SimplePart:
    def __init__(self, part_dict):
        self.text = part_dict.get("text")
        
        # Support both camelCase (REST API standard) and snake_case representations
        fc = part_dict.get("functionCall") or part_dict.get("function_call")
        if fc:
            self.function_call = SimpleFunctionCall(
                name=fc.get("name"),
                id=fc.get("id"),
                args=fc.get("args")
            )
        else:
            self.function_call = None
            
        fr = part_dict.get("functionResponse") or part_dict.get("function_response")
        if fr:
            self.function_response = SimpleFunctionResponse(
                name=fr.get("name"),
                id=fr.get("id")
            )
        else:
            self.function_response = None

class SimpleContent:
    def __init__(self, content_dict):
        parts_list = content_dict.get("parts", []) if content_dict else []
        self.parts = [SimplePart(p) for p in parts_list if isinstance(p, dict)]

class SimpleEvent:
    def __init__(self, author, content_data, timestamp, output=None):
        self.author = author
        self.content = SimpleContent(content_data) if content_data else None
        self.timestamp = timestamp
        self.output = output

class SimpleSession:
    def __init__(self, id, user_id, last_update_time):
        self.id = id
        self.user_id = user_id
        self.last_update_time = last_update_time

class SimpleSessionResult:
    def __init__(self, id, user_id, last_update_time, state, events):
        self.id = id
        self.user_id = user_id
        self.last_update_time = last_update_time
        self.state = state
        self.events = events

class DirectVertexAiSessionService:
    def __init__(self, project: str, location: str, agent_engine_id: str):
        self.project = project
        self.location = location
        self.agent_engine_id = agent_engine_id

    async def _get_headers(self) -> dict:
        credentials, _ = google.auth.default()
        auth_req = google.auth.transport.requests.Request()
        await asyncio.to_thread(credentials.refresh, auth_req)
        return {
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json"
        }

    async def list_sessions(self, app_name: str) -> list:
        url = f"https://{self.location}-aiplatform.googleapis.com/v1/projects/{self.project}/locations/{self.location}/reasoningEngines/{self.agent_engine_id}/sessions"
        headers = await self._get_headers()
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=headers)
            if res.status_code != 200:
                raise Exception(f"Failed to list sessions: {res.status_code} - {res.text}")
            data = res.json()
            sessions = []
            for item in data.get("sessions", []):
                name_parts = item["name"].split("/")
                sess_id = name_parts[-1]
                update_time_str = item.get("updateTime", "")
                try:
                    dt = datetime.datetime.fromisoformat(update_time_str.replace("Z", "+00:00"))
                    ts = dt.timestamp()
                except Exception:
                    ts = 0.0
                sessions.append(SimpleSession(
                    id=sess_id,
                    user_id=item.get("userId", "default-user"),
                    last_update_time=ts
                ))
            return sessions

    async def get_session(self, app_name: str, user_id: str, session_id: str) -> Optional[SimpleSessionResult]:
        url = f"https://{self.location}-aiplatform.googleapis.com/v1/projects/{self.project}/locations/{self.location}/reasoningEngines/{self.agent_engine_id}/sessions/{session_id}"
        headers = await self._get_headers()
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=headers)
            if res.status_code != 200:
                return None
            session_data = res.json()
            
            events_url = f"{url}/events"
            res_events = await client.get(events_url, headers=headers)
            events = []
            if res_events.status_code == 200:
                json_data = res_events.json()
                events_data = json_data.get("sessionEvents") or json_data.get("events") or []
                for ev in events_data:
                    author = ev.get("author")
                    raw_event = ev.get("rawEvent") or ev.get("raw_event") or {}
                    content_data = ev.get("content") or raw_event.get("content")
                    
                    ts = raw_event.get("timestamp")
                    if not ts:
                        update_time_str = ev.get("updateTime", "")
                        try:
                            dt = datetime.datetime.fromisoformat(update_time_str.replace("Z", "+00:00"))
                            ts = dt.timestamp()
                        except Exception:
                            ts = 0.0
                    output_data = raw_event.get("output")
                    events.append(SimpleEvent(author, content_data, ts, output_data))
                    
            update_time_str = session_data.get("updateTime", "")
            try:
                dt = datetime.datetime.fromisoformat(update_time_str.replace("Z", "+00:00"))
                last_update_time = dt.timestamp()
            except Exception:
                last_update_time = 0.0
                
            return SimpleSessionResult(
                id=session_id,
                user_id=session_data.get("userId", "default-user"),
                last_update_time=last_update_time,
                state=session_data.get("sessionState", {}),
                events=events
            )

def get_session_service() -> DirectVertexAiSessionService:
    if not PROJECT or not AGENT_RUNTIME_ID:
        raise HTTPException(
            status_code=500,
            detail="GCP project and AGENT_RUNTIME_ID must be set in environment variables."
        )
    return DirectVertexAiSessionService(
        project=PROJECT,
        location=LOCATION,
        agent_engine_id=AGENT_RUNTIME_ID
    )

def extract_risk_assessment(events) -> Optional[Dict[str, Any]]:
    # Search backwards for the risk reviewer's output or a flagged state
    for event in reversed(events):
        if event.author == "risk_reviewer":
            if event.output:
                return event.output
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        try:
                            return json.loads(part.text)
                        except Exception:
                            pass
        # Fallback to general workflow output containing risk assessment details
        if event.author == "expense_workflow" and event.output:
            if isinstance(event.output, dict) and "risk_level" in event.output:
                return event.output
    return None

from fastapi import FastAPI, HTTPException, Response

@app.get("/api/pending")
async def get_pending_approvals(response: Response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    try:
        service = get_session_service()
        # List all sessions for the expense agent
        sessions = await service.list_sessions(app_name="expense_agent")
        
        pending_items = []
        
        # Iterate and fetch full history for each session
        for sess in sessions:
            full_session = await service.get_session(
                app_name="expense_agent",
                user_id=sess.user_id,
                session_id=sess.id
            )
            if not full_session:
                continue
                
            # Scan events for unresolved adk_request_input interrupts
            # We track requested vs resolved interrupts
            requested = {}  # interrupt_id -> event / details
            resolved = set()
            
            for event in full_session.events:
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        # Find interrupt requests
                        if part.function_call and part.function_call.name == "adk_request_input":
                            fc = part.function_call
                            int_id = fc.id or fc.args.get("interruptId")
                            if int_id:
                                requested[int_id] = {
                                    "message": fc.args.get("message"),
                                    "timestamp": event.timestamp
                                }
                        # Find interrupt responses
                        if part.function_response and part.function_response.name == "adk_request_input":
                            fr = part.function_response
                            if fr.id:
                                resolved.add(fr.id)
                            else:
                                # Fallback to oldest unresolved
                                unresolved_keys = [k for k in requested.keys() if k not in resolved]
                                if unresolved_keys:
                                    resolved.add(unresolved_keys[0])
            
            # Find which interrupts are still unresolved
            unresolved_ids = [k for k in requested.keys() if k not in resolved]
            
            if unresolved_ids:
                # Get the last/active unresolved interrupt
                active_int_id = unresolved_ids[-1]
                int_info = requested[active_int_id]
                
                # Fetch expense details from session state
                expense = full_session.state.get("expense") or {}
                
                # Extract risk assessment details from history
                risk_assessment = extract_risk_assessment(full_session.events)
                
                pending_items.append({
                    "session_id": sess.id,
                    "user_id": sess.user_id,
                    "interrupt_id": active_int_id,
                    "expense": expense,
                    "message": int_info["message"],
                    "risk_assessment": risk_assessment,
                    "last_updated": sess.last_update_time
                })
                
        return pending_items
    except Exception as e:
        logger.error(f"Error fetching pending approvals: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/action/{session_id}")
async def post_action(session_id: str, request_data: ActionRequest):
    try:
        if not PROJECT or not AGENT_RUNTIME_ID:
            raise HTTPException(
                status_code=500,
                detail="GCP project and AGENT_RUNTIME_ID must be set in environment variables."
            )
            
        # Create a Reasoning Engine execution client to resume the agent runtime session
        client = aiplatform_v1.ReasoningEngineExecutionServiceAsyncClient(
            client_options={"api_endpoint": f"{LOCATION}-aiplatform.googleapis.com"}
        )
        
        name = f"projects/{PROJECT}/locations/{LOCATION}/reasoningEngines/{AGENT_RUNTIME_ID}"
        
        # Format the resume message payload strictly as required to avoid duplicate parameter errors on ADK
        resume_payload = {
            "role": "user",
            "parts": [
                {
                    "function_response": {
                        "id": request_data.interrupt_id,
                        "name": "adk_request_input",
                        "response": {
                            "approved": request_data.approved
                        }
                    }
                }
            ]
        }
        
        request = {
            "name": name,
            "class_method": "async_stream_query",
            "input": {
                "user_id": request_data.user_id,
                "session_id": session_id,
                "message": resume_payload
            }
        }
        
        logger.info(f"Resuming session {session_id} on engine {AGENT_RUNTIME_ID}...")
        
        # Trigger the reasoning engine stream and exhaust it to let the agent process the response
        response_stream = await client.stream_query_reasoning_engine(request=request)
        
        async for chunk in response_stream:
            # We exhaust the stream so the agent completes its run
            logger.debug(f"Received chunk: {chunk}")
            
        return {"status": "success", "message": f"Session {session_id} resumed with approved={request_data.approved}"}
        
    except Exception as e:
        logger.error(f"Error resuming session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    # Return a premium, glassmorphic manager dashboard UI
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Expense Manager Dashboard</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg-gradient: radial-gradient(circle at 50% 50%, #1a153b 0%, #0d0b18 100%);
                --card-bg: rgba(255, 255, 255, 0.04);
                --card-border: rgba(255, 255, 255, 0.08);
                --text-primary: #ffffff;
                --text-secondary: #a0aec0;
                --purple-glow: rgba(139, 92, 246, 0.15);
                --green-glow: rgba(16, 185, 129, 0.2);
                --red-glow: rgba(239, 68, 68, 0.2);
                --accent-purple: #8b5cf6;
                --accent-green: #10b981;
                --accent-red: #ef4444;
            }

            * {
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }

            body {
                font-family: 'Inter', sans-serif;
                background: var(--bg-gradient);
                color: var(--text-primary);
                min-height: 100vh;
                overflow-x: hidden;
                position: relative;
            }

            h1, h2, h3, .font-outfit {
                font-family: 'Outfit', sans-serif;
            }

            /* Glow effects */
            .glow-bg {
                position: absolute;
                width: 600px;
                height: 600px;
                background: radial-gradient(circle, rgba(139, 92, 246, 0.12) 0%, rgba(0,0,0,0) 70%);
                top: -10%;
                left: 10%;
                pointer-events: none;
                z-index: 0;
            }
            .glow-bg-right {
                position: absolute;
                width: 500px;
                height: 500px;
                background: radial-gradient(circle, rgba(16, 185, 129, 0.08) 0%, rgba(0,0,0,0) 70%);
                bottom: 10%;
                right: -10%;
                pointer-events: none;
                z-index: 0;
            }

            header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 2rem 4rem;
                border-bottom: 1px solid var(--card-border);
                backdrop-filter: blur(10px);
                position: relative;
                z-index: 10;
            }

            .logo-section {
                display: flex;
                align-items: center;
                gap: 1rem;
            }

            .logo-section h1 {
                font-size: 1.8rem;
                font-weight: 700;
                letter-spacing: -0.5px;
                background: linear-gradient(135deg, #fff 0%, #a78bfa 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }

            .badge {
                background: rgba(139, 92, 246, 0.2);
                border: 1px solid var(--accent-purple);
                color: #c4b5fd;
                padding: 0.25rem 0.75rem;
                border-radius: 9999px;
                font-size: 0.8rem;
                font-weight: 600;
            }

            .env-info {
                font-size: 0.9rem;
                color: var(--text-secondary);
                background: rgba(255, 255, 255, 0.02);
                padding: 0.5rem 1rem;
                border-radius: 8px;
                border: 1px solid var(--card-border);
            }

            .main-container {
                max-width: 1400px;
                margin: 0 auto;
                padding: 3rem 4rem;
                position: relative;
                z-index: 10;
            }

            .dashboard-title {
                font-size: 2.2rem;
                margin-bottom: 2rem;
                font-weight: 600;
            }

            /* Pending Grid */
            .grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
                gap: 2rem;
            }

            /* Card Styling */
            .card {
                background: var(--card-bg);
                border: 1px solid var(--card-border);
                border-radius: 16px;
                padding: 1.75rem;
                backdrop-filter: blur(20px);
                -webkit-backdrop-filter: blur(20px);
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                position: relative;
                overflow: hidden;
            }

            .card:hover {
                transform: translateY(-5px);
                border-color: rgba(139, 92, 246, 0.3);
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4), 0 0 1px 1px rgba(139, 92, 246, 0.2);
            }

            .card-header {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                margin-bottom: 1.5rem;
            }

            .amount {
                font-size: 2rem;
                font-weight: 700;
                color: #fff;
            }

            .submitter {
                font-size: 0.95rem;
                color: var(--text-secondary);
                margin-top: 0.25rem;
            }

            .category-tag {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                padding: 0.3rem 0.8rem;
                border-radius: 8px;
                font-size: 0.8rem;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                color: #cbd5e1;
            }

            .description-box {
                background: rgba(0, 0, 0, 0.2);
                border-radius: 8px;
                padding: 1rem;
                font-size: 0.9rem;
                line-height: 1.5;
                color: #e2e8f0;
                margin-bottom: 1.5rem;
                min-height: 4.5rem;
                border-left: 3px solid var(--accent-purple);
            }

            .risk-badge-container {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                margin-bottom: 1.5rem;
            }

            .risk-badge {
                padding: 0.35rem 0.75rem;
                border-radius: 6px;
                font-size: 0.8rem;
                font-weight: 700;
                text-transform: uppercase;
                display: inline-flex;
                align-items: center;
            }

            .risk-High {
                background: rgba(239, 68, 68, 0.15);
                border: 1px solid var(--accent-red);
                color: #fca5a5;
            }

            .risk-Medium {
                background: rgba(245, 158, 11, 0.15);
                border: 1px solid #f59e0b;
                color: #fde047;
            }

            .risk-Low {
                background: rgba(16, 185, 129, 0.15);
                border: 1px solid var(--accent-green);
                color: #a7f3d0;
            }

            .risk-None {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid var(--card-border);
                color: var(--text-secondary);
            }

            .btn-group {
                display: flex;
                gap: 1rem;
            }

            button {
                padding: 0.8rem 1.5rem;
                border-radius: 12px;
                font-weight: 600;
                font-size: 0.95rem;
                cursor: pointer;
                transition: all 0.2s ease;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 0.5rem;
                outline: none;
                flex: 1;
            }

            .btn-approve {
                background: var(--accent-green);
                border: none;
                color: #0b2216;
            }

            .btn-approve:hover {
                background: #059669;
                box-shadow: 0 0 15px rgba(16, 185, 129, 0.4);
            }

            .btn-reject {
                background: transparent;
                border: 1px solid var(--accent-red);
                color: #ef4444;
            }

            .btn-reject:hover {
                background: rgba(239, 68, 68, 0.1);
                box-shadow: 0 0 15px rgba(239, 68, 68, 0.3);
            }

            .btn-review {
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid var(--card-border);
                color: #fff;
                margin-top: 1rem;
                width: 100%;
                flex: none;
            }

            .btn-review:hover {
                background: rgba(255, 255, 255, 0.08);
                border-color: rgba(255, 255, 255, 0.2);
            }

            /* Modal / Drawer */
            .drawer-overlay {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.7);
                backdrop-filter: blur(5px);
                z-index: 100;
                opacity: 0;
                pointer-events: none;
                transition: opacity 0.3s ease;
            }

            .drawer-overlay.active {
                opacity: 1;
                pointer-events: auto;
            }

            .drawer {
                position: fixed;
                top: 0;
                right: -450px;
                width: 450px;
                height: 100%;
                background: #110e24;
                border-left: 1px solid var(--card-border);
                box-shadow: -10px 0 30px rgba(0, 0, 0, 0.5);
                z-index: 101;
                transition: right 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                display: flex;
                flex-direction: column;
                padding: 2.5rem;
            }

            .drawer.active {
                right: 0;
            }

            .drawer-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 2rem;
            }

            .drawer-header h3 {
                font-size: 1.5rem;
                font-weight: 600;
            }

            .close-btn {
                background: none;
                border: none;
                color: var(--text-secondary);
                font-size: 1.5rem;
                cursor: pointer;
                padding: 0.5rem;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            .drawer-content {
                flex: 1;
                overflow-y: auto;
            }

            .compliance-section {
                margin-bottom: 2rem;
            }

            .compliance-section-title {
                font-size: 0.85rem;
                text-transform: uppercase;
                letter-spacing: 1px;
                color: var(--text-secondary);
                margin-bottom: 0.75rem;
                font-weight: 600;
            }

            .finding-item {
                background: rgba(255, 255, 255, 0.02);
                border: 1px solid var(--card-border);
                border-radius: 8px;
                padding: 0.75rem 1rem;
                margin-bottom: 0.5rem;
                font-size: 0.9rem;
                line-height: 1.4;
            }

            .finding-item::before {
                content: "•";
                color: var(--accent-purple);
                display: inline-block;
                width: 1em;
                margin-left: -0.5em;
                font-weight: bold;
            }

            .justification-box {
                background: rgba(139, 92, 246, 0.05);
                border: 1px solid rgba(139, 92, 246, 0.15);
                border-radius: 8px;
                padding: 1.25rem;
                font-size: 0.95rem;
                line-height: 1.5;
                color: #e2e8f0;
            }

            /* Spinner */
            .spinner {
                border: 2px solid rgba(255, 255, 255, 0.1);
                width: 20px;
                height: 20px;
                border-radius: 50%;
                border-left-color: currentColor;
                animation: spin 1s linear infinite;
                display: none;
            }

            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }

            .no-pending {
                text-align: center;
                grid-column: 1 / -1;
                padding: 5rem 2rem;
                background: var(--card-bg);
                border: 1px solid var(--card-border);
                border-radius: 16px;
                backdrop-filter: blur(20px);
            }

            .no-pending p {
                font-size: 1.2rem;
                color: var(--text-secondary);
                margin-bottom: 1.5rem;
            }

            .loading-container {
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 300px;
                width: 100%;
                grid-column: 1 / -1;
            }

            .spinner-large {
                border: 4px solid rgba(139, 92, 246, 0.1);
                width: 50px;
                height: 50px;
                border-radius: 50%;
                border-left-color: var(--accent-purple);
                animation: spin 1s linear infinite;
            }
        </style>
    </head>
    <body>
        <div class="glow-bg"></div>
        <div class="glow-bg-right"></div>

        <header>
            <div class="logo-section">
                <h1>Autonomous Expense Compliance</h1>
                <span class="badge">Manager Review</span>
            </div>
            <div class="env-info">
                GCP: <span style="color: #fff">__PROJECT__</span> &nbsp;|&nbsp; 
                Engine ID: <span style="color: #fff">__AGENT_RUNTIME_ID__</span>
            </div>
        </header>

        <main class="main-container">
            <h2 class="dashboard-title">Pending Manager Approvals</h2>

            <div id="grid-container" class="grid">
                <div class="loading-container">
                    <div class="spinner-large"></div>
                </div>
            </div>
        </main>

        <!-- Slide Out Drawer -->
        <div class="drawer-overlay" id="drawer-overlay" onclick="closeDrawer()"></div>
        <div class="drawer" id="drawer">
            <div class="drawer-header">
                <h3>Compliance Review</h3>
                <button class="close-btn" onclick="closeDrawer()">&times;</button>
            </div>
            <div class="drawer-content" id="drawer-content">
                <!-- Filled dynamically -->
            </div>
        </div>

        <script>
            let pendingItems = [];

            async function fetchPending() {
                try {
                    const res = await fetch('/api/pending');
                    pendingItems = await res.json();
                    renderGrid();
                } catch (err) {
                    console.error("Error fetching approvals", err);
                    document.getElementById('grid-container').innerHTML = `
                        <div class="no-pending" style="border-color: var(--accent-red)">
                            <p style="color: var(--accent-red)">Failed to load pending approvals from backend</p>
                            <p style="font-size: 0.9rem; margin-top: 0.5rem">${err.message}</p>
                        </div>
                    `;
                }
            }

            function renderGrid() {
                const container = document.getElementById('grid-container');
                if (pendingItems.length === 0) {
                    container.innerHTML = `
                        <div class="no-pending">
                            <p>All expense approvals are completed</p>
                            <span style="font-size: 0.9rem; color: var(--text-secondary)">No items require manual review at this time.</span>
                        </div>
                    `;
                    return;
                }

                container.innerHTML = pendingItems.map((item, idx) => {
                    const exp = item.expense || {};
                    const risk = item.risk_assessment || {};
                    const riskLevel = risk.risk_level || 'Low';
                    
                    return `
                        <div class="card" id="card-${item.session_id}">
                            <div class="card-header">
                                <div>
                                    <div class="amount">$${exp.amount || '0.00'}</div>
                                    <div class="submitter">${exp.submitter || 'unknown@company.com'}</div>
                                </div>
                                <span class="category-tag">${exp.category || 'General'}</span>
                            </div>

                            <div class="description-box">
                                "${exp.description || 'No description provided'}"
                            </div>

                            <div class="risk-badge-container">
                                <span class="risk-badge risk-${riskLevel}">
                                    Risk: ${riskLevel}
                                </span>
                            </div>

                            <div class="btn-group">
                                <button class="btn-approve" onclick="handleAction('${item.session_id}', '${item.user_id}', '${item.interrupt_id}', true, this)">
                                    <span class="spinner" id="spin-approve-${item.session_id}"></span>
                                    <span>Approve</span>
                                </button>
                                <button class="btn-reject" onclick="handleAction('${item.session_id}', '${item.user_id}', '${item.interrupt_id}', false, this)">
                                    <span class="spinner" id="spin-reject-${item.session_id}"></span>
                                    <span>Reject</span>
                                </button>
                            </div>

                            <button class="btn-review" onclick="openDrawer(${idx})">
                                View Compliance Logs
                            </button>
                        </div>
                    `;
                }).join('');
            }

            async function handleAction(sessionId, userId, interruptId, approved, btn) {
                const card = document.getElementById(`card-${sessionId}`);
                const approveSpinner = document.getElementById(`spin-approve-${sessionId}`);
                const rejectSpinner = document.getElementById(`spin-reject-${sessionId}`);
                
                // Show loading spinner
                if (approved) {
                    approveSpinner.style.display = 'inline-block';
                } else {
                    rejectSpinner.style.display = 'inline-block';
                }

                // Disable all buttons in this card
                const buttons = card.querySelectorAll('button');
                buttons.forEach(b => b.disabled = true);

                try {
                    const res = await fetch(`/api/action/${sessionId}`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ interrupt_id: interruptId, approved: approved, user_id: userId })
                    });
                    
                    if (res.ok) {
                        // Smooth removal animation
                        card.style.opacity = '0';
                        card.style.transform = 'scale(0.9) translateY(10px)';
                        setTimeout(() => {
                            pendingItems = pendingItems.filter(item => item.session_id !== sessionId);
                            renderGrid();
                        }, 300);
                    } else {
                        alert("Failed to submit action to agent runtime");
                        buttons.forEach(b => b.disabled = false);
                    }
                } catch (err) {
                    console.error(err);
                    alert("Error submitting action: " + err.message);
                    buttons.forEach(b => b.disabled = false);
                } finally {
                    approveSpinner.style.display = 'none';
                    rejectSpinner.style.display = 'none';
                }
            }

            function openDrawer(idx) {
                const item = pendingItems[idx];
                const risk = item.risk_assessment || {};
                const findings = risk.findings || [];
                
                let findingsHtml = findings.map(f => `<div class="finding-item">${f}</div>`).join('');
                if (findings.length === 0) {
                    findingsHtml = '<p style="color: var(--text-secondary); font-size: 0.9rem">No anomaly findings recorded</p>';
                }

                const content = `
                    <div class="compliance-section">
                        <div class="compliance-section-title">Risk Assessment Evaluation</div>
                        <div class="risk-badge-container">
                            <span class="risk-badge risk-${risk.risk_level || 'Low'}">
                                ${risk.risk_level || 'Low'} Risk
                            </span>
                        </div>
                    </div>

                    <div class="compliance-section">
                        <div class="compliance-section-title">Justification</div>
                        <div class="justification-box">
                            ${risk.justification || 'No justification logs available from compliance model.'}
                        </div>
                    </div>

                    <div class="compliance-section">
                        <div class="compliance-section-title">Anomaly Findings</div>
                        ${findingsHtml}
                    </div>
                `;

                document.getElementById('drawer-content').innerHTML = content;
                document.getElementById('drawer').classList.add('active');
                document.getElementById('drawer-overlay').classList.add('active');
            }

            function closeDrawer() {
                document.getElementById('drawer').classList.remove('active');
                document.getElementById('drawer-overlay').classList.remove('active');
            }

            // Initial load
            fetchPending();
        </script>
    </body>
    </html>
    """
    return html_content.replace("__PROJECT__", PROJECT or "Not set").replace("__AGENT_RUNTIME_ID__", AGENT_RUNTIME_ID or "Not set")
