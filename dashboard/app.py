# Owner-facing web app.
# For now: a CLI stand-in that lets the owner work through pending bucket-2
# verifications one at a time. Will be replaced by a real web app later.
from shared.queries import get_pending_escalations
from tools_lambda.tools.booking import resolve_verification


def main():
    pending = get_pending_escalations()

    if not pending:
        print("No pending verifications.")
        return

    for item in pending:
        reservation = item["reservation"]
        print(f"\nBooking {item['reservation_id']} — party of {reservation['party_size']} on {reservation['date']} at {reservation['time']}")
        print(f"Allergy info: {reservation['allergy_info']}")

        answer = input("Approve? (yes/no): ").strip().lower()
        reason = input("Reason (optional): ").strip()

        result = resolve_verification(item["reservation_id"], answer, reason)
        print(result)


if __name__ == "__main__":
    main()
