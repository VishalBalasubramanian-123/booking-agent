# Tests for the agent's system prompt and Agent construction.
from tools_lambda.tools.booking import (
    _windows_overlap,
    _find_next_free_start,
    _to_date,
    _to_time,
    check_availability,
    reserve_table,
    check_booking,
    verification_to_human,
    resolve_verification,
    cancel_booking,
    _bucket_gate,
)
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


def test_to_date_converts_string():
    assert _to_date("2026-08-28") == date(2026, 8, 28)


def test_to_date_passes_through_date_object():
    d = date(2026, 8, 28)
    assert _to_date(d) is d


def test_to_time_converts_string():
    assert _to_time("19:00:00") == time(19, 0, 0)


def test_to_time_passes_through_time_object():
    t = time(19, 0, 0)
    assert _to_time(t) is t


def test_check_availability_when_no_candidate_tables():
    with patch("tools_lambda.tools.booking.get_tables", return_value=[]):
        result = check_availability(date(2026, 8, 28), time(19, 0), party_size=4)
    assert result == ["No single table fits a party of 4"]

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



def fake_get_existing_bookings(table_id, requested_date):
    if requested_date == date(2026, 8, 28):
        return [{
            "table_number": 5,
            "time": datetime.fromisoformat("2026-08-28T21:00:00"),
            "occupancy_end_time": datetime.fromisoformat("2026-08-28T22:00:00"),
        }]
    return []


def fake_get_closing_time(requested_date):
    if requested_date == date(2026, 8, 28):
        return datetime.fromisoformat("2026-08-28T22:00:00")
    if requested_date == date(2026, 8, 29):
        return datetime.fromisoformat("2026-08-29T23:00:00")
    return datetime.fromisoformat("2026-08-30T23:00:00")


def test_check_availability_when_alternatives_found_next_two_days():
    with patch("tools_lambda.tools.booking.get_tables", return_value=[{"table_id": 3, "table_number": 5}]), \
    patch("tools_lambda.tools.booking.get_maintenance_window", return_value=[]), \
    patch("tools_lambda.tools.booking.get_existing_bookings", side_effect=fake_get_existing_bookings), \
    patch("tools_lambda.tools.booking.get_closing_time", side_effect=fake_get_closing_time):
        result = check_availability(date(2026, 8, 28), time(21, 0), party_size=2)
    assert result == [{
        "table": 5,
        "available": False,
        "alternatives": [
            (date(2026, 8, 29), datetime.fromisoformat("2026-08-29T21:00:00")),
            (date(2026, 8, 30), datetime.fromisoformat("2026-08-30T21:00:00")),
        ],
    }]

def fake_get_existing_bookings_noalt(table_id, requested_date):
    if requested_date == date(2026, 8, 28):
        return [{
            "table_number": 5,
            "time": datetime.fromisoformat("2026-08-28T21:00:00"),
            "occupancy_end_time": datetime.fromisoformat("2026-08-28T22:00:00"),
        }]
    return []


def fake_get_closing_time_noalt(requested_date):
    if requested_date == date(2026, 8, 28):
        return datetime.fromisoformat("2026-08-28T22:00:00")
    if requested_date == date(2026, 8, 29):
        return datetime.fromisoformat("2026-08-29T22:00:00")
    return datetime.fromisoformat("2026-08-30T22:00:00")

def test_check_availability_when_no_alternatives():
    with patch("tools_lambda.tools.booking.get_tables", return_value=[{"table_id": 3, "table_number": 5}]), \
    patch("tools_lambda.tools.booking.get_maintenance_window", return_value=[]), \
    patch("tools_lambda.tools.booking.get_existing_bookings", side_effect=fake_get_existing_bookings_noalt), \
    patch("tools_lambda.tools.booking.get_closing_time", side_effect=fake_get_closing_time_noalt):
        result = check_availability(date(2026, 8, 28), time(21, 0), party_size=2)
    assert result == [{
        "table": 5,
        "available": False,
        "alternatives": [],
    }]

def fake_get_existing_bookings_step6(table_id, requested_date):
    if table_id == 3:  # table 5 (requested): no bookings at all -> available
        return []
    if table_id == 7:  # table 8: conflicts today, but a same-day slot fits before closing
        if requested_date == date(2026, 8, 28):
            return [{
                "table_number": 8,
                "time": datetime.fromisoformat("2026-08-28T20:30:00"),
                "occupancy_end_time": datetime.fromisoformat("2026-08-28T22:00:00"),
            }]
        return []
    if table_id == 9:  # table 12: conflicts today, next slot doesn't fit -> lookahead finds alternatives
        if requested_date == date(2026, 8, 28):
            return [{
                "table_number": 12,
                "time": datetime.fromisoformat("2026-08-28T21:00:00"),
                "occupancy_end_time": datetime.fromisoformat("2026-08-28T23:00:00"),
            }]
        return []  # Aug 29/30 wide open


def fake_get_closing_time_step6(requested_date):
    # restaurant-wide closing time -- same for every table on a given date
    if requested_date == date(2026, 8, 28):
        return datetime.fromisoformat("2026-08-28T23:30:00")
    if requested_date == date(2026, 8, 29):
        return datetime.fromisoformat("2026-08-29T23:00:00")
    return datetime.fromisoformat("2026-08-30T23:00:00")


def test_check_availability_when_table_given():
    with patch("tools_lambda.tools.booking.get_tables", return_value=[
            {"table_id": 3, "table_number": 5},
            {"table_id": 7, "table_number": 8},
            {"table_id": 9, "table_number": 12},
        ]), \
    patch("tools_lambda.tools.booking.get_maintenance_window", return_value=[]), \
    patch("tools_lambda.tools.booking.get_existing_bookings", side_effect=fake_get_existing_bookings_step6), \
    patch("tools_lambda.tools.booking.get_closing_time", side_effect=fake_get_closing_time_step6):
        result = check_availability(date(2026, 8, 28), time(21, 0), table_number=5, party_size=2)
    assert result == [{
        "requested_table": {
            "table": 5,
            "available": True,
            "date": date(2026, 8, 28),
            "time": time(21, 0),
        },
        "alternative_tables": [
            {
                "table": 8,
                "available": False,
                "next_available_time": datetime.fromisoformat("2026-08-28T22:00:00"),
            },
        ],
    }]

def test_reserve_table_when_no_name_and_no_phone():
    result = reserve_table(date(2026, 8, 28), time(19, 0), party_size=2, name="", allergy_info="", phone="", email=None, table_number=5, session_id=1)
    assert result == "Please provide your name and phone number"


def test_reserve_table_when_no_name():
    result = reserve_table(date(2026, 8, 28), time(19, 0), party_size=2, name="", allergy_info="", phone="1234567890", email=None, table_number=5, session_id=1)
    assert result == "Please provide your name"


def test_reserve_table_when_no_phone():
    result = reserve_table(date(2026, 8, 28), time(19, 0), party_size=2, name="John", allergy_info="", phone="", email=None, table_number=5, session_id=1)
    assert result == "Please provide your phone number"


def test_reserve_table_when_table_not_found():
    with patch("tools_lambda.tools.booking.get_table_id", return_value=None):
        result = reserve_table(date(2026, 8, 28), time(19, 0), party_size=2, name="John", allergy_info="", phone="1234567890", email=None, table_number=99, session_id=1)
    assert result == "Please choose one of the available tables first."


def test_reserve_table_new_customer_no_allergy_confirms():
    with patch("tools_lambda.tools.booking.get_table_id", return_value=3), \
    patch("tools_lambda.tools.booking.get_customer", return_value=[]), \
    patch("tools_lambda.tools.booking.insert_customer") as mock_insert_customer, \
    patch("tools_lambda.tools.booking.book_table", return_value=[{"reservation_id": 10, "date": "2026-08-28", "time": "19:00:00", "party_size": 2}]), \
    patch("tools_lambda.tools.booking.link_reservation_to_table") as mock_link, \
    patch("tools_lambda.tools.booking.update_status", return_value=[{"confirmed_declined": "confirmed"}]) as mock_update_status:
        result = reserve_table(date(2026, 8, 28), time(19, 0), party_size=2, name="John", allergy_info="", phone="1234567890", email=None, table_number=5, session_id=1)

    mock_insert_customer.assert_called_once_with("John", "1234567890", None)
    mock_link.assert_called_once_with(10, 3)
    mock_update_status.assert_called_once_with(1, 10, "confirmed", "No allergy or safety concern noted")
    assert result == {
        "session_id": 1,
        "reservation_id": 10,
        "date": "2026-08-28",
        "time": "19:00:00",
        "party_size": 2,
        "status": "confirmed",
    }


def test_reserve_table_existing_customer_skips_insert():
    with patch("tools_lambda.tools.booking.get_table_id", return_value=3), \
    patch("tools_lambda.tools.booking.get_customer", return_value=[{"customer_id": 1, "name": "John", "phone": "1234567890"}]), \
    patch("tools_lambda.tools.booking.insert_customer") as mock_insert_customer, \
    patch("tools_lambda.tools.booking.book_table", return_value=[{"reservation_id": 10, "date": "2026-08-28", "time": "19:00:00", "party_size": 2}]), \
    patch("tools_lambda.tools.booking.link_reservation_to_table"), \
    patch("tools_lambda.tools.booking.update_status", return_value=[{"confirmed_declined": "confirmed"}]):
        reserve_table(date(2026, 8, 28), time(19, 0), party_size=2, name="John", allergy_info="", phone="1234567890", email=None, table_number=5, session_id=1)

    mock_insert_customer.assert_not_called()


def test_reserve_table_with_allergy_goes_pending():
    with patch("tools_lambda.tools.booking.get_table_id", return_value=3), \
    patch("tools_lambda.tools.booking.get_customer", return_value=[{"customer_id": 1}]), \
    patch("tools_lambda.tools.booking.book_table", return_value=[{"reservation_id": 10, "date": "2026-08-28", "time": "19:00:00", "party_size": 2}]), \
    patch("tools_lambda.tools.booking.link_reservation_to_table"), \
    patch("tools_lambda.tools.booking.verification_to_human") as mock_verification:
        result = reserve_table(date(2026, 8, 28), time(19, 0), party_size=2, name="John", allergy_info="peanut allergy", phone="1234567890", email=None, table_number=5, session_id=1)

    mock_verification.assert_called_once_with(10, 1, "verification")
    assert result == {
        "session_id": 1,
        "reservation_id": 10,
        "date": "2026-08-28",
        "time": "19:00:00",
        "party_size": 2,
        "status": "pending",
    }


def test_check_booking_when_records_present():
    with patch("tools_lambda.tools.booking.get_booking_status", return_value=[{"session_id": 1, "reservation_id": 2, "confirmed_declined": "pending", "party_size": 4, "date": "2026-08-28", "time": "12:00:00", "allergy_info": "Peanut allergy", "occupancy_end_time": "2026-08-28T13:30:00"}]):
        result = check_booking(2)
    assert result == {
            "session_id": 1,
            "status": "pending",
            "party": 4,
            "date": date.fromisoformat("2026-08-28"),
            "time": time.fromisoformat("12:00:00"),
            "allergy_information": "Peanut allergy",
            "total_time": datetime.fromisoformat("2026-08-28T13:30:00") - datetime.combine(date.fromisoformat("2026-08-28"), time.fromisoformat("12:00:00"))
        }

def test_check_booking_when_no_records():
    with patch("tools_lambda.tools.booking.get_booking_status", return_value=[]):
        result = check_booking(2)
    assert result == None

def test_verification_to_human_inserts_escalation():
    with patch("tools_lambda.tools.booking.insert_escalation") as mock_insert:
        result = verification_to_human(10, 1, "verification")
    mock_insert.assert_called_once_with(10, 1, "verification")
    assert result == "Please wait a moment, checking with the team for confirmation"


def test_resolve_verification_booking_not_found():
    with patch("tools_lambda.tools.booking.get_booking_status", return_value=[]):
        result = resolve_verification(2, "yes", "")
    assert result == "Booking not found."


def test_resolve_verification_already_resolved():
    with patch("tools_lambda.tools.booking.get_booking_status", return_value=[{"session_id": 1, "reservation_id": 2, "confirmed_declined": "pending", "party_size": 4, "date": "2026-08-28", "time": "12:00:00", "allergy_info": "Peanut allergy", "occupancy_end_time": "2026-08-28T13:30:00"}]), \
    patch("tools_lambda.tools.booking.update_escalation_answer", return_value=[]):
        result = resolve_verification(2, "yes", "")
    assert result == "This booking has already been resolved."


def test_resolve_verification_yes_with_reason():
    with patch("tools_lambda.tools.booking.get_booking_status", return_value=[{"session_id": 1, "reservation_id": 2, "confirmed_declined": "pending", "party_size": 4, "date": "2026-08-28", "time": "12:00:00", "allergy_info": "Peanut allergy", "occupancy_end_time": "2026-08-28T13:30:00"}]), \
    patch("tools_lambda.tools.booking.update_escalation_answer", return_value=[{"owners_answer": "yes"}]), \
    patch("tools_lambda.tools.booking.update_status", return_value=[{"session_id": 1, "reservation_id": 2, "confirmed_declined": "confirmed"}]) as mock_update_status:
        result = resolve_verification(2, "yes", "kitchen confirmed no cross contamination")
    mock_update_status.assert_called_once_with(1, 2, "confirmed", "kitchen confirmed no cross contamination")
    assert result == {"session_id": 1, "booking_id": 2, "status": "confirmed"}


def test_resolve_verification_yes_without_reason_uses_default():
    with patch("tools_lambda.tools.booking.get_booking_status", return_value=[{"session_id": 1, "reservation_id": 2, "confirmed_declined": "pending", "party_size": 4, "date": "2026-08-28", "time": "12:00:00", "allergy_info": "Peanut allergy", "occupancy_end_time": "2026-08-28T13:30:00"}]), \
    patch("tools_lambda.tools.booking.update_escalation_answer", return_value=[{"owners_answer": "yes"}]), \
    patch("tools_lambda.tools.booking.update_status", return_value=[{"session_id": 1, "reservation_id": 2, "confirmed_declined": "confirmed"}]) as mock_update_status:
        resolve_verification(2, "yes", "")
    mock_update_status.assert_called_once_with(1, 2, "confirmed", "The owner approved the booking")


def test_resolve_verification_no_with_reason():
    with patch("tools_lambda.tools.booking.get_booking_status", return_value=[{"session_id": 1, "reservation_id": 2, "confirmed_declined": "pending", "party_size": 4, "date": "2026-08-28", "time": "12:00:00", "allergy_info": "Peanut allergy", "occupancy_end_time": "2026-08-28T13:30:00"}]), \
    patch("tools_lambda.tools.booking.update_escalation_answer", return_value=[{"owners_answer": "no"}]), \
    patch("tools_lambda.tools.booking.update_status", return_value=[{"session_id": 1, "reservation_id": 2, "confirmed_declined": "declined"}]) as mock_update_status:
        result = resolve_verification(2, "no", "kitchen can't guarantee it")
    mock_update_status.assert_called_once_with(1, 2, "declined", "kitchen can't guarantee it")
    assert result == {"session_id": 1, "booking_id": 2, "status": "declined"}


def test_resolve_verification_no_without_reason_uses_default():
    with patch("tools_lambda.tools.booking.get_booking_status", return_value=[{"session_id": 1, "reservation_id": 2, "confirmed_declined": "pending", "party_size": 4, "date": "2026-08-28", "time": "12:00:00", "allergy_info": "Peanut allergy", "occupancy_end_time": "2026-08-28T13:30:00"}]), \
    patch("tools_lambda.tools.booking.update_escalation_answer", return_value=[{"owners_answer": "no"}]), \
    patch("tools_lambda.tools.booking.update_status", return_value=[{"session_id": 1, "reservation_id": 2, "confirmed_declined": "declined"}]) as mock_update_status:
        resolve_verification(2, "no", "")
    mock_update_status.assert_called_once_with(1, 2, "declined", "The owner declined the booking")


def test_cancel_booking_when_no_records():
    with patch("tools_lambda.tools.booking.get_booking_status", return_value=[]):
        result = cancel_booking(2, "wrong day booking")
    assert result == "Booking not found."

@pytest.mark.parametrize("status", ["pending", "declined", "cancelled"])
def test_cancel_booking_when_status_not_confirmed(status):
    with patch("tools_lambda.tools.booking.get_booking_status", return_value=[{"session_id": 1, "reservation_id": 2, "confirmed_declined": status, "party_size": 4, "date": "2026-08-28", "time": "12:00:00", "allergy_info": "Peanut allergy", "occupancy_end_time": "2026-08-28T13:30:00"}]):
        result = cancel_booking(2, "wrong day booking")
    assert result == f"Cannot be cancelled as the booking has been {status}"


def test_cancel_booking_when_status_confirmed():
    with patch("tools_lambda.tools.booking.get_booking_status", return_value=[{"session_id": 1, "reservation_id": 2, "confirmed_declined": "confirmed", "party_size": 4, "date": "2026-08-28", "time": "12:00:00", "allergy_info": "Peanut allergy", "occupancy_end_time": "2026-08-28T13:30:00"}]), \
    patch("tools_lambda.tools.booking.update_status", return_value=[{"session_id": 1, "reservation_id": 2, "availability": "True", "confirmed_declined": "cancelled", "reason": "wrong day booking", "party_size": 4, "date": "2026-08-28", "time": "12:00:00", "allergy_info": "Peanut allergy", "start_time_hold_reserve": "2026-08-27T13:50:00", "end_time_hold_reserve":"2026-08-27T13:54:00", "created_at_timestamp": "2026-08-27T13:50:00", "occupancy_end_time": "2026-08-28T13:30:00"}]):
        result = cancel_booking(2, "wrong day booking")
    assert result == {
        "session_id": 1,
        "booking_id": 2,
        "status": "cancelled",
        "message": "Your booking has been cancelled and the reason is wrong day booking"
    }

@pytest.mark.parametrize("allergy_bucket, expected", [
    pytest.param("severe peanut allergy", "verification", id="Extreme word used"),
    pytest.param("", "auto", id="No allergy")

])
def test_bucket_gate(allergy_bucket, expected):
    allergy_info = _bucket_gate(allergy_bucket)
    assert allergy_info == expected