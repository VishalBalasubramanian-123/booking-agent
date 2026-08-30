# Tests for the agent's system prompt and Agent construction.
from tools_lambda.tools.booking import _windows_overlap, _find_next_free_start, check_availability
from unittest.mock import patch
import pytest
from datetime import datetime, date, time, timedelta


@pytest.mark.parametrize("cand_start, cand_end, existing_start, existing_end, expected", [
    ("2026-08-27T19:00:00Z", "2026-08-27T20:30:00Z", "2026-08-27T18:00:00Z", "2026-08-27T19:30:00Z", True),
    ("2026-08-28T15:00:00Z", "2026-08-28T16:45:00Z", "2026-08-28T15:13:45Z", "2026-08-28T15:15:00Z", True),
    ("2026-08-21T13:00:00Z", "2026-08-21T14:50:00Z", "2026-08-21T15:00:00Z", "2026-08-21T16:15:00Z", False),
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



def test_check_availability():
    pass