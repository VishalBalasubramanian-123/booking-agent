# Lambda entrypoint, dispatches to tools/ by action name.
from tools_lambda.tools import booking

ACTIONS = {
    "check_availability": booking.check_availability,
    "reserve_table": booking.reserve_table,
    "check_booking": booking.check_booking,
    "verification_to_human": booking.verification_to_human,
    "decision_to_human": booking.decision_to_human,
    "get_restaurant_name": booking.get_restaurant_name,
}


def handler(event, context):
    action = event["action"]
    if action not in ACTIONS:
        raise ValueError(f"Unknown action: {action}")
    return ACTIONS[action](**event.get("parameters", {}))
