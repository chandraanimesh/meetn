from datetime import UTC, datetime


def utc_now_naive() -> datetime:
    """Return explicit UTC using the project's existing naïve-UTC DB contract."""

    return datetime.now(UTC).replace(tzinfo=None)


def utc_from_timestamp_naive(timestamp: float) -> datetime:
    """Convert a Unix timestamp to naïve UTC without using local time."""

    return datetime.fromtimestamp(timestamp, UTC).replace(tzinfo=None)
