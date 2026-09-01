# Reusable reservation/escalation queries.
from datetime import datetime

from shared.db import supabase

def get_tables(party_size):
    response = supabase.table("tables_info").select("table_id", "table_number").gte("capacity", party_size).execute().data
    return response

def get_closing_time(date):
    column = "weekend_closing_time" if date.weekday() >= 5 else "weekday_closing_time"
    response = supabase.table("restaurant_info").select(column).execute().data
    if not response:
        return None
    closing_time = datetime.combine(date, datetime.strptime(response[0][column], "%H:%M:%S").time())
    return closing_time


def get_maintenance_window(table_id, date, time):
    requested_at = datetime.combine(date, time)
    response = (
        supabase.table("table_unavailability")
        .select("*, tables_info(table_number)")
        .eq("table_id", table_id)
        .lte("start_time", requested_at.isoformat())
        .gte("end_time", requested_at.isoformat())
        .execute()
        .data
    )
    return response


def get_existing_bookings(table_id, date):
    rows = (
        supabase.table("reservation_tables_booking")
        .select(
            "tables_info(table_number), "
            "reservation(date, time, occupancy_end_time, confirmed_declined, end_time_hold_reserve)"
        )
        .eq("table_id", table_id)
        .execute()
        .data
    )

    now = datetime.now()
    bookings = []
    for row in rows:
        reservation = row["reservation"]
        if reservation["date"] != date.isoformat():
            continue

        confirmed_declined = reservation["confirmed_declined"]
        end_time_hold_reserve = reservation["end_time_hold_reserve"]
        still_on_hold = (
            confirmed_declined == "pending"
            and end_time_hold_reserve is not None
            and now < datetime.fromisoformat(reservation["end_time_hold_reserve"])
        )
        if confirmed_declined != "confirmed" and not still_on_hold:
            continue

        booking_time = datetime.combine(date, datetime.strptime(reservation["time"], "%H:%M:%S").time())
        bookings.append(
            {
                "table_number": row["tables_info"]["table_number"],
                "time": booking_time,
                "occupancy_end_time": datetime.fromisoformat(reservation["occupancy_end_time"]),
            }
        )
    return bookings
