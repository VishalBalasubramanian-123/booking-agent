# Tests for dashboard/app.py -- the owner-facing CLI stand-in.
from unittest.mock import patch

from dashboard.app import main


def test_main_prints_message_when_nothing_pending(capsys):
    with patch("dashboard.app.get_pending_escalations", return_value=[]):
        main()
    captured = capsys.readouterr()
    assert "No pending verifications." in captured.out


def test_main_resolves_a_single_pending_item():
    pending = [
        {
            "reservation_id": 42,
            "reservation": {"party_size": 4, "date": "2026-08-28", "time": "19:00:00", "allergy_info": "Peanut allergy"},
        }
    ]
    with patch("dashboard.app.get_pending_escalations", return_value=pending), \
    patch("builtins.input", side_effect=["yes", "kitchen confirmed safe"]), \
    patch("dashboard.app.resolve_verification", return_value={"status": "confirmed"}) as mock_resolve:
        main()
    mock_resolve.assert_called_once_with(42, "yes", "kitchen confirmed safe")


def test_main_walks_through_multiple_pending_items_in_order():
    pending = [
        {"reservation_id": 1, "reservation": {"party_size": 2, "date": "2026-08-28", "time": "18:00:00", "allergy_info": "Shellfish"}},
        {"reservation_id": 2, "reservation": {"party_size": 3, "date": "2026-08-28", "time": "19:00:00", "allergy_info": "Nuts"}},
    ]
    with patch("dashboard.app.get_pending_escalations", return_value=pending), \
    patch("builtins.input", side_effect=["yes", "", "no", "kitchen can't guarantee"]), \
    patch("dashboard.app.resolve_verification", return_value={"status": "confirmed"}) as mock_resolve:
        main()
    assert mock_resolve.call_count == 2
    mock_resolve.assert_any_call(1, "yes", "")
    mock_resolve.assert_any_call(2, "no", "kitchen can't guarantee")


def test_main_prints_allergy_info_for_owner_to_read(capsys):
    pending = [
        {
            "reservation_id": 42,
            "reservation": {"party_size": 4, "date": "2026-08-28", "time": "19:00:00", "allergy_info": "Severe peanut allergy"},
        }
    ]
    with patch("dashboard.app.get_pending_escalations", return_value=pending), \
    patch("builtins.input", side_effect=["yes", ""]), \
    patch("dashboard.app.resolve_verification", return_value={"status": "confirmed"}):
        main()
    captured = capsys.readouterr()
    assert "Severe peanut allergy" in captured.out
    assert "Booking 42" in captured.out
