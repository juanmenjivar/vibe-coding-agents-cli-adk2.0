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

from pydantic import BaseModel, Field

# In-memory store for mock registered users
REGISTERED_USERS = {"user_1", "user_2", "user_3", "customer_123", "vip_customer"}

# In-memory store for valid discount codes and their redemption status
# Maps discount code -> user_id of the redeemer (None if not yet redeemed)
DISCOUNT_CODES = {
    "WELCOME50": None,
    "SUMMER20": None,
}

# In-memory store for shopping carts
CARTS = {}


class CheckoutRequest(BaseModel):
    cart_id: str = Field(description="The unique identifier of the shopping cart.")
    discount_code: str | None = Field(
        default=None, description="Optional discount code to apply."
    )
    user_id: str = Field(description="The registered user ID of the customer.")


def redeem_discount_code(code: str, user_id: str) -> dict:
    """Redeems a single-use discount code for a registered user.

    Args:
        code: The discount code to redeem (e.g., WELCOME50, SUMMER20).
        user_id: The registered user ID.

    Returns:
        dict: A dictionary containing the status and a descriptive message.
    """
    normalized_code = code.strip().upper()

    if user_id not in REGISTERED_USERS:
        return {
            "status": "error",
            "message": f"User ID '{user_id}' is not a registered user. A registered user ID is required to redeem discount codes.",
        }

    if normalized_code not in DISCOUNT_CODES:
        return {
            "status": "error",
            "message": f"Discount code '{code}' is invalid. Please check the code and try again.",
        }

    redeemed_by = DISCOUNT_CODES[normalized_code]
    if redeemed_by is not None:
        return {
            "status": "error",
            "message": f"Discount code '{normalized_code}' has already been redeemed by user '{redeemed_by}'.",
        }

    # Mark as redeemed
    DISCOUNT_CODES[normalized_code] = user_id
    return {
        "status": "success",
        "message": f"Discount code '{normalized_code}' successfully redeemed for user '{user_id}'!",
    }


def process_cart_checkout(request: CheckoutRequest) -> dict:
    """Processes checkout for a shopping cart, applying any discount codes.

    Args:
        request: The checkout request details.

    Returns:
        dict: A dictionary containing the status, total price, and a message.
    """
    user_id = request.user_id
    cart_id = request.cart_id
    discount_code = request.discount_code

    if user_id not in REGISTERED_USERS:
        return {
            "status": "error",
            "message": f"User ID '{user_id}' is not a registered user. A registered user ID is required to process checkout.",
        }

    if cart_id not in CARTS:
        return {
            "status": "error",
            "message": f"Cart ID '{cart_id}' is invalid or does not exist.",
        }

    cart = CARTS[cart_id]
    if cart.get("status") == "completed":
        return {
            "status": "error",
            "message": f"Cart ID '{cart_id}' has already been checked out.",
        }

    # Calculate total price of items in the cart
    items = cart.get("items", [])
    subtotal = sum(item.get("price", 0.0) for item in items)
    discount_amount = 0.0

    if discount_code:
        normalized_code = discount_code.strip().upper()
        if normalized_code not in DISCOUNT_CODES:
            return {
                "status": "error",
                "message": f"Discount code '{discount_code}' is invalid.",
            }

        redeemed_by = DISCOUNT_CODES[normalized_code]
        if redeemed_by is not None:
            return {
                "status": "error",
                "message": f"Discount code '{normalized_code}' has already been redeemed by user '{redeemed_by}'.",
            }

        # Apply discount (e.g. WELCOME50 is 50%, SUMMER20 is 20%)
        if normalized_code == "WELCOME50":
            discount_amount = subtotal * 0.50
        elif normalized_code == "SUMMER20":
            discount_amount = subtotal * 0.20
        else:
            discount_amount = 0.0

        # Mark code as redeemed
        DISCOUNT_CODES[normalized_code] = user_id

    total_price = max(0.0, subtotal - discount_amount)
    cart["status"] = "completed"

    return {
        "status": "success",
        "cart_id": cart_id,
        "subtotal": subtotal,
        "discount_applied": discount_amount,
        "total_price": total_price,
        "message": f"Checkout successful! Your order has been processed. Total charged: ${total_price:.2f}.",
    }
