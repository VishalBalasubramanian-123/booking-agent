# Strands agent definition, deployed to AgentCore Runtime.
import json
import threading
import time
from datetime import date
from pathlib import Path
import boto3
from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from strands import Agent, tool
from strands.models import BedrockModel

from shared.config import TOOLS_LAMBDA_NAME

load_dotenv()

SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "system_prompt.md"
SYSTEM_PROMPT_TEMPLATE = SYSTEM_PROMPT_PATH.read_text()

model = BedrockModel(model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0")
# model = BedrockModel(model_id="us.amazon.nova-2-lite-v1:0")

_lambda_client = boto3.client("lambda")


def _invoke_tool(action, **parameters):
    """Invoke the tools Lambda, which dispatches to tools_lambda/tools/ by action name."""
    print(f"\n[TOOL CALL] {action} <- {parameters}")
    response = _lambda_client.invoke(
        FunctionName=TOOLS_LAMBDA_NAME,
        Payload=json.dumps({"action": action, "parameters": parameters}).encode(),
    )
    result = json.loads(response["Payload"].read())
    print(f"[TOOL RESULT] {action} -> {result}")
    return result


# Restaurant name is fetched once at startup (not an LLM-callable tool — this is
# deployment context, not something the agent should ever need to ask itself for
# mid-conversation) and baked into the system prompt before the Agent is built.
_restaurant_name = _invoke_tool("get_restaurant_name")

# Today's date, same reasoning — the model has no access to the real system
# clock on its own, so without this it has no way to resolve a guest-given
# date that omits a year (see error_log.md #21).
_today = date.today().strftime("%A, %B %-d, %Y")

SYSTEM_PROMPT = SYSTEM_PROMPT_TEMPLATE.format(restaurant_name=_restaurant_name, today=_today)

# One session per CLI run, same reasoning as _restaurant_name above — not
# something the agent should ever ask itself for mid-conversation.
_session = _invoke_tool("create_session")
_session_id = _session[0]["session_id"]


def _watch_verification(reservation_id):
    """Runs in a background thread: polls until the owner resolves the
    escalation (or the hold window runs out) and prints the outcome.
    Display only — does NOT enforce the fail-closed decline itself; that's
    the hold-expiry sweep's job, independent of whether this is running."""
    max_wait_seconds = 5 * 60  # matches the booking hold window
    poll_interval = 5
    waited = 0

    while waited < max_wait_seconds:
        time.sleep(poll_interval)
        waited += poll_interval
        booking = _invoke_tool("check_booking", booking_id=reservation_id)
        if booking and booking.get("status") != "pending":
            print(f"\n[Update] Booking {reservation_id} is now {booking['status']}.")
            return

    print(f"\n[Update] Booking {reservation_id} is still awaiting a response after {max_wait_seconds // 60} minutes.")


@tool
def check_availability(date: str, time: str, party_size: int, table_number: int | None = None, stay_minutes: int | None = None) -> dict:
    """Check whether a table is available for a given date, time, and party size.

    The response may include pre-formatted "*_display" fields (e.g.
    next_available_time_display, date_display, alternatives[].display) —
    always use those exact strings when telling the guest a date/time.
    Never compute or reformat a date/time yourself from the raw fields.

    Args:
        date: Reservation date, YYYY-MM-DD.
        time: Reservation time, HH:MM (24h).
        party_size: Number of guests.
        table_number: Specific table to check, if the guest requested one.
    """
    return _invoke_tool(
        "check_availability", date=date, time=time, party_size=party_size, table_number=table_number, stay_minutes=stay_minutes
    )


@tool
def reserve_table(
    date: str,
    time: str,
    party_size: int,
    name: str,
    phone: str,
    email: str | None = None,
    allergy_info: str = "",
    table_number: int | None = None,
) -> dict:
    """Reserve a table for a guest.

    The response includes a "status_message" field — use it verbatim as your
    opening/confirmation sentence. Do not independently compose your own
    "confirmed"/"success" framing based on the tool call having succeeded;
    the reservation can come back "pending" (awaiting review) even when the
    call itself completes without error, and status_message already reflects
    that correctly.

    Args:
        date: Reservation date, YYYY-MM-DD.
        time: Reservation time, HH:MM (24h).
        party_size: Number of guests.
        name: Guest's name.
        phone: Guest's phone number.
        email: Guest's email address.
        allergy_info: Any allergy or safety concern the guest mentioned, if any.
        table_number: Specific table requested, if any.
    """
    result = _invoke_tool(
        "reserve_table",
        date=date,
        time=time,
        party_size=party_size,
        name=name,
        phone=phone,
        email=email,
        allergy_info=allergy_info,
        table_number=table_number,
        session_id=_session_id,
    )
    if isinstance(result, dict) and result.get("status") == "pending":
        threading.Thread(target=_watch_verification, args=(result["reservation_id"],), daemon=True).start()
    return result


@tool
def check_booking(booking_id: int) -> dict:
    """Look up an existing booking by its ID.

    The response includes pre-formatted "*_display" fields (date_display,
    time_display, total_time_display) — always use those exact strings when
    telling the guest a date/time/duration. Never compute or reformat one
    yourself from the raw fields.

    Args:
        booking_id: The booking's unique identifier.
    """
    return _invoke_tool("check_booking", booking_id=booking_id)

@tool
def cancel_booking(booking_id: int, reason: str = "No reason given"):
    """cancels the table booking for the user

    Args:
        booking_id: The booking's unique identifier. 
        reason: The reason for cancelling the booking
    """
    return _invoke_tool("cancel_booking", booking_id=booking_id, reason=reason)

# @tool
# def decision_to_human(booking_id: str, decision: str) -> dict:
#     """Record a human's decision on an escalated booking.

#     Args:
#         booking_id: The booking's unique identifier.
#         decision: The human's decision (e.g. approve, decline).
#     """
#     return _invoke_tool("decision_to_human", booking_id=booking_id, decision=decision)

@tool
def check_KB(topic: str) -> list[dict]:
    """Check the KB if the information on the user query is present.
    
    Args:
        topic: The query asked by the users
    """
    return _invoke_tool("check_KB", topic=topic)



agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[check_availability, reserve_table, check_booking, check_KB, cancel_booking],
    callback_handler=None,
)

if __name__ == "__main__":
    session = PromptSession()
    with patch_stdout():
        while True:
            user_input = session.prompt(" \n You: ")
            print(f" \n [GUEST INPUT] {user_input!r} \n")
            _invoke_tool("insert_conversation", session_id=_session_id, message=user_input, by_who="user")
            if user_input.strip().lower() == "exit":
                break
            response = agent(user_input)
            print(f"\n [MODEL REPLY] {str(response)!r} \n")
            _invoke_tool("insert_conversation", session_id=_session_id, message=str(response), by_who="assistant")
            print(response)
