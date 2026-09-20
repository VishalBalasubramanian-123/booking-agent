# verification_to_human, decision_to_human, reserve_table, check_booking.
from datetime import datetime, timedelta, date, time

from shared.db import supabase
from shared.queries import get_existing_bookings, get_maintenance_window, get_tables, get_closing_time, get_booking_status , update_status, book_table, get_customer, insert_customer, get_table_id, link_reservation_to_table, insert_escalation, update_escalation_answer, update_session_customer

# Default table occupancy when the guest doesn't specify how long they're staying.
DEFAULT_OCCUPANCY_TIME = timedelta(minutes=90)

# Pre-written status framing, keyed by reserve_table's real status -- the model
# should relay this verbatim rather than composing its own opening/celebratory
# sentence, which has been observed saying "confirmed" while correctly showing
# "Pending" two lines later in the same reply (error_log.md #27).
STATUS_MESSAGES = {
    "confirmed": "Your reservation is confirmed!",
    "pending": "Your reservation is pending — we've noted the allergy/safety information you shared, and our team will review it before confirming. We'll let you know as soon as it's decided.",
}

def _to_date(value: str | date):
    return date.fromisoformat(value) if isinstance(value, str) else value

def _to_time(value: str | time):
    return time.fromisoformat(value) if isinstance(value, str) else value

def _format_date_human(d: date) -> str:
    return d.strftime("%A, %B %-d, %Y")

def _format_time_human(t: time) -> str:
    return t.strftime("%-I:%M %p")

def _format_duration_human(td: timedelta) -> str:
    total_minutes = int(td.total_seconds() // 60)
    hours, minutes = divmod(total_minutes, 60)
    parts = []
    if hours:
        parts.append(f"{hours} hour" + ("s" if hours != 1 else ""))
    if minutes:
        parts.append(f"{minutes} minute" + ("s" if minutes != 1 else ""))
    return " ".join(parts) if parts else "0 minutes"

def _windows_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime):
    "checks if  either start_time asked by user is within (conflicting) existing booking end time"
    "or the end_time asked for is within the existing booked start time"
    return a_start < b_end and b_start < a_end


def _table_has_conflict(table_id: int, date: date, requested_start: datetime, requested_end: datetime) -> bool:
    "re-checks a specific table for a real conflict at write time -- check_availability's" \
    "result is only a snapshot from earlier in the conversation and can go stale (another" \
    "guest, in another session, may have booked the same table/slot in the meantime)."
    bookings = get_existing_bookings(table_id, date)
    return any(
        _windows_overlap(requested_start, requested_end, b["time"], b["occupancy_end_time"])
        for b in bookings
    )


def _find_next_free_start(time: datetime, occupancy_time: timedelta, sorted_bookings: list[dict]):
    "this function is to find the next available time of the tables. also implements the _windows_overlap function"
    candidates = sorted({time, *(b["occupancy_end_time"] for b in sorted_bookings)})
    for candidate_start in candidates:
        if candidate_start < time: # doesnt give you the list of times before the user given time 
            continue
        candidate_end = candidate_start + occupancy_time
        if not any(
            _windows_overlap(candidate_start, candidate_end, b["time"], b["occupancy_end_time"]) # calculates whether the specified candidate_end (total time needed does not conflict with prevous booking
            for b in sorted_bookings
        ):
            return candidate_start


def check_availability(date: date, time: time, party_size: int, table_number: int | None = None, stay_minutes: int | None = None):

    date = _to_date(date)
    time = _to_time(time)

    occupancy_time = timedelta(minutes=stay_minutes) if stay_minutes else DEFAULT_OCCUPANCY_TIME

    # Step 1: Capacity filter, before anything else
    candidate_tables = get_tables(party_size)

    if not candidate_tables:
        return [f"No single table fits a party of {party_size}"]
        # bucket-3 territory (owner decides on combining tables) — not this tool's job

    results = []

    for candidate in candidate_tables:
        table_id = candidate["table_id"]
        table = candidate["table_number"]

        # Step 2: Maintenance — its own check, own data source, never merged with booking status
        maintenance_window = get_maintenance_window(table_id, date, time)
        if maintenance_window:
            results.extend(
                [
                    {
                        "table": table,
                        "available": False,
                        "reason": w["reason"],
                        "window": [datetime.fromisoformat(w["start_time"]), datetime.fromisoformat(w["end_time"])],
                        "window_display": f"{_format_time_human(datetime.fromisoformat(w['start_time']).time())} to {_format_time_human(datetime.fromisoformat(w['end_time']).time())}",
                    }
                    for w in maintenance_window
                ]
            )
            continue

        # Step 3: Existing bookings — only ones that genuinely still hold the table
        bookings = get_existing_bookings(table_id, date)

        requested_start = datetime.combine(date, time)
        requested_end = requested_start + occupancy_time

        # Step 4: Real overlap check against EVERY existing booking, not just the latest
        conflicting = [
            b
            for b in bookings
            if _windows_overlap(requested_start, requested_end, b["time"], b["occupancy_end_time"])
        ]

        if not conflicting:
            results.append({
                "table": table,
                "available": True,
                "date": date,
                "time": time,
                "date_display": _format_date_human(date),
                "time_display": _format_time_human(time),
            })
            continue

        # Step 5: Table's busy at the requested time — find the next real gap that day
        sorted_bookings = sorted(bookings, key=lambda b: b["time"])
        next_free_start = _find_next_free_start(requested_start, occupancy_time, sorted_bookings)

        closing_time = get_closing_time(date)

        if next_free_start is not None and next_free_start + occupancy_time <= closing_time:
            results.append({
                "table": table,
                "available": False,
                "next_available_time": next_free_start,
                "next_available_time_display": _format_time_human(next_free_start.time()),
            })
        else:
            # nothing free today — look ahead up to 2 days, same table
            alt_slots = []
            for day_offset in (1, 2):
                next_date = date + timedelta(days=day_offset)
                if get_maintenance_window(table_id, next_date, time):
                    continue
                next_day_bookings = get_existing_bookings(table_id, next_date)
                next_day_closing = get_closing_time(next_date)
                sorted_next_day_bookings = sorted(next_day_bookings, key=lambda b: b["time"])
                computed_time = _find_next_free_start(datetime.combine(next_date, time), occupancy_time, sorted_next_day_bookings)
                if computed_time is not None and computed_time + occupancy_time <= next_day_closing:
                    alt_slots.append({
                        "date": next_date,
                        "time": computed_time,
                        "display": f"{_format_date_human(next_date)} at {_format_time_human(computed_time.time())}",
                    })
            results.append({"table": table, "available": False, "alternatives": alt_slots})

    # Step 6: Shape the response
    if table_number is not None:
        requested = next((r for r in results if r["table"] == table_number), None)
        same_night_alternatives = [
            r for r in results
            if (r.get("available") or r.get("next_available_time") is not None) and r["table"] != table_number #checks for both available = True and alternate times the table is available for.
        ]
        return [{"requested_table": requested, "alternative_tables": same_night_alternatives}]
    else:
        return results  # full status across every candidate table


def reserve_table(date: date, time: time, party_size: int, name: str, allergy_info: str, phone: str, email: str | None, table_number: int | None, session_id: int) -> dict:

    date = _to_date(date)
    time = _to_time(time)

    if not name and not phone:
        return "Please provide your name and phone number"
    elif not name:
        return "Please provide your name"
    elif not phone:
        return "Please provide your phone number"

    table_id = get_table_id(table_number)
    if table_id is None:
            return "Please choose one of the available tables first."

    requested_start = datetime.combine(date, time)
    requested_end = requested_start + DEFAULT_OCCUPANCY_TIME
    if _table_has_conflict(table_id, date, requested_start, requested_end):
        return f"Table {table_number} is no longer available at that time — please check availability again."

    check_customer_exists = get_customer(name, phone)

    # Make sure a customer record exists for this guest. session_id comes in
    # as its own parameter (this conversation's session) — it is not derived
    # from the customer lookup.
    if check_customer_exists:
        customer_id = check_customer_exists[0]["customer_id"]
    else:
        new_customer = insert_customer(name, phone, email)
        customer_id = new_customer[0]["customer_id"]

    update_session_customer(session_id, customer_id)

    occupancy_end_time = datetime.combine(date, time) + DEFAULT_OCCUPANCY_TIME
    booking_table = book_table(
        session_id=session_id,
        date=date,
        confirmed_declined="pending",
        allergy_info=allergy_info,
        time=time,
        party_size=party_size,
        occupancy_end_time=occupancy_end_time,
    )
    link_reservation_to_table(booking_table[0]["reservation_id"], table_id)

    bucket = _bucket_gate(allergy_info)

    if bucket == "auto":
        status_update = update_status(session_id, booking_table[0]["reservation_id"], "confirmed", "No allergy or safety concern noted")
        status = status_update[0]["confirmed_declined"]
    elif bucket == "verification":
        # Bucket 2 is fire-and-forget: hand off to the owner and return
        # immediately. The reservation stays "pending" until resolve_verification
        # (called from the owner side) or the hold-expiry sweep updates it.
        verification_to_human(booking_table[0]["reservation_id"], session_id, bucket)
        status = "pending"

    booked_date = _to_date(booking_table[0]["date"])
    booked_time = _to_time(booking_table[0]["time"])

    return {
        "session_id": session_id,
        "reservation_id": booking_table[0]["reservation_id"],
        "date": booking_table[0]["date"],
        "time": booking_table[0]["time"],
        "date_display": _format_date_human(booked_date),
        "time_display": _format_time_human(booked_time),
        "party_size": booking_table[0]["party_size"],
        "status": status,
        "status_message": STATUS_MESSAGES[status],
    }


def check_booking(booking_id: int):
    current_status = get_booking_status(booking_id)

    if current_status:
        booking_date = date.fromisoformat(current_status[0]["date"])
        booking_time = time.fromisoformat(current_status[0]["time"])
        total_time = datetime.fromisoformat(current_status[0]["occupancy_end_time"]) - datetime.combine(booking_date, booking_time)
        response = {
            "session_id": current_status[0]["session_id"],
            "status": current_status[0]["confirmed_declined"],
            "party": current_status[0]["party_size"],
            "date": booking_date,
            "time": booking_time,
            "date_display": _format_date_human(booking_date),
            "time_display": _format_time_human(booking_time),
            "allergy_information": current_status[0]["allergy_info"],
            "total_time": total_time,
            "total_time_display": _format_duration_human(total_time),
        }
        return response
    else:
        return None


def verification_to_human(booking_id: int, session_id: int, bucket: str):
    escalation = insert_escalation(booking_id, session_id, bucket)
    return "Please wait a moment, checking with the team for confirmation"

def resolve_verification(booking_id: int, answer: str, reason: str):
    check_status = check_booking(booking_id)
    if check_status is None:
        return "Booking not found."

    escalation_update = update_escalation_answer(booking_id, answer)
    if not escalation_update:
        return "This booking has already been resolved."

    if answer.strip().lower() == "yes":
        status = "confirmed"  
        final_reason = reason.strip() if reason and reason.strip() else "The owner approved the booking"
    else:
        status = "declined"
        final_reason = reason.strip() if reason and reason.strip() else "The owner declined the booking"

    status_update = update_status(check_status["session_id"], booking_id, status, final_reason)

    return {
        "session_id": status_update[0]["session_id"],
        "booking_id": status_update[0]["reservation_id"],
        "status": status_update[0]["confirmed_declined"],
    }

# def decision_to_human(booking_id, decision):
#     pass

def cancel_booking(booking_id: int, reason: str = "No reason given"):
    check_status = check_booking(booking_id)

    if check_status is None:
        return "Booking not found."
    if check_status["status"].lower() in ["pending", "declined", "cancelled"]:
        return f"Cannot be cancelled as the booking has been {check_status['status']}"

    cancellation = update_status(check_status["session_id"], booking_id, "cancelled", reason)

    result = {
        "session_id": cancellation[0]["session_id"],
        "booking_id": cancellation[0]["reservation_id"],
        "status": cancellation[0]["confirmed_declined"],
        "message": f"Your booking has been cancelled and the reason is {cancellation[0]['reason']}"
    }

    return result


def _bucket_gate(allergy_info: str):
    if allergy_info:
        return "verification"
    return "auto"