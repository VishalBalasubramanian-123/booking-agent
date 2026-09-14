# Lambda entrypoint, dispatches to tools/ by action name.
from tools_lambda.tools import booking, kb
from shared import queries

ACTIONS = {
    "check_availability": booking.check_availability,
    "reserve_table": booking.reserve_table,
    "check_booking": booking.check_booking,
    "get_restaurant_name": queries.get_restaurant_name,
    "check_KB": kb.check_KB,
    "create_session": queries.create_session
}


def handler(event, context):
    action = event["action"]
    if action not in ACTIONS:
        raise ValueError(f"Unknown action: {action}")
    return ACTIONS[action](**event.get("parameters", {}))
