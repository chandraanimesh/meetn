from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PageManifestDTO:
    page_id: str
    active_meeting_id: str | None = None
    visible_meeting_ids: tuple[str, ...] = ()
