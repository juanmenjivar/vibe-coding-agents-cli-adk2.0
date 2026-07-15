import asyncio
import json
import os
import httpx
import google.auth
import google.auth.transport.requests

credentials, _ = google.auth.default()
auth_req = google.auth.transport.requests.Request()
credentials.refresh(auth_req)
headers = {
    'Authorization': f'Bearer {credentials.token}',
    'Content-Type': 'application/json'
}

url = 'https://us-east1-aiplatform.googleapis.com/v1/projects/project-a3eb1889-fbc0-4f8e-a9a/locations/us-east1/reasoningEngines/7474814297156091904/sessions/8826699577634586624/events'
res = httpx.get(url, headers=headers)
print(json.dumps(res.json(), indent=2))
