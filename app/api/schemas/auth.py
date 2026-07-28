from pydantic import BaseModel

class UserSummary(BaseModel):
    id: str
    display_name: str
    primary_email: str
    avatar_url: str | None

class SessionResponse(BaseModel):
    user: UserSummary
    csrf_token: str
    message: str = "Authenticated successfully"
