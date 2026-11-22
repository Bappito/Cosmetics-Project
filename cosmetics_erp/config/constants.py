from datetime import date

CLOSED_PO_STATUSES = ("Received", "Cancelled")

# Leave as None to start the eight-week plan at the current week's Sunday.
# Set a date here to pin the planning window to a fixed start.
PLAN_START_OVERRIDE: date | None = None
