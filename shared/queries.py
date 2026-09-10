# Reusable reservation/escalation queries.
from datetime import datetime, timedelta

from shared.db import supabase

def get_tables(party_size):
    response = supabase.table("tables_info").select("table_id", "table_number").gte("capacity", party_size).execute().data
    return response

def get_restaurant_name():
    response = supabase.table("restaurant_info").select("restaurant_name").execute().data
    if not response:
        return None
    return response[0]["restaurant_name"]

def get_booking_status(booking_id):
    response = supabase.table("reservation").select("session_id", "reservation_id", "confirmed_declined", "party_size", "date", "time", "allergy_info", "occupancy_end_time").eq("reservation_id", booking_id).execute().data
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

def update_status(session_id, booking_id, status,reason):
    updated_status = supabase.table("reservation").update({"confirmed_declined": status, "reason": reason}).eq("session_id", session_id).eq("reservation_id", booking_id).execute().data
    return updated_status

def get_kb_content():
    kb_content = supabase.table("restaurant_kb").select("restaurant_kb_id", "content").is_("embedding", "null").execute().data
    return kb_content

def update_kb_content(restaurant_kb_id, content_embedding):
    kb_content = supabase.table("restaurant_kb").update({"embedding": content_embedding}).eq("restaurant_kb_id", restaurant_kb_id).execute().data
    return kb_content

def get_matching_kb_contents(query_embeddings):
    matching = supabase.rpc("match_kb_content", {"query_embedding": query_embeddings, "match_count": 5}).execute().data
    return matching

def get_table_id(table_number):
    response = supabase.table("tables_info").select("table_id").eq("table_number", table_number).execute().data
    if not response:
        return None
    return response[0]["table_id"]

def link_reservation_to_table(reservation_id, table_id):
    linked = supabase.table("reservation_tables_booking").insert({"reservation_id": reservation_id, "table_id": table_id}).execute().data
    return linked

def book_table(session_id, date, confirmed_declined, allergy_info, time, party_size, occupancy_end_time):
    booked_table = supabase.from_("reservation").insert({"session_id": session_id, "availability": False, "confirmed_declined": confirmed_declined, "party_size": party_size, "date": date, "time": time, "allergy_info": allergy_info, "start_time_hold_reserve": datetime.now(), "end_time_hold_reserve": datetime.now() + timedelta(minutes=5), "occupancy_end_time": occupancy_end_time}).execute().data
    return booked_table

def get_customer(name, phone):
    customer = supabase.from_("customer").select("customer_id, name, phone, session(session_id, customer_id)").eq("name", name).eq("phone", phone).execute().data
    return customer

def insert_customer(name, phone, email):
    updated_status = supabase.table("customer").insert({"name": name, "phone": phone, "email": email}).execute().data
    return updated_status