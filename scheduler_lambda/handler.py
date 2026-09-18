# EventBridge-triggered sweep: declines expired pending reservations.
from scheduler_lambda.sweep import decline_expired_reservations


def handler(event, context):
    declined = decline_expired_reservations()
    return {"declined_count": len(declined), "declined": declined}
