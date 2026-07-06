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

from app.tools import (
    CARTS,
    DISCOUNT_CODES,
    CheckoutRequest,
    process_cart_checkout,
)


def test_checkout_success_no_discount() -> None:
    # Set up active cart
    CARTS["cart_1"] = {"items": [{"name": "Shirt", "price": 20.0}], "status": "active"}

    request = CheckoutRequest(cart_id="cart_1", user_id="user_1")
    res = process_cart_checkout(request)

    assert res["status"] == "success"
    assert res["total_price"] == 20.0
    assert CARTS["cart_1"]["status"] == "completed"


def test_checkout_success_with_discount() -> None:
    CARTS["cart_2"] = {"items": [{"name": "Shoes", "price": 100.0}], "status": "active"}
    DISCOUNT_CODES["SUMMER20"] = None  # reset discount

    request = CheckoutRequest(
        cart_id="cart_2", user_id="user_1", discount_code="SUMMER20"
    )
    res = process_cart_checkout(request)

    assert res["status"] == "success"
    # SUMMER20 gives 20% off -> 100 - 20% = 80.0
    assert res["total_price"] == 80.0
    assert CARTS["cart_2"]["status"] == "completed"
    assert DISCOUNT_CODES["SUMMER20"] == "user_1"  # marked redeemed


def test_checkout_unregistered_user() -> None:
    CARTS["cart_3"] = {"items": [{"name": "Hat", "price": 15.0}], "status": "active"}

    request = CheckoutRequest(cart_id="cart_3", user_id="fake_user")
    res = process_cart_checkout(request)

    assert res["status"] == "error"
    assert "not a registered user" in res["message"]
    assert CARTS["cart_3"]["status"] == "active"  # cart remains active


def test_checkout_invalid_cart() -> None:
    request = CheckoutRequest(cart_id="invalid_cart", user_id="user_1")
    res = process_cart_checkout(request)

    assert res["status"] == "error"
    assert "is invalid or does not exist" in res["message"]


def test_checkout_already_completed() -> None:
    CARTS["cart_4"] = {
        "items": [{"name": "Socks", "price": 5.0}],
        "status": "completed",
    }

    request = CheckoutRequest(cart_id="cart_4", user_id="user_1")
    res = process_cart_checkout(request)

    assert res["status"] == "error"
    assert "already been checked out" in res["message"]


def test_checkout_already_redeemed_discount() -> None:
    CARTS["cart_5"] = {"items": [{"name": "Coat", "price": 200.0}], "status": "active"}
    DISCOUNT_CODES["WELCOME50"] = "user_2"  # already redeemed

    request = CheckoutRequest(
        cart_id="cart_5", user_id="user_1", discount_code="WELCOME50"
    )
    res = process_cart_checkout(request)

    assert res["status"] == "error"
    assert "already been redeemed" in res["message"]
    assert CARTS["cart_5"]["status"] == "active"  # cart remains active
