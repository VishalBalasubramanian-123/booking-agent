# Declines any reservation still "pending" once its hold window has expired.
# This is the fail-closed enforcement itself -- it runs on its own EventBridge
# schedule, independent of whether any CLI session or owner dashboard happens
# to be open. Anything it finds is, by construction, an unanswered bucket-2
# escalation: bucket-1 bookings get confirmed synchronously inside
# reserve_table, so they're never still "pending" by the time this runs.
from shared.queries import get_expired_pending_reservations, update_status

DECLINE_REASON = "No response from the owner within the hold window"


def decline_expired_reservations():
    expired = get_expired_pending_reservations()

    declined = []
    for reservation in expired:
        result = update_status(
            reservation["session_id"],
            reservation["reservation_id"],
            "declined",
            DECLINE_REASON,
        )
        declined.append(result[0])
    return declined
