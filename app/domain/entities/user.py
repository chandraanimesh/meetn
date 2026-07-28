from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid

from app.domain.time import utc_now_naive

@dataclass
class User:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    display_name: str = ""
    primary_email: str = ""
    avatar_url: Optional[str] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=utc_now_naive)
    updated_at: datetime = field(default_factory=utc_now_naive)

@dataclass
class ExternalIdentity:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    provider: str = ""
    provider_subject: str = ""
    provider_email: str = ""
    email_verified: bool = False
    last_authenticated_at: datetime = field(default_factory=utc_now_naive)

@dataclass
class AuthSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    jwt_id: str = ""
    csrf_token: str = ""
    issued_at: datetime = field(default_factory=utc_now_naive)
    expires_at: datetime = field(default_factory=utc_now_naive)
    revoked_at: Optional[datetime] = None
    last_seen_at: datetime = field(default_factory=utc_now_naive)

    @property
    def is_active(self) -> bool:
        if self.revoked_at is not None:
            return False
        if utc_now_naive() >= self.expires_at:
            return False
        return True
