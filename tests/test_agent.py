# Tests for agent/agent.py.
#
# agent.py does real work at *import* time (_invoke_tool("get_restaurant_name"),
# _invoke_tool("create_session"), Agent(...) construction) -- so importing it
# needs boto3.client("lambda") faked out before the import runs. Every other
# service name (e.g. "bedrock-runtime", used internally by Strands) falls
# through to the real boto3.client -- that's safe since *constructing* a
# client makes no network call, only an actual invoke would.
import json
import os
from unittest.mock import patch, MagicMock

import pytest
import boto3

os.environ.setdefault("TOOLS_LAMBDA_NAME", "test-tools-lambda")

_real_boto3_client = boto3.client


def _fake_lambda_response(payload):
    body = MagicMock()
    body.read.return_value = json.dumps(payload).encode()
    return {"Payload": body}


def _lambda_invoke_side_effect(FunctionName, Payload):
    action = json.loads(Payload)["action"]
    if action == "get_restaurant_name":
        return _fake_lambda_response("Test Restaurant")
    if action == "create_session":
        return _fake_lambda_response([{"session_id": 1}])
    return _fake_lambda_response(None)


def _boto3_client_side_effect(service_name, *args, **kwargs):
    if service_name == "lambda":
        mock_lambda_client = MagicMock()
        mock_lambda_client.invoke.side_effect = _lambda_invoke_side_effect
        return mock_lambda_client
    return _real_boto3_client(service_name, *args, **kwargs)


@pytest.fixture(scope="module")
def agent_module():
    with patch("boto3.client", side_effect=_boto3_client_side_effect):
        import agent.agent as module
    return module


def test_agent_module_imports_and_builds_without_raising(agent_module):
    assert agent_module.agent is not None
    assert agent_module._session_id == 1
    assert agent_module._restaurant_name == "Test Restaurant"


def test_invoke_tool_sends_action_and_parameters(agent_module):
    fake_client = MagicMock()
    fake_client.invoke.return_value = _fake_lambda_response({"ok": True})
    with patch.object(agent_module, "_lambda_client", fake_client):
        result = agent_module._invoke_tool("some_action", foo="bar")

    sent_payload = json.loads(fake_client.invoke.call_args.kwargs["Payload"])
    assert sent_payload == {"action": "some_action", "parameters": {"foo": "bar"}}
    assert result == {"ok": True}


def test_check_availability_tool_forwards_to_invoke_tool(agent_module):
    with patch.object(agent_module, "_invoke_tool", return_value={"available": True}) as mock_invoke:
        result = agent_module.check_availability("2026-08-28", "19:00", 4, table_number=5, stay_minutes=90)
    mock_invoke.assert_called_once_with(
        "check_availability", date="2026-08-28", time="19:00", party_size=4, table_number=5, stay_minutes=90
    )
    assert result == {"available": True}


def test_reserve_table_tool_forwards_session_id(agent_module):
    with patch.object(agent_module, "_invoke_tool", return_value={"status": "confirmed"}) as mock_invoke:
        agent_module.reserve_table("2026-08-28", "19:00", 4, "John", "1234567890")
    _, kwargs = mock_invoke.call_args
    assert kwargs["session_id"] == agent_module._session_id


def test_reserve_table_starts_watcher_thread_when_pending(agent_module):
    with patch.object(agent_module, "_invoke_tool", return_value={"status": "pending", "reservation_id": 42}), \
    patch.object(agent_module.threading, "Thread") as mock_thread_cls:
        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread
        agent_module.reserve_table("2026-08-28", "19:00", 4, "John", "1234567890", allergy_info="peanuts")

    mock_thread_cls.assert_called_once_with(
        target=agent_module._watch_verification, args=(42,), daemon=True
    )
    mock_thread.start.assert_called_once()


def test_reserve_table_does_not_start_watcher_when_confirmed(agent_module):
    with patch.object(agent_module, "_invoke_tool", return_value={"status": "confirmed", "reservation_id": 42}), \
    patch.object(agent_module.threading, "Thread") as mock_thread_cls:
        agent_module.reserve_table("2026-08-28", "19:00", 4, "John", "1234567890")
    mock_thread_cls.assert_not_called()


def test_check_booking_tool_forwards_to_invoke_tool(agent_module):
    with patch.object(agent_module, "_invoke_tool", return_value={"status": "confirmed"}) as mock_invoke:
        result = agent_module.check_booking(2)
    mock_invoke.assert_called_once_with("check_booking", booking_id=2)
    assert result == {"status": "confirmed"}


def test_cancel_booking_tool_forwards_to_invoke_tool(agent_module):
    with patch.object(agent_module, "_invoke_tool", return_value={"status": "cancelled"}) as mock_invoke:
        result = agent_module.cancel_booking(2, "change of plans")
    mock_invoke.assert_called_once_with("cancel_booking", booking_id=2, reason="change of plans")
    assert result == {"status": "cancelled"}


def test_check_KB_tool_forwards_to_invoke_tool(agent_module):
    with patch.object(agent_module, "_invoke_tool", return_value=[{"content": "We open at 9am"}]) as mock_invoke:
        result = agent_module.check_KB("opening hours")
    mock_invoke.assert_called_once_with("check_KB", topic="opening hours")
    assert result == [{"content": "We open at 9am"}]


def test_watch_verification_prints_update_once_resolved(agent_module, capsys):
    with patch.object(agent_module, "_invoke_tool", return_value={"status": "confirmed"}), \
    patch.object(agent_module.time, "sleep"):
        agent_module._watch_verification(42)
    captured = capsys.readouterr()
    assert "Booking 42 is now confirmed." in captured.out


def test_watch_verification_gives_up_after_max_wait(agent_module, capsys):
    with patch.object(agent_module, "_invoke_tool", return_value={"status": "pending"}), \
    patch.object(agent_module.time, "sleep"):
        agent_module._watch_verification(42)
    captured = capsys.readouterr()
    assert "still awaiting a response" in captured.out
