# Tests for scheduler_lambda/sweep.py and its Lambda handler.
from unittest.mock import patch

from scheduler_lambda.sweep import decline_expired_reservations
from scheduler_lambda.handler import handler


def test_decline_expired_reservations_declines_each_expired_booking():
    expired = [
        {"reservation_id": 1, "session_id": 10},
        {"reservation_id": 2, "session_id": 20},
    ]
    with patch("scheduler_lambda.sweep.get_expired_pending_reservations", return_value=expired), \
    patch("scheduler_lambda.sweep.update_status", side_effect=[
        [{"reservation_id": 1, "session_id": 10, "confirmed_declined": "declined"}],
        [{"reservation_id": 2, "session_id": 20, "confirmed_declined": "declined"}],
    ]) as mock_update_status:
        result = decline_expired_reservations()

    assert mock_update_status.call_count == 2
    mock_update_status.assert_any_call(10, 1, "declined", "No response from the owner within the hold window")
    mock_update_status.assert_any_call(20, 2, "declined", "No response from the owner within the hold window")
    assert result == [
        {"reservation_id": 1, "session_id": 10, "confirmed_declined": "declined"},
        {"reservation_id": 2, "session_id": 20, "confirmed_declined": "declined"},
    ]


def test_decline_expired_reservations_when_nothing_expired():
    with patch("scheduler_lambda.sweep.get_expired_pending_reservations", return_value=[]), \
    patch("scheduler_lambda.sweep.update_status") as mock_update_status:
        result = decline_expired_reservations()
    mock_update_status.assert_not_called()
    assert result == []


def test_handler_returns_declined_summary():
    with patch("scheduler_lambda.handler.decline_expired_reservations", return_value=[{"reservation_id": 1}]):
        result = handler({}, None)
    assert result == {"declined_count": 1, "declined": [{"reservation_id": 1}]}


def test_handler_returns_zero_when_nothing_declined():
    with patch("scheduler_lambda.handler.decline_expired_reservations", return_value=[]):
        result = handler({}, None)
    assert result == {"declined_count": 0, "declined": []}
