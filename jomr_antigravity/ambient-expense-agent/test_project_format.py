import asyncio
import traceback
from google.adk.sessions.vertex_ai_session_service import VertexAiSessionService

async def test_format(project_val):
    print(f"\n--- Testing project format: '{project_val}' ---")
    try:
        s = VertexAiSessionService(
            project=project_val,
            location='us-east1',
            agent_engine_id='7474814297156091904'
        )
        api_client = s._get_api_client()
        # Mock/Inspect parameter conversion
        from google.genai import types
        from vertexai._genai.sessions import _ListAgentEngineSessionsRequestParameters_to_vertex
        parameter_model = types._ListAgentEngineSessionsRequestParameters(
            name='reasoningEngines/7474814297156091904',
        )
        # We need to bind the client context to convert it
        # Under the hood, _ListAgentEngineSessionsRequestParameters_to_vertex is generated.
        # Let's see what request_dict is generated. We can inspect the client's internal client mapping.
        # Let's just run it and catch client details.
        sessions = await s.list_sessions(app_name='expense_agent')
        print(f"SUCCESS! Sessions found: {len(sessions.sessions) if hasattr(sessions, 'sessions') else 0}")
    except Exception as e:
        print(f"FAILED: {e}")
        traceback.print_exc()

async def main():
    await test_format('project-a3eb1889-fbc0-4f8e-a9a')
    await test_format('projects/project-a3eb1889-fbc0-4f8e-a9a')

if __name__ == '__main__':
    asyncio.run(main())
