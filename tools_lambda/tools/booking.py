# verification_to_human, decision_to_human, reserve_table, check_booking.
from datetime import datetime, timedelta

from shared.db import supabase
from shared.queries import get_existing_bookings, get_maintenance_window, get_tables, get_closing_time
from tools_lambda.tools.kb import check_KB as check_KB_tool

# Default table occupancy when the guest doesn't specify how long they're staying.
DEFAULT_OCCUPANCY_TIME = timedelta(minutes=90)


def _windows_overlap(a_start, a_end, b_start, b_end):
    "checks if  either start_time asked by user is within (conflicting) existing booking end time"
    "or the end_time asked for is within the existing booked start time"
    return a_start < b_end and b_start < a_end


def _find_next_free_start(time, occupancy_time, sorted_bookings):
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


def check_availability(date, time, party_size, table_number=None, stay_minutes=None):
    occupancy_time = timedelta(minutes=stay_minutes) if stay_minutes else DEFAULT_OCCUPANCY_TIME

    # Step 1: Capacity filter, before anything else
    candidate_tables = get_tables(party_size)

    if not candidate_tables:
        return f"No single table fits a party of {party_size}"
        # bucket-3 territory (owner decides on combining tables) — not this tool's job

    results = []

    for candidate in candidate_tables:
        table_id = candidate["table_id"]
        table = candidate["table_number"]

        # Step 2: Maintenance — its own check, own data source, never merged with booking status
        maintenance_window = get_maintenance_window(table_id, date, time)
        if maintenance_window:
            results.extend(
                [{"table": table, "available": False, "reason": w["reason"], "window": [datetime.fromisoformat(w["start_time"]), datetime.fromisoformat(w["end_time"])]} for w in maintenance_window]
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
            results.append({"table": table, "available": True, "date": date, "time": time})
            continue

        # Step 5: Table's busy at the requested time — find the next real gap that day
        sorted_bookings = sorted(bookings, key=lambda b: b["time"])
        next_free_start = _find_next_free_start(requested_start, occupancy_time, sorted_bookings)

        closing_time = get_closing_time(date)

        if next_free_start is not None and next_free_start + occupancy_time <= closing_time:
            results.append({"table": table, "available": False, "next_available_time": next_free_start})
        else:
            # nothing free today — look ahead up to 2 days, same table
            alt_slots = []
            for day_offset in (1, 2):
                next_date = date + timedelta(days=day_offset)
                next_day_bookings = get_existing_bookings(table_id, next_date)
                next_day_closing = get_closing_time(next_date)
                sorted_next_day_bookings = sorted(next_day_bookings, key=lambda b: b["time"])
                computed_time = _find_next_free_start(datetime.combine(next_date, time), occupancy_time, sorted_next_day_bookings)
                if computed_time is not None and computed_time + occupancy_time <= next_day_closing:
                    alt_slots.append((next_date, computed_time))
            results.append({"table": table, "available": False, "alternatives": alt_slots})

    # Step 6: Shape the response
    if table_number is not None:
        requested = next((r for r in results if r["table"] == table_number), None)
        same_night_alternatives = [
            r for r in results
            if (r.get("available") or r.get("next_available_time") is not None) and r["table"] != table_number #checks for both available = True and alternate times the table is available for.
        ]
        return {"requested_table": requested, "alternative_tables": same_night_alternatives}
    else:
        return results  # full status across every candidate table


def reserve_table(date, time, party_size, name, phone, email, table_number=None):
    pass


def check_booking(booking_id):
    pass


def verification_to_human(booking_id, reason):
    pass


def decision_to_human(booking_id, decision):
    pass

def cancel_booking(booking_id):
    pass