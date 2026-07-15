import asyncio
import json
import os
from dotenv import load_dotenv

load_dotenv()
with open("deployment_metadata.json") as f:
    meta = json.load(f)

os.environ["GOOGLE_CLOUD_PROJECT"] = "project-a3eb1889-fbc0-4f8e-a9a"
os.environ["AGENT_RUNTIME_ID"] = meta["remote_agent_runtime_id"].split("/")[-1]
os.environ["GOOGLE_CLOUD_LOCATION"] = "us-east1"

from submission_frontend.main import get_pending_approvals
from fastapi import Response

async def main():
    resp = Response()
    res = await get_pending_approvals(resp)
    print("PENDING APPROVALS JSON:")
    print(json.dumps(res, indent=2))

asyncio.run(main())
