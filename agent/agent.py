# Strands agent definition, deployed to AgentCore Runtime.
import json
from pathlib import Path

import boto3
from dotenv import load_dotenv
from strands import Agent, tool
from strands.models import BedrockModel

from shared.config import TOOLS_LAMBDA_NAME

load_dotenv()

SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "system_prompt.md"
SYSTEM_PROMPT = SYSTEM_PROMPT_PATH.read_text()

# model = BedrockModel(model_id="anthropic.claude-haiku-4-5-20251001-v1:0")amazon.nova-2-lite-v1:0
model = BedrockModel(model_id="us.amazon.nova-2-lite-v1:0")

_lambda_client = boto3.client("lambda")


def _invoke_tool(action, **parameters):
    """Invoke the tools Lambda, which dispatches to tools_lambda/tools/ by action name."""
    response = _lambda_client.invoke(
        FunctionName=TOOLS_LAMBDA_NAME,
        Payload=json.dumps({"action": action, "parameters": parameters}).encode(),
    )
    return json.loads(response["Payload"].read())


@tool
def check_availability(date: str, time: str, party_size: int, table_number: int | None = None) -> dict:
    """Check whether a table is available for a given date, time, and party size.

    Args:
        date: Reservation date, YYYY-MM-DD.
        time: Reservation time, HH:MM (24h).
        party_size: Number of guests.
        table_number: Specific table to check, if the guest requested one.
    """
    return _invoke_tool(
        "check_availability", date=date, time=time, party_size=party_size, table_number=table_number
    )


@tool
def reserve_table(
    date: str, time: str, party_size: int, name: str, phone: str, email: str, table_number: int | None = None
) -> dict:
    """Reserve a table for a guest.

    Args:
        date: Reservation date, YYYY-MM-DD.
        time: Reservation time, HH:MM (24h).
        party_size: Number of guests.
        name: Guest's name.
        phone: Guest's phone number.
        email: Guest's email address.
        table_number: Specific table requested, if any.
    """
    return _invoke_tool(
        "reserve_table",
        date=date,
        time=time,
        party_size=party_size,
        name=name,
        phone=phone,
        email=email,
        table_number=table_number,
    )


@tool
def check_booking(booking_id: str) -> dict:
    """Look up an existing booking by its ID.

    Args:
        booking_id: The booking's unique identifier.
    """
    return _invoke_tool("check_booking", booking_id=booking_id)


@tool
def verification_to_human(booking_id: str, reason: str) -> dict:
    """Escalate a booking to a human for verification.

    Args:
        booking_id: The booking's unique identifier.
        reason: Why the booking needs human verification.
    """
    return _invoke_tool("verification_to_human", booking_id=booking_id, reason=reason)


@tool
def decision_to_human(booking_id: str, decision: str) -> dict:
    """Record a human's decision on an escalated booking.

    Args:
        booking_id: The booking's unique identifier.
        decision: The human's decision (e.g. approve, decline).
    """
    return _invoke_tool("decision_to_human", booking_id=booking_id, decision=decision)


agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[check_availability, reserve_table, check_booking, verification_to_human, decision_to_human],
    callback_handler=None,
)


if __name__ == "__main__":
    while True:
        user_input = input("You: ")
        if user_input.strip().lower() == "exit":
            break
        response = agent(user_input)
        print(response)
