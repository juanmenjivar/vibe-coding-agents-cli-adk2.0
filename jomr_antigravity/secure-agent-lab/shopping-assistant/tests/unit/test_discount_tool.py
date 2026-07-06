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

from app.tools import DISCOUNT_CODES, redeem_discount_code


def test_redeem_discount_code_success() -> None:
    # Reset in-memory store
    DISCOUNT_CODES["WELCOME50"] = None

    # First redemption should succeed
    res = redeem_discount_code("WELCOME50", "user_1")
    assert res["status"] == "success"
    assert "successfully redeemed" in res["message"]


def test_redeem_discount_code_already_redeemed() -> None:
    # Reset and redeem once
    DISCOUNT_CODES["WELCOME50"] = "user_1"

    # Second redemption should fail
    res = redeem_discount_code("WELCOME50", "user_2")
    assert res["status"] == "error"
    assert "already been redeemed" in res["message"]


def test_redeem_discount_code_invalid_user() -> None:
    # Redeeming with unregistered user should fail
    res = redeem_discount_code("WELCOME50", "fake_user")
    assert res["status"] == "error"
    assert "not a registered user" in res["message"]


def test_redeem_discount_code_invalid_code() -> None:
    # Redeeming invalid code should fail
    res = redeem_discount_code("INVALID_CODE", "user_1")
    assert res["status"] == "error"
    assert "is invalid" in res["message"]
