from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Path as PathParameter
from fastapi.responses import HTMLResponse, RedirectResponse

from app.web.page_renderer import render_page


router = APIRouter(include_in_schema=False)
STATIC_DIRECTORY = Path(__file__).resolve().parent / "static"

MeetingID = Annotated[
    str,
    PathParameter(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    ),
]


@router.get("/", response_class=RedirectResponse)
async def index() -> RedirectResponse:
    return RedirectResponse(url="/dashboard", status_code=302)


@router.get("/login", response_class=HTMLResponse)
async def login_page() -> HTMLResponse:
    return HTMLResponse(render_page("login"))


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page() -> HTMLResponse:
    return HTMLResponse(render_page("dashboard"))


@router.get("/meetings", response_class=HTMLResponse)
async def meeting_history_page() -> HTMLResponse:
    return HTMLResponse(render_page("meeting_history"))


@router.get("/meetings/{meeting_id}", response_class=HTMLResponse)
async def meeting_detail_page(meeting_id: MeetingID) -> HTMLResponse:
    return HTMLResponse(
        render_page("meeting_detail", active_meeting_id=meeting_id)
    )


@router.get(
    "/meetings/{meeting_id}/transcript",
    response_class=HTMLResponse,
)
async def transcript_page(meeting_id: MeetingID) -> HTMLResponse:
    return HTMLResponse(render_page("transcript", active_meeting_id=meeting_id))


@router.get(
    "/meetings/{meeting_id}/confidential-notes",
    response_class=HTMLResponse,
)
async def confidential_notes_page(meeting_id: MeetingID) -> HTMLResponse:
    return HTMLResponse(
        render_page("confidential_notes", active_meeting_id=meeting_id)
    )


@router.get("/plans", response_class=HTMLResponse)
async def membership_plans_page() -> HTMLResponse:
    return HTMLResponse(render_page("membership_plans"))
