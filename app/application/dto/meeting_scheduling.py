from dataclasses import dataclass
from datetime import UTC, datetime


MINIMUM_MEETING_DURATION_MINUTES = 15
MAXIMUM_MEETING_DURATION_MINUTES = 480


def normalize_start_time(value: datetime) -> datetime:
    """Convert an aware timestamp to the project's naive-UTC DB contract."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Meeting start time must include a timezone")
    return value.astimezone(UTC).replace(tzinfo=None)


@dataclass(frozen=True, slots=True)
class MeetingCreateCommand:
    title: str
    place: str
    purpose: str
    start_time: datetime
    duration_minutes: int
    personal_gift: str = ""


@dataclass(frozen=True, slots=True)
class MeetingRescheduleCommand:
    start_time: datetime
    duration_minutes: int
    title: str | None = None
    place: str | None = None
    purpose: str | None = None
    personal_gift: str | None = None
