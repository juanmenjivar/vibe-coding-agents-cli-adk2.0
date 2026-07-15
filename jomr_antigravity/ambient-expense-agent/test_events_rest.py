import asyncio
import google.auth
import google.auth.transport.requests
import httpx

async def main():
    credentials, project = google.auth.default()
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    
    headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json"
    }
    
    # Query events for the session
    url = "https://us-east1-aiplatform.googleapis.com/v1/projects/project-a3eb1889-fbc0-4f8e-a9a/locations/us-east1/reasoningEngines/7474814297156091904/sessions/3784779057304961024/events"
    
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=headers)
        print("Status code:", res.status_code)
        if res.status_code == 200:
            data = res.json()
            print("Response keys:", list(data.keys()))
            print("Events list type/len:", type(data.get("events")), len(data.get("events", [])))
            print("First event preview:", data.get("events", [])[0] if data.get("events") else "None")

if __name__ == '__main__':
    asyncio.run(main())
