# ruff: noqa
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

from functools import cached_property
from google import genai
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

from app.tools import process_cart_checkout, redeem_discount_code


class CustomGemini(Gemini):
    @cached_property
    def api_client(self) -> genai.Client:
        api_key = os.environ.get("GEMINI_API_KEY", "MOCK_DEVELOPMENT_KEY")
        return genai.Client(api_key=api_key)


root_agent = Agent(
    name="root_agent",
    model=CustomGemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are an AI shopping assistant for a retail store. "
        "Help customers with their shopping questions, assist them with redeeming discount codes, "
        "and help them checkout their carts. "
        "To redeem a discount code, you MUST use the redeem_discount_code tool. "
        "To checkout a cart, you MUST use the process_cart_checkout tool. "
        "Ask the customer for their registered user ID if they have not provided it yet, as it is required to redeem codes or checkout."
    ),
    tools=[redeem_discount_code, process_cart_checkout],
)

app = App(
    root_agent=root_agent,
    name="app",
)
