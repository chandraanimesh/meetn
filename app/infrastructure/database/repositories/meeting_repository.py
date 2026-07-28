from typing import Any, List, Optional

from sqlalchemy import exists, inspect, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.application.ports.meeting_repository import (
    MeetingRepositoryPort,
    TranscriptAlreadyExistsError,
)
from app.domain.entities.meeting import (
    ConfidentialNote,
    ConfidentialNoteAccess,
    Meeting,
    MeetingParticipant,
    ParticipantMembershipStatus,
    ParticipantRole,
    Transcript,
)
from app.domain.time import utc_now_naive
from app.domain.value_objects.authorization_facts import (
    ActiveMeetingRole,
    ConfidentialNoteAccessFacts,
    MeetingAccessFacts,
)
from app.infrastructure.database.models.meeting import (
    ConfidentialNoteAccessModel,
    ConfidentialNoteModel,
    MeetingModel,
    MeetingParticipantModel,
    TranscriptModel,
)


class SQLAlchemyMeetingRepository(MeetingRepositoryPort):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _commit(self) -> None:
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    def _to_meeting_entity(self, model: MeetingModel) -> Meeting:
        meeting = Meeting(
            id=model.id,
            title=model.title,
            created_by=model.created_by,
            start_time=model.start_time,
            end_time=model.end_time,
            status=model.status,
            place=model.place,
            purpose=model.purpose,
            personal_gift=model.personal_gift,
            created_at=model.created_at,
        )
        model_state: Any = inspect(model)
        if "participants" not in model_state.unloaded:
            meeting.participants = [
                self._to_participant_entity(participant)
                for participant in model.participants
            ]
        if "transcript" not in model_state.unloaded and model.transcript is not None:
            meeting.transcript = self._to_transcript_entity(model.transcript)
        if "confidential_notes" not in model_state.unloaded:
            meeting.confidential_notes = [
                self._to_note_entity(note) for note in model.confidential_notes
            ]
        return meeting

    def _to_meeting_model(self, entity: Meeting) -> MeetingModel:
        return MeetingModel(
            id=entity.id,
            title=entity.title,
            created_by=entity.created_by,
            start_time=entity.start_time,
            end_time=entity.end_time,
            status=entity.status,
            place=entity.place,
            purpose=entity.purpose,
            personal_gift=entity.personal_gift,
            created_at=entity.created_at,
        )

    def _to_participant_entity(
        self, model: MeetingParticipantModel
    ) -> MeetingParticipant:
        return MeetingParticipant(
            id=model.id,
            meeting_id=model.meeting_id,
            user_id=model.user_id,
            role=model.role,
            joined_at=model.joined_at,
            membership_status=model.membership_status,
            removed_at=model.removed_at,
        )

    def _to_participant_model(
        self, entity: MeetingParticipant
    ) -> MeetingParticipantModel:
        return MeetingParticipantModel(
            id=entity.id,
            meeting_id=entity.meeting_id,
            user_id=entity.user_id,
            role=entity.role,
            joined_at=entity.joined_at,
            membership_status=entity.membership_status,
            removed_at=entity.removed_at,
        )

    def _to_transcript_entity(self, model: TranscriptModel) -> Transcript:
        return Transcript(
            id=model.id,
            meeting_id=model.meeting_id,
            content=model.content,
            created_at=model.created_at,
        )

    def _to_transcript_model(self, entity: Transcript) -> TranscriptModel:
        return TranscriptModel(
            id=entity.id,
            meeting_id=entity.meeting_id,
            content=entity.content,
            created_at=entity.created_at,
        )

    def _to_note_entity(self, model: ConfidentialNoteModel) -> ConfidentialNote:
        note = ConfidentialNote(
            id=model.id,
            meeting_id=model.meeting_id,
            created_by=model.created_by,
            content=model.content,
            created_at=model.created_at,
            deleted_at=model.deleted_at,
        )
        model_state: Any = inspect(model)
        if "access_list" not in model_state.unloaded:
            note.access_list = [
                self._to_access_entity(access) for access in model.access_list
            ]
        return note

    def _to_note_model(self, entity: ConfidentialNote) -> ConfidentialNoteModel:
        return ConfidentialNoteModel(
            id=entity.id,
            meeting_id=entity.meeting_id,
            created_by=entity.created_by,
            content=entity.content,
            created_at=entity.created_at,
            deleted_at=entity.deleted_at,
        )

    def _to_access_entity(
        self, model: ConfidentialNoteAccessModel
    ) -> ConfidentialNoteAccess:
        return ConfidentialNoteAccess(
            id=model.id,
            note_id=model.note_id,
            user_id=model.user_id,
            granted_by=model.granted_by,
            granted_at=model.granted_at,
            revoked_at=model.revoked_at,
        )

    def _to_access_model(
        self, entity: ConfidentialNoteAccess
    ) -> ConfidentialNoteAccessModel:
        return ConfidentialNoteAccessModel(
            id=entity.id,
            note_id=entity.note_id,
            user_id=entity.user_id,
            granted_by=entity.granted_by,
            granted_at=entity.granted_at,
            revoked_at=entity.revoked_at,
        )

    async def create_meeting(self, meeting: Meeting) -> Meeting:
        meeting_model = self._to_meeting_model(meeting)
        organizer_participant = MeetingParticipantModel(
            meeting_id=meeting.id,
            user_id=meeting.created_by,
            role=ParticipantRole.HOST,
            joined_at=meeting.created_at,
            membership_status=ParticipantMembershipStatus.ACTIVE,
        )
        self.session.add_all([meeting_model, organizer_participant])
        await self._commit()
        return self._to_meeting_entity(meeting_model)

    async def get_meeting_by_id(
        self, meeting_id: str, requesting_user_id: str
    ) -> Optional[Meeting]:
        active_participant = exists(
            select(1).where(
                MeetingParticipantModel.meeting_id == MeetingModel.id,
                MeetingParticipantModel.user_id == requesting_user_id,
                MeetingParticipantModel.membership_status
                == ParticipantMembershipStatus.ACTIVE,
            )
        )
        stmt = (
            select(MeetingModel)
            .options(
                selectinload(
                    MeetingModel.participants.and_(
                        MeetingParticipantModel.membership_status
                        == ParticipantMembershipStatus.ACTIVE
                    )
                )
            )
            .where(
                MeetingModel.id == meeting_id,
                or_(
                    MeetingModel.created_by == requesting_user_id,
                    active_participant,
                ),
            )
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_meeting_entity(model) if model is not None else None

    async def get_meeting_access_facts(
        self, meeting_id: str
    ) -> Optional[MeetingAccessFacts]:
        stmt = (
            select(MeetingModel)
            .options(selectinload(MeetingModel.participants))
            .where(MeetingModel.id == meeting_id)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None

        active_participants = tuple(
            participant
            for participant in model.participants
            if participant.membership_status is ParticipantMembershipStatus.ACTIVE
        )
        return MeetingAccessFacts(
            meeting_id=model.id,
            organizer_user_id=model.created_by,
            active_participant_user_ids=frozenset(
                participant.user_id for participant in active_participants
            ),
            active_role_assignments=frozenset(
                ActiveMeetingRole(
                    user_id=participant.user_id,
                    role_id=participant.role.value,
                )
                for participant in active_participants
            ),
        )

    async def list_meetings_by_user(self, user_id: str) -> List[Meeting]:
        active_participant = exists(
            select(1).where(
                MeetingParticipantModel.meeting_id == MeetingModel.id,
                MeetingParticipantModel.user_id == user_id,
                MeetingParticipantModel.membership_status
                == ParticipantMembershipStatus.ACTIVE,
            )
        )
        stmt = (
            select(MeetingModel)
            .options(
                selectinload(
                    MeetingModel.participants.and_(
                        MeetingParticipantModel.membership_status
                        == ParticipantMembershipStatus.ACTIVE
                    )
                )
            )
            .where(
                or_(MeetingModel.created_by == user_id, active_participant)
            )
            .order_by(MeetingModel.start_time.desc())
        )
        result = await self.session.execute(stmt)
        return [self._to_meeting_entity(model) for model in result.scalars().all()]

    async def update_meeting(
        self, meeting: Meeting, actor_user_id: str
    ) -> Meeting:
        result = await self.session.execute(
            select(MeetingModel).where(
                MeetingModel.id == meeting.id,
                MeetingModel.created_by == actor_user_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise PermissionError("Meeting update is not permitted")

        model.title = meeting.title
        model.start_time = meeting.start_time
        model.end_time = meeting.end_time
        model.status = meeting.status
        model.place = meeting.place
        model.purpose = meeting.purpose
        model.personal_gift = meeting.personal_gift
        await self._commit()
        return self._to_meeting_entity(model)

    async def add_participant(
        self, participant: MeetingParticipant, actor_user_id: str
    ) -> MeetingParticipant:
        organizer_result = await self.session.execute(
            select(MeetingModel.id).where(
                MeetingModel.id == participant.meeting_id,
                MeetingModel.created_by == actor_user_id,
            )
        )
        if organizer_result.scalar_one_or_none() is None:
            raise PermissionError("Participant update is not permitted")

        existing_result = await self.session.execute(
            select(MeetingParticipantModel).where(
                MeetingParticipantModel.meeting_id == participant.meeting_id,
                MeetingParticipantModel.user_id == participant.user_id,
            )
        )
        model = existing_result.scalar_one_or_none()
        if model is None:
            model = self._to_participant_model(participant)
            self.session.add(model)
        else:
            model.role = participant.role
            model.membership_status = ParticipantMembershipStatus.ACTIVE
            model.removed_at = None
            model.joined_at = participant.joined_at or model.joined_at

        await self._commit()
        return self._to_participant_entity(model)

    async def get_participants(
        self, meeting_id: str, requesting_user_id: str
    ) -> List[MeetingParticipant]:
        active_requester = exists(
            select(1).where(
                MeetingParticipantModel.meeting_id == MeetingModel.id,
                MeetingParticipantModel.user_id == requesting_user_id,
                MeetingParticipantModel.membership_status
                == ParticipantMembershipStatus.ACTIVE,
            )
        )
        visible_meeting = exists(
            select(1).where(
                MeetingModel.id == meeting_id,
                or_(
                    MeetingModel.created_by == requesting_user_id,
                    active_requester,
                ),
            )
        )
        stmt = select(MeetingParticipantModel).where(
            MeetingParticipantModel.meeting_id == meeting_id,
            MeetingParticipantModel.membership_status
            == ParticipantMembershipStatus.ACTIVE,
            visible_meeting,
        )
        result = await self.session.execute(stmt)
        return [
            self._to_participant_entity(model) for model in result.scalars().all()
        ]

    async def update_participant_membership(
        self,
        meeting_id: str,
        user_id: str,
        status: ParticipantMembershipStatus,
        actor_user_id: str,
    ) -> Optional[MeetingParticipant]:
        meeting_result = await self.session.execute(
            select(MeetingModel).where(
                MeetingModel.id == meeting_id,
                MeetingModel.created_by == actor_user_id,
            )
        )
        meeting = meeting_result.scalar_one_or_none()
        if meeting is None:
            return None
        if user_id == meeting.created_by and status is not ParticipantMembershipStatus.ACTIVE:
            raise ValueError("The meeting organizer must remain active")

        participant_result = await self.session.execute(
            select(MeetingParticipantModel).where(
                MeetingParticipantModel.meeting_id == meeting_id,
                MeetingParticipantModel.user_id == user_id,
            )
        )
        participant = participant_result.scalar_one_or_none()
        if participant is None:
            return None

        participant.membership_status = status
        participant.removed_at = (
            None if status is ParticipantMembershipStatus.ACTIVE else utc_now_naive()
        )
        if status is not ParticipantMembershipStatus.ACTIVE:
            note_ids = select(ConfidentialNoteModel.id).where(
                ConfidentialNoteModel.meeting_id == meeting_id
            )
            await self.session.execute(
                update(ConfidentialNoteAccessModel)
                .where(
                    ConfidentialNoteAccessModel.note_id.in_(note_ids),
                    ConfidentialNoteAccessModel.user_id == user_id,
                    ConfidentialNoteAccessModel.revoked_at.is_(None),
                )
                .values(revoked_at=participant.removed_at)
            )

        await self._commit()
        return self._to_participant_entity(participant)

    async def add_transcript(
        self, transcript: Transcript, actor_user_id: str
    ) -> Transcript:
        organizer_result = await self.session.execute(
            select(MeetingModel.id).where(
                MeetingModel.id == transcript.meeting_id,
                MeetingModel.created_by == actor_user_id,
            )
        )
        if organizer_result.scalar_one_or_none() is None:
            raise PermissionError("Transcript update is not permitted")

        model = self._to_transcript_model(transcript)
        self.session.add(model)
        try:
            await self._commit()
        except IntegrityError as exc:
            raise TranscriptAlreadyExistsError from exc
        return self._to_transcript_entity(model)

    async def get_transcript(
        self, meeting_id: str, requesting_user_id: str
    ) -> Optional[Transcript]:
        stmt = (
            select(TranscriptModel)
            .join(
                MeetingParticipantModel,
                MeetingParticipantModel.meeting_id == TranscriptModel.meeting_id,
            )
            .where(
                TranscriptModel.meeting_id == meeting_id,
                MeetingParticipantModel.user_id == requesting_user_id,
                MeetingParticipantModel.membership_status
                == ParticipantMembershipStatus.ACTIVE,
            )
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_transcript_entity(model) if model is not None else None

    async def transcript_exists(self, meeting_id: str) -> bool:
        result = await self.session.execute(
            select(TranscriptModel.id).where(TranscriptModel.meeting_id == meeting_id)
        )
        return result.scalar_one_or_none() is not None

    async def add_confidential_note(
        self, note: ConfidentialNote, actor_user_id: str
    ) -> ConfidentialNote:
        organizer_result = await self.session.execute(
            select(MeetingModel.id).where(
                MeetingModel.id == note.meeting_id,
                MeetingModel.created_by == actor_user_id,
            )
        )
        if (
            organizer_result.scalar_one_or_none() is None
            or note.created_by != actor_user_id
        ):
            raise PermissionError("Confidential note creation is not permitted")

        model = self._to_note_model(note)
        self.session.add(model)
        await self._commit()
        return self._to_note_entity(model)

    async def get_confidential_notes(
        self, meeting_id: str, user_id: str
    ) -> List[ConfidentialNote]:
        active_participant = exists(
            select(1).where(
                MeetingParticipantModel.meeting_id == ConfidentialNoteModel.meeting_id,
                MeetingParticipantModel.user_id == user_id,
                MeetingParticipantModel.membership_status
                == ParticipantMembershipStatus.ACTIVE,
            )
        )
        active_grant = exists(
            select(1).where(
                ConfidentialNoteAccessModel.note_id == ConfidentialNoteModel.id,
                ConfidentialNoteAccessModel.user_id == user_id,
                ConfidentialNoteAccessModel.revoked_at.is_(None),
            )
        )
        stmt = (
            select(ConfidentialNoteModel)
            .join(MeetingModel, MeetingModel.id == ConfidentialNoteModel.meeting_id)
            .options(selectinload(ConfidentialNoteModel.access_list))
            .where(
                ConfidentialNoteModel.meeting_id == meeting_id,
                ConfidentialNoteModel.deleted_at.is_(None),
                active_participant,
                or_(MeetingModel.created_by == user_id, active_grant),
            )
        )
        result = await self.session.execute(stmt)
        return [self._to_note_entity(model) for model in result.unique().scalars()]

    async def get_confidential_note_access_facts(
        self, meeting_id: str
    ) -> List[ConfidentialNoteAccessFacts]:
        note_result = await self.session.execute(
            select(
                ConfidentialNoteModel.id,
                ConfidentialNoteModel.meeting_id,
                ConfidentialNoteModel.deleted_at,
            ).where(ConfidentialNoteModel.meeting_id == meeting_id)
        )
        note_rows = note_result.all()
        if not note_rows:
            return []

        note_ids = tuple(row.id for row in note_rows)
        grant_result = await self.session.execute(
            select(
                ConfidentialNoteAccessModel.note_id,
                ConfidentialNoteAccessModel.user_id,
            ).where(
                ConfidentialNoteAccessModel.note_id.in_(note_ids),
                ConfidentialNoteAccessModel.revoked_at.is_(None),
            )
        )
        allowed_users_by_note: dict[str, set[str]] = {
            note_id: set() for note_id in note_ids
        }
        for grant in grant_result.all():
            allowed_users_by_note[grant.note_id].add(grant.user_id)

        return [
            ConfidentialNoteAccessFacts(
                note_id=row.id,
                meeting_id=row.meeting_id,
                allowed_user_ids=frozenset(allowed_users_by_note[row.id]),
                is_deleted=row.deleted_at is not None,
            )
            for row in note_rows
        ]

    async def get_confidential_note_by_id(
        self, note_id: str, requesting_user_id: str
    ) -> Optional[ConfidentialNote]:
        active_participant = exists(
            select(1).where(
                MeetingParticipantModel.meeting_id == ConfidentialNoteModel.meeting_id,
                MeetingParticipantModel.user_id == requesting_user_id,
                MeetingParticipantModel.membership_status
                == ParticipantMembershipStatus.ACTIVE,
            )
        )
        active_grant = exists(
            select(1).where(
                ConfidentialNoteAccessModel.note_id == ConfidentialNoteModel.id,
                ConfidentialNoteAccessModel.user_id == requesting_user_id,
                ConfidentialNoteAccessModel.revoked_at.is_(None),
            )
        )
        stmt = (
            select(ConfidentialNoteModel)
            .join(MeetingModel, MeetingModel.id == ConfidentialNoteModel.meeting_id)
            .options(selectinload(ConfidentialNoteModel.access_list))
            .where(
                ConfidentialNoteModel.id == note_id,
                ConfidentialNoteModel.deleted_at.is_(None),
                active_participant,
                or_(MeetingModel.created_by == requesting_user_id, active_grant),
            )
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_note_entity(model) if model is not None else None

    async def grant_note_access(
        self, access: ConfidentialNoteAccess
    ) -> ConfidentialNoteAccess:
        active_grantee = exists(
            select(1).where(
                MeetingParticipantModel.meeting_id == ConfidentialNoteModel.meeting_id,
                MeetingParticipantModel.user_id == access.user_id,
                MeetingParticipantModel.membership_status
                == ParticipantMembershipStatus.ACTIVE,
            )
        )
        authorization_result = await self.session.execute(
            select(ConfidentialNoteModel.id)
            .join(MeetingModel, MeetingModel.id == ConfidentialNoteModel.meeting_id)
            .where(
                ConfidentialNoteModel.id == access.note_id,
                ConfidentialNoteModel.deleted_at.is_(None),
                MeetingModel.created_by == access.granted_by,
                active_grantee,
            )
        )
        if authorization_result.scalar_one_or_none() is None:
            raise PermissionError("Confidential note grant is not permitted")

        existing_result = await self.session.execute(
            select(ConfidentialNoteAccessModel).where(
                ConfidentialNoteAccessModel.note_id == access.note_id,
                ConfidentialNoteAccessModel.user_id == access.user_id,
            )
        )
        model = existing_result.scalar_one_or_none()
        if model is None:
            model = self._to_access_model(access)
            self.session.add(model)
        else:
            model.granted_by = access.granted_by
            model.granted_at = access.granted_at
            model.revoked_at = None

        await self._commit()
        return self._to_access_entity(model)

    async def revoke_note_access(
        self, note_id: str, user_id: str, actor_user_id: str
    ) -> bool:
        result = await self.session.execute(
            select(ConfidentialNoteAccessModel)
            .join(
                ConfidentialNoteModel,
                ConfidentialNoteModel.id == ConfidentialNoteAccessModel.note_id,
            )
            .join(MeetingModel, MeetingModel.id == ConfidentialNoteModel.meeting_id)
            .where(
                ConfidentialNoteAccessModel.note_id == note_id,
                ConfidentialNoteAccessModel.user_id == user_id,
                MeetingModel.created_by == actor_user_id,
            )
        )
        access = result.scalar_one_or_none()
        if access is None:
            return False
        if access.revoked_at is None:
            access.revoked_at = utc_now_naive()
            await self._commit()
        return True
