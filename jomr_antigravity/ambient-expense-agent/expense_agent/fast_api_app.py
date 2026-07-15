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

import contextlib
import json
import os
import logging
from collections.abc import AsyncIterator

import google.auth
from a2a.server.tasks import InMemoryTaskStore
from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.requests import Request
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import Runner

from expense_agent.app_utils import services
from expense_agent.app_utils.a2a import attach_a2a_routes
from expense_agent.app_utils.telemetry import setup_telemetry
from expense_agent.app_utils.reasoning_engine_adapter import attach_reasoning_engine_routes
from expense_agent.app_utils.typing import Feedback

load_dotenv()
setup_telemetry()

# Configure standard Python logging for console logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from expense_agent.agent import app as adk_app
    from expense_agent.agent import expense_workflow as root_agent

    runner = Runner(
        app=adk_app,
        session_service=services.get_session_service(),
        artifact_service=services.get_artifact_service(),
        auto_create_session=True,
    )
    app.state.runner = runner
    app.state.agent_app_name = adk_app.name
    await attach_a2a_routes(
        app,
        agent=root_agent,
        runner=runner,
        task_store=InMemoryTaskStore(),
        rpc_path=f"/a2a/{adk_app.name}",
    )
    yield


app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=False,
    trigger_sources=["pubsub"],
    artifact_service_uri=services.ARTIFACT_SERVICE_URI,
    allow_origins=allow_origins,
    session_service_uri=services.SESSION_SERVICE_URI,
    otel_to_cloud=False,
    lifespan=lifespan,
)
app.title = "ambient-expense-agent"
app.description = "API for interacting with the Agent ambient-expense-agent"

attach_reasoning_engine_routes(app)


@app.middleware("http")
async def normalize_pubsub_subscription(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Normalize projects/.../subscriptions/NAME to just NAME.

    Pub/Sub push deliveries include the fully-qualified subscription
    resource path. The ADK trigger handler uses this value as the
    session user_id. Normalizing to the short name keeps session
    records clean and consistent.
    """
    if request.url.path.endswith("/trigger/pubsub") and request.method == "POST":
        body = await request.body()
        try:
            data = json.loads(body)
            sub = data.get("subscription", "")
            if "/" in sub:
                data["subscription"] = sub.rsplit("/", 1)[-1]
                request._body = json.dumps(data).encode()
                logger.info(f"Normalized subscription path to: {data['subscription']}")
        except (json.JSONDecodeError, KeyError):
            pass
    return await call_next(request)


@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Collect and log feedback.

    Args:
        feedback: The feedback data to log

    Returns:
        Success message
    """
    logger.info(f"Feedback received: {feedback.model_dump()}")
    return {"status": "success"}


# Main execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
