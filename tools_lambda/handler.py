# Lambda entrypoint, dispatches to tools/ by action name.
import json
import time as time_module
from datetime import date, time, datetime, timedelta

from tools_lambda.tools import booking, kb
from shared import queries

ACTIONS = {
    "check_availability": booking.check_availability,
    "reserve_table": booking.reserve_table,
    "check_booking": booking.check_booking,
    "get_restaurant_name": queries.get_restaurant_name,
    "check_KB": kb.check_KB,
    "create_session": queries.create_session,
    "insert_conversation": queries.insert_conversation,
    "cancel_booking": booking.cancel_booking
}


def _json_safe(value):
    # Business-logic functions build responses using real date/time/datetime/
    # timedelta objects for their own internal logic -- this is the one
    # choke point every response passes through before crossing back over
    # the Lambda boundary, so it's the right place to make them JSON-safe
    # rather than requiring every function to remember to do it itself.
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, dict):
        return {key: _json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def handler(event, context):
    action = event["action"]
    parameters = event.get("parameters", {})

    if action not in ACTIONS:
        raise ValueError(f"Unknown action: {action}")

    started_at = time_module.perf_counter()
    result = ACTIONS[action](**parameters)
    safe_result = _json_safe(result)
    latency_ms = round((time_module.perf_counter() - started_at) * 1000, 2)

    print(json.dumps({
        "action": action,
        "parameters": parameters,
        "result": safe_result,
        "latency_ms": latency_ms,
    }, default=str))

    return safe_result
