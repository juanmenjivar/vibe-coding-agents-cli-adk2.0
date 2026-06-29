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

import os
from dotenv import load_dotenv
import google.auth
from google.auth.exceptions import DefaultCredentialsError

from google.adk import Agent, Workflow, Event, Context
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types
from pydantic import BaseModel

load_dotenv()

# Handle authentication setup for Vertex AI vs Developer Gemini API
try:
    _, project_id = google.auth.default()
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")
except DefaultCredentialsError:
    if os.getenv("GEMINI_API_KEY"):
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"
    else:
        raise

# Initialize the Gemini model
model_instance = Gemini(
    model="gemini-flash-latest",
    retry_options=types.HttpRetryOptions(attempts=3),
)

# Input schema for shipping FAQ agent
class ShippingQuery(BaseModel):
    query: str

def store_query_node(node_input: str):
    """Stores the original query in the session state and forwards it."""
    return Event(
        state={"query": node_input},
        output=node_input
    )

classifier_agent = Agent(
    name="classifier_agent",
    model=model_instance,
    instruction="""
    Classify the incoming user query.
    If the query is related to shipping (such as shipping rates, shipment tracking, package delivery, returns, or pickup), reply with 'SHIPPING'.
    If the query is unrelated to shipping, reply with 'UNRELATED'.
    Do not include any other text in your output, just 'SHIPPING' or 'UNRELATED'.
    """,
    output_schema=str,
    mode="single_turn",
)

def router(node_input: str):
    """Routes the query based on classification."""
    print(f"Router input: {node_input}")
    val = node_input.strip().upper()
    if "SHIPPING" in val:
        return Event(route="SHIPPING_FAQ")
    else:
        return Event(route="DECLINE")

async def prepare_faq_input(ctx: Context):
    """Retrieves the stored query and wraps it in the ShippingQuery schema."""
    query = ctx.state.get("query", "")
    return Event(output=ShippingQuery(query=query))

shipping_faq_agent = Agent(
    name="shipping_faq_agent",
    model=model_instance,
    input_schema=ShippingQuery,
    instruction="""
    You are a friendly, enthusiastic, and playful customer support representative for a shipping company. 🚀✨
    Answer the user's shipping query regarding rates, tracking, delivery, or returns to the best of your ability.
    The user's query is: {ShippingQuery.query}
    
    Guidelines:
    - If the user asks about shipping rates, be super playful and enthusiastic! 📦🎉 
    - If there are no specific rates provided, mock/invent some fun, placeholder rates (e.g., "Snail Mail" 🐌, "Standard Rocket" 🚀, "Instant Teleportation" ⚡).
    - Always highlight our awesome FREE shipping threshold: FREE shipping on all orders over $50! 🆓💰
    - Sprinkle in fun emojis to keep the conversation lively!
    - Keep your response helpful, concise, and professional yet highly energetic.
    """,
    mode="single_turn",
)

def decline_node():
    """Declines to answer unrelated queries politely."""
    msg = "I can only assist with shipping-related queries (such as rates, tracking, delivery, and returns). Please let me know if you have any shipping-related questions!"
    return Event(
        output=msg,
        message=msg
    )

root_agent = Workflow(
    name="customer_support_workflow",
    description="A workflow that routes shipping questions to an FAQ agent, and politely declines other questions.",
    edges=[
        ("START", store_query_node, classifier_agent, router),
        (router, {
            "SHIPPING_FAQ": prepare_faq_input,
            "DECLINE": decline_node
        }),
        (prepare_faq_input, shipping_faq_agent)
    ]
)

app = App(
    root_agent=root_agent,
    name="app",
)
