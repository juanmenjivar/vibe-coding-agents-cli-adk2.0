import asyncio
from google.adk.sessions.vertex_ai_session_service import VertexAiSessionService

async def main():
    import traceback
    try:
        s = VertexAiSessionService(
            project='project-a3eb1889-fbc0-4f8e-a9a',
            location='us-east1',
            agent_engine_id='7474814297156091904'
        )
        sessions = await s.list_sessions(app_name='expense_agent')
        print("SESSIONS COUNT:", len(sessions.sessions) if hasattr(sessions, 'sessions') else 0)
        for sess in getattr(sessions, 'sessions', []):
            print(f"ID: {sess.id}, State: {sess.state}, Time: {sess.last_update_time}")
    except Exception as e:
        print(f"An error occurred: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())
