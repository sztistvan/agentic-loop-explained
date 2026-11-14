"""
Two toy tools for steps 6 and 7, with the descriptions the model will read.

The data is made up and tiny on purpose: the point is that the model cannot know it, so it has to
ask for it. Each tool has two parts:
  * a Python function that does the work, and
  * a JSON description (name, what it does, its arguments) that is sent to the model with every request.
"""
import json

ORDERS = {
    "A-1001": {"customer": "ada@example.com", "status": "delayed", "reason": "supplier stockout"},
    "A-1002": {"customer": "ada@example.com", "status": "delivered", "reason": ""},
    "B-2001": {"customer": "bob@example.com", "status": "processing", "reason": ""},
}


def find_orders(customer_email: str) -> str:
    ids = [oid for oid, o in ORDERS.items() if o["customer"] == customer_email]
    return json.dumps(ids) if ids else f"ERROR: no orders for {customer_email}"


def get_order_status(order_id: str) -> str:
    order = ORDERS.get(order_id)
    if order is None:
        # Errors are returned as ordinary text, so the model can read them and try again.
        return f"ERROR: no order {order_id!r}. Valid order ids look like: {', '.join(ORDERS)}"
    return json.dumps({"order_id": order_id, "status": order["status"], "reason": order["reason"]})


# What the model is told about the tools (this is the JSON that goes in the request's "tools" field).
TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "find_orders",
            "description": "List the order ids that belong to a customer. Use it when you only have an email address.",
            "parameters": {
                "type": "object",
                "properties": {"customer_email": {"type": "string", "description": "the customer's email"}},
                "required": ["customer_email"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": "Get the status of one order, and the reason if it is delayed.",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string", "description": "for example A-1001"}},
                "required": ["order_id"],
            },
        },
    },
]

# How a tool name from the model is turned into a function call.
FUNCTIONS = {"find_orders": find_orders, "get_order_status": get_order_status}


def run_tool(name: str, arguments_json: str) -> str:
    """Run the tool the model asked for. `arguments_json` is the JSON string the model produced."""
    if name not in FUNCTIONS:
        return f"ERROR: unknown tool {name!r}. Available: {', '.join(FUNCTIONS)}"
    try:
        return FUNCTIONS[name](**json.loads(arguments_json))
    except Exception as exc:  # bad arguments from the model: tell it, do not crash
        return f"ERROR: {type(exc).__name__}: {exc}"
