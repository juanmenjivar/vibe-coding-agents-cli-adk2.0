import asyncio
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file before anything else
load_dotenv()

from google.adk.runners import Runner
from google.genai import types as genai_types
from expense_agent.agent import app as adk_app
from expense_agent.agent import expense_workflow as root_agent
from expense_agent.agent import risk_reviewer
from expense_agent.app_utils import services

async def run_scenario(case):
    runner = Runner(
        app=adk_app,
        session_service=services.get_session_service(),
        artifact_service=services.get_artifact_service(),
        auto_create_session=True,
    )
    
    prompt_text = case["prompt"]["parts"][0]["text"]
    session_id = f"session_{case['eval_case_id']}"
    
    # Clean up previous session if it exists to ensure a fresh run
    await runner.session_service.delete_session(
        app_name=adk_app.name,
        user_id="user",
        session_id=session_id
    )
    
    new_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part.from_text(text=prompt_text)]
    )
    
    print(f"Running scenario: {case['eval_case_id']}")
    
    generator = runner.run_async(
        user_id="user",
        session_id=session_id,
        new_message=new_message,
        yield_user_message=True
    )
    
    async def process_generator(gen):
        async for event in gen:
            # Check for interrupt
            if event.long_running_tool_ids and "human_decision" in event.long_running_tool_ids:
                # Automate decision
                decision = "Approved"
                description = json.loads(prompt_text).get("description", "").lower()
                category = json.loads(prompt_text).get("category", "").lower()
                
                # Reject prompt injections or luxury items
                if ("bypass" in description or 
                    "ignore" in description or 
                    "override" in description or 
                    category == "luxury"):
                    decision = "Rejected"
                
                print(f"  [INTERRUPT] Automating decision: {decision}")
                
                resume_payload = genai_types.Content(
                    role="user",
                    parts=[genai_types.Part.from_function_response(
                        name="adk_request_input",
                        response={"result": decision}
                    )]
                )
                
                resume_gen = runner.run_async(
                    user_id="user",
                    session_id=session_id,
                    invocation_id=event.invocation_id,
                    new_message=resume_payload
                )
                await process_generator(resume_gen)
                
    await process_generator(generator)
    
    # Retrieve the final session events from session service
    session = await runner.session_service.get_session(
        app_name=adk_app.name,
        user_id="user",
        session_id=session_id
    )
    
    serialized_events = []
    for ev in session.events:
        ev_dict = json.loads(ev.model_dump_json(exclude_none=True))
        # Strip thought signatures for clean evaluation traces
        if "content" in ev_dict and "parts" in ev_dict["content"]:
            for part in ev_dict["content"]["parts"]:
                part.pop("thought_signature", None)
        # Normalize model author to agent name
        author = ev_dict.get("author")
        if author == "model":
            author = adk_app.name
        
        # Only keep author and content to match strict EvaluationDataset schema
        clean_ev = {
            "author": author or "",
            "content": ev_dict.get("content", {})
        }
        serialized_events.append(clean_ev)
        
    # Extract final text response for the evaluation SDK
    final_response = None
    for ev in reversed(serialized_events):
        content = ev.get("content") or {}
        parts = content.get("parts") or []
        texts = [p.get("text") for p in parts if p.get("text")]
        if texts:
            final_response = {
                "response": {
                    "role": content.get("role") or "model",
                    "parts": [{"text": "".join(texts)}]
                }
            }
            break

    ret = {
        "eval_case_id": case["eval_case_id"],
        "prompt": case["prompt"],
        "agent_data": {
            "agents": {
                adk_app.name: {
                    "agent_id": adk_app.name,
                    "instruction": risk_reviewer.instruction
                }
            },
            "turns": [
                {
                    "turn_index": 0,
                    "events": serialized_events
                }
            ]
        }
    }
    if final_response:
        ret["responses"] = [final_response]
    return ret

async def main():
    dataset_path = Path("tests/eval/datasets/basic-dataset.json")
    output_path = Path("artifacts/traces/generated_traces.json")
    
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)
        
    eval_cases = []
    for case in dataset.get("eval_cases", []):
        try:
            eval_case = await run_scenario(case)
            eval_cases.append(eval_case)
        except Exception as e:
            print(f"Error running case {case['eval_case_id']}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"eval_cases": eval_cases}, f, indent=2)
        
    print(f"Successfully generated {len(eval_cases)} traces in {output_path}")

if __name__ == "__main__":
    asyncio.run(main())
