# Tests for tools_lambda/handler.py's action dispatch.
from unittest.mock import patch, Mock

import pytest

from tools_lambda.handler import handler


def test_handler_dispatches_to_registered_action_with_parameters():
    mock_action = Mock(return_value={"status": "confirmed"})
    with patch.dict("tools_lambda.handler.ACTIONS", {"check_booking": mock_action}):
        result = handler({"action": "check_booking", "parameters": {"booking_id": 2}}, None)
    mock_action.assert_called_once_with(booking_id=2)
    assert result == {"status": "confirmed"}


def test_handler_works_with_no_parameters_key():
    mock_action = Mock(return_value=[{"session_id": 1}])
    with patch.dict("tools_lambda.handler.ACTIONS", {"create_session": mock_action}):
        result = handler({"action": "create_session"}, None)
    mock_action.assert_called_once_with()
    assert result == [{"session_id": 1}]


def test_handler_raises_on_unknown_action():
    with pytest.raises(ValueError, match="Unknown action: not_a_real_action"):
        handler({"action": "not_a_real_action", "parameters": {}}, None)


def test_handler_every_registered_action_is_a_real_attribute():
    # Guards against the earlier class of bug where an ACTIONS entry pointed
    # at a name that had been removed/renamed/commented out (e.g. the old
    # decision_to_human) -- that only surfaces as an AttributeError at import
    # time, breaking every action, not just the broken one.
    from tools_lambda.handler import ACTIONS
    assert ACTIONS  # non-empty
    for action_name, fn in ACTIONS.items():
        assert callable(fn), f"{action_name} is not callable"
