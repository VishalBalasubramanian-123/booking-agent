# Tests for tools_lambda/handler.py's action dispatch.
from datetime import date, time, datetime, timedelta
from unittest.mock import patch, Mock

import pytest

from tools_lambda.handler import handler, _json_safe


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


def test_json_safe_converts_date_time_datetime():
    assert _json_safe(date(2026, 8, 28)) == "2026-08-28"
    assert _json_safe(time(19, 0)) == "19:00:00"
    assert _json_safe(datetime(2026, 8, 28, 19, 0)) == "2026-08-28T19:00:00"


def test_json_safe_converts_timedelta_to_seconds():
    assert _json_safe(timedelta(minutes=90)) == 5400.0


def test_json_safe_recurses_into_nested_dicts_and_lists():
    value = {
        "table": 5,
        "available": True,
        "date": date(2026, 8, 28),
        "alternatives": [(date(2026, 8, 29), datetime(2026, 8, 29, 21, 0))],
    }
    assert _json_safe(value) == {
        "table": 5,
        "available": True,
        "date": "2026-08-28",
        "alternatives": [["2026-08-29", "2026-08-29T21:00:00"]],
    }


def test_json_safe_leaves_plain_values_untouched():
    assert _json_safe({"a": 1, "b": "text", "c": None, "d": True}) == {"a": 1, "b": "text", "c": None, "d": True}


def test_handler_applies_json_safe_to_action_result():
    mock_action = Mock(return_value={"date": date(2026, 8, 28), "total_time": timedelta(minutes=90)})
    with patch.dict("tools_lambda.handler.ACTIONS", {"check_availability": mock_action}):
        result = handler({"action": "check_availability", "parameters": {}}, None)
    assert result == {"date": "2026-08-28", "total_time": 5400.0}
