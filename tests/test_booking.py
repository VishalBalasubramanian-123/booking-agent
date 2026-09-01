# Tests for the agent's system prompt and Agent construction.
from tools_lambda.tools.booking import _windows_overlap, _find_next_free_start, check_availability
from unittest.mock import patch
import pytest
from datetime import datetime, date, time, timedelta


@pytest.mark.parametrize("cand_start, cand_end, existing_start, existing_end, expected", [
    pytest.param("2026-08-27T19:00:00Z", "2026-08-27T20:30:00Z", "2026-08-27T18:00:00Z", "2026-08-27T19:30:00Z", True, id="candidate_start_inside_existing_window"),
    pytest.param("2026-08-28T15:00:00Z", "2026-08-28T16:45:00Z", "2026-08-28T15:13:45Z", "2026-08-28T15:15:00Z", True, id="existing_window_inside_candidate"),
    pytest.param("2026-08-21T13:00:00Z", "2026-08-21T14:50:00Z", "2026-08-21T15:00:00Z", "2026-08-21T16:15:00Z", False, id="no_overlap_sequential"),
])
def test_windows_overlap(cand_start, cand_end, existing_start, existing_end, expected):
    assert _windows_overlap(cand_start, cand_end, existing_start, existing_end) == expected

@pytest.mark.parametrize("bookings, expected", [
    ([
        { 
            "table_number": 4, 
            "time": datetime.fromisoformat("2026-08-28 15:00:00"), 
            "occupancy_end_time": datetime.fromisoformat("2026-08-28 16:30:00"),
        },
        {
            "table_number": 4, 
            "time": datetime.fromisoformat("2026-08-28 18:00:00"), 
            "occupancy_end_time": datetime.fromisoformat("2026-08-28 19:30:00"),
        },
        {
            "table_number": 4, 
            "time": datetime.fromisoformat("2026-08-28 20:00:00"), 
            "occupancy_end_time": datetime.fromisoformat("2026-08-28 21:30:00"),
        },
        ], 
        datetime.fromisoformat("2026-08-28 21:30:00")
    ),

    (
        [
        { 
            "table_number": 4, 
            "time": datetime.fromisoformat("2026-08-28 20:30:00"), 
            "occupancy_end_time": datetime.fromisoformat("2026-08-28 21:30:00"),
        },
        {
            "table_number": 4, 
            "time": datetime.fromisoformat("2026-08-28 21:30:00"), 
            "occupancy_end_time": datetime.fromisoformat("2026-08-28 22:30:00"),
        }
        ], 
        datetime.fromisoformat("2026-08-28 19:00:00")
    )
])
def test_find_next_free_start(bookings, expected):
    requested_start = datetime.fromisoformat("2026-08-28 19:00:00")
    occupancy_time = timedelta(minutes=90)
    query_return = bookings

    sorted_query_result = sorted(query_return, key=lambda b: b["time"])

    response = _find_next_free_start(requested_start, occupancy_time, sorted_query_result)

    assert response == expected


def test_check_availability_when_no_candidate_tables():
    with patch("tools_lambda.tools.booking.get_tables", return_value=[]):
        result = check_availability(date(2026, 8, 28), time(19, 0), party_size=4)
    assert result == "No single table fits a party of 4"

def test_check_availability_when_maintanence_window_available():
    with  patch("tools_lambda.tools.booking.get_tables", return_value=[{"table_id": 3, "table_number": 5}]), \
        patch("tools_lambda.tools.booking.get_maintenance_window", return_value=[
    {
        "unavailability_id": 2,
        "table_id": 3,
        "start_time": "2026-08-28T18:30:00",
        "end_time": "2026-08-28T20:00:00",
        "reason": "deep cleaning",
        "tables_info": {"table_number": 5},
    }
]):
        result = check_availability(date(2026, 8, 28), time(19, 0), party_size=2)
    assert result == [{
        "table": 5, 
        "available": False, 
        "reason": "deep cleaning", 
        "window": [datetime.fromisoformat("2026-08-28T18:30:00"), datetime.fromisoformat("2026-08-28T20:00:00")]
        }]

def test_check_availability_when_not_conflicting():
    with patch("tools_lambda.tools.booking.get_existing_bookings", return_value=[{
                        "table_number": 5,
                        "time":  datetime.fromisoformat("2026-08-28T18:30:00"),
                        "occupancy_end_time": datetime.fromisoformat("2026-08-28T20:00:00"),
                    }]), \
    patch("tools_lambda.tools.booking.get_tables", return_value=[{"table_id": 3, "table_number": 5}]), \
    patch("tools_lambda.tools.booking.get_maintenance_window", return_value=[]):
        result = check_availability(date(2026, 8, 28), time(20, 0), party_size=2)
    assert result == [{"table": 5, "available": True, "date": date.fromisoformat("2026-08-28"), "time": time.fromisoformat("20:00:00")}]

def test_check_availability_when_conflicting():
    with patch("tools_lambda.tools.booking.get_tables", return_value=[{"table_id": 3, "table_number": 5}]), \
    patch("tools_lambda.tools.booking.get_maintenance_window", return_value=[]), \
    patch("tools_lambda.tools.booking.get_existing_bookings", return_value=[{
                        "table_number": 5,
                        "time":  datetime.fromisoformat("2026-08-28T18:30:00"),
                        "occupancy_end_time": datetime.fromisoformat("2026-08-28T20:00:00"),
                    }]), \
    patch("tools_lambda.tools.booking.get_closing_time", return_value=datetime.fromisoformat("2026-08-28T23:00:00")):
        result = check_availability(date(2026, 8, 28), time(19, 0), party_size=2)
    assert result == [{"table": 5, "available": False, "next_available_time": datetime.fromisoformat("2026-08-28T20:00:00")}]
    