"""Order creation and cancellation."""
from decimal import Decimal
from auth import authenticate, require_admin


def calculate_total(items: list[dict]) -> Decimal:
    """Calculate an order total from unit prices and positive quantities."""
    total = Decimal("0.00")
    for item in items:
        if item["quantity"] <= 0:
            raise ValueError("Quantity must be positive")
        total += Decimal(str(item["price"])) * item["quantity"]
    return total


def create_order(api_key: str, users: dict, items: list[dict], orders: dict) -> dict:
    """Authenticate the customer before creating an order."""
    user = authenticate(api_key, users)
    order = {"customer": user.id, "total": calculate_total(items), "status": "pending"}
    order_id = str(len(orders) + 1)
    orders[order_id] = order
    return {"id": order_id, **order}


def cancel_order(api_key: str, users: dict, order_id: str, orders: dict) -> None:
    """Require an admin to cancel an existing pending order."""
    user = authenticate(api_key, users)
    require_admin(user)
    order = orders[order_id]
    if order["status"] != "pending":
        raise ValueError("Only pending orders can be cancelled")
    order["status"] = "cancelled"
