from abc import ABC, abstractmethod
from typing import List, Optional
from app.domain.entities.meeting import (
    ConfidentialNote,
    ConfidentialNoteAccess,
    Meeting,
    MeetingParticipant,
    ParticipantMembershipStatus,
    Transcript,
)
from app.domain.value_objects.authorization_facts import (
    ConfidentialNoteAccessFacts,
    MeetingAccessFacts,
)


class TranscriptAlreadyExistsError(Exception):
    """Raised when a meeting already has its single allowed transcript."""


class MeetingRepositoryPort(ABC):
    @abstractmethod
    async def create_meeting(self, meeting: Meeting) -> Meeting:
        pass

    @abstractmethod
    async def get_meeting_by_id(
        self, meeting_id: str, requesting_user_id: str
    ) -> Optional[Meeting]:
        pass

    @abstractmethod
    async def get_meeting_access_facts(
        self, meeting_id: str
    ) -> Optional[MeetingAccessFacts]:
        """Load content-free, trusted facts for application authorization."""
        pass
        
    @abstractmethod
    async def list_meetings_by_user(self, user_id: str) -> List[Meeting]:
        pass

    @abstractmethod
    async def update_meeting(self, meeting: Meeting, actor_user_id: str) -> Meeting:
        pass

    @abstractmethod
    async def add_participant(
        self, participant: MeetingParticipant, actor_user_id: str
    ) -> MeetingParticipant:
        pass

    @abstractmethod
    async def get_participants(
        self, meeting_id: str, requesting_user_id: str
    ) -> List[MeetingParticipant]:
        pass

    @abstractmethod
    async def update_participant_membership(
        self,
        meeting_id: str,
        user_id: str,
        status: ParticipantMembershipStatus,
        actor_user_id: str,
    ) -> Optional[MeetingParticipant]:
        pass

    @abstractmethod
    async def add_transcript(
        self, transcript: Transcript, actor_user_id: str
    ) -> Transcript:
        pass

    @abstractmethod
    async def get_transcript(
        self, meeting_id: str, requesting_user_id: str
    ) -> Optional[Transcript]:
        pass

    @abstractmethod
    async def transcript_exists(self, meeting_id: str) -> bool:
        """Check transcript existence without loading protected content."""
        pass

    @abstractmethod
    async def add_confidential_note(
        self, note: ConfidentialNote, actor_user_id: str
    ) -> ConfidentialNote:
        pass

    @abstractmethod
    async def get_confidential_notes(self, meeting_id: str, user_id: str) -> List[ConfidentialNote]:
        """
        Get notes for a meeting that were either created by user_id OR user_id was granted access.
        """
        pass

    @abstractmethod
    async def get_confidential_note_access_facts(
        self, meeting_id: str
    ) -> List[ConfidentialNoteAccessFacts]:
        """Load note grants and scope without selecting confidential content."""
        pass
        
    @abstractmethod
    async def get_confidential_note_by_id(
        self, note_id: str, requesting_user_id: str
    ) -> Optional[ConfidentialNote]:
        pass

    @abstractmethod
    async def grant_note_access(self, access: ConfidentialNoteAccess) -> ConfidentialNoteAccess:
        pass

    @abstractmethod
    async def revoke_note_access(
        self, note_id: str, user_id: str, actor_user_id: str
    ) -> bool:
        pass
