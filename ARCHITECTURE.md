# Production-Shaped FastAPI Prototype — Architecture Contracts

## 1. API Request/Response Contracts

### Common API conventions

* Base path: `/api/v1`
* Authentication: `app_session` JWT cookie
* The frontend does not send bearer tokens.
* Every response includes or exposes a `request_id`.
* State-changing requests require a CSRF token.
* All resource IDs are opaque strings.
* Authorization failures are decided exclusively by the backend.

### Standard error response

| Field              | Type        | Description                               |
| ------------------ | ----------- | ----------------------------------------- |
| `error.code`       | string      | Stable machine-readable error code        |
| `error.message`    | string      | Safe user-facing explanation              |
| `error.request_id` | string      | Request correlation ID                    |
| `error.details`    | object/null | Optional non-sensitive validation details |

Common error codes:

* `AUTHENTICATION_REQUIRED`
* `SESSION_EXPIRED`
* `CSRF_VALIDATION_FAILED`
* `RESOURCE_NOT_FOUND`
* `PARTICIPANT_ACCESS_REQUIRED`
* `CONFIDENTIAL_NOTE_ACCESS_DENIED`
* `ENTITLEMENT_REQUIRED`
* `ENTITLEMENT_EXPIRED`
* `ACTION_NOT_REGISTERED`
* `ACTION_NOT_ALLOWED`
* `VALIDATION_ERROR`

---

### Authentication contracts

#### `GET /auth/google/start`

Starts Google OIDC authentication.

**Request**

No body.

**Response**

* `302 Redirect` to Google authorization endpoint.
* Backend generates and stores OIDC `state`, `nonce`, and login transaction details.

---

#### `GET /auth/google/callback`

Handles the Google OIDC callback.

**Request query parameters**

| Field               | Required |
| ------------------- | -------: |
| `code`              |      Yes |
| `state`             |      Yes |
| `error`             |       No |
| `error_description` |       No |

**Successful response**

* Validates Google identity.
* Creates or updates the local user.
* Creates an application session.
* Sets the `app_session` cookie.
* Redirects to the application.

**Cookie contract**

| Property   | Value                              |
| ---------- | ---------------------------------- |
| `HttpOnly` | `true`                             |
| `Secure`   | `true` outside local development   |
| `SameSite` | `Lax`                              |
| `Path`     | `/`                                |
| Expiry     | Same as application session expiry |

The frontend never receives or stores the JWT directly.

---

#### `GET /api/v1/session`

Returns the authenticated application session.

**Response**

| Field                   | Type        |
| ----------------------- | ----------- |
| `user.id`               | string      |
| `user.display_name`     | string      |
| `user.email`            | string      |
| `user.avatar_url`       | string/null |
| `session.expires_at`    | datetime    |
| `session.auth_provider` | `"google"`  |
| `csrf_token`            | string      |

The `csrf_token` must be sent in an `X-CSRF-Token` header for state-changing requests.

---

#### `POST /api/v1/auth/logout`

Revokes the application session and clears the cookie.

**Request**

* `X-CSRF-Token` header required.

**Response**

* `204 No Content`
* Clears the `app_session` cookie.

---

### Meeting contracts

#### `GET /api/v1/meetings`

Returns meetings visible to the authenticated user.

**Query parameters**

| Field    | Type        | Default |
| -------- | ----------- | ------- |
| `cursor` | string/null | `null`  |
| `limit`  | integer     | `20`    |
| `status` | string/null | `null`  |

**Response**

| Field         | Type                       |
| ------------- | -------------------------- |
| `items`       | array of meeting summaries |
| `next_cursor` | string/null                |

Meeting summary:

| Field                | Type          |
| -------------------- | ------------- |
| `id`                 | string        |
| `title`              | string        |
| `starts_at`          | datetime      |
| `ends_at`            | datetime/null |
| `organizer`          | user summary  |
| `participant_status` | string        |
| `transcript_status`  | string        |
| `recording_status`   | string        |

Only meetings where the user is the organizer or an active participant are returned.

---

#### `GET /api/v1/meetings/{meeting_id}`

Returns meeting metadata.

**Response**

| Field                      | Type                            |
| -------------------------- | ------------------------------- |
| `id`                       | string                          |
| `title`                    | string                          |
| `starts_at`                | datetime                        |
| `ends_at`                  | datetime/null                   |
| `organizer`                | user summary                    |
| `participants`             | array of participant summaries  |
| `transcript_status`        | string                          |
| `recording_status`         | string                          |
| `current_user_permissions` | array of permission identifiers |

`current_user_permissions` is informational for UI rendering. It is not an authorization grant.

---

### Transcript contracts

#### `GET /api/v1/meetings/{meeting_id}/transcript`

Returns transcript content to active meeting participants.

**Query parameters**

| Field    | Type        | Default |
| -------- | ----------- | ------- |
| `cursor` | string/null | `null`  |
| `limit`  | integer     | `100`   |

**Response**

| Field           | Type                                   |
| --------------- | -------------------------------------- |
| `meeting_id`    | string                                 |
| `transcript_id` | string                                 |
| `status`        | `PROCESSING`, `AVAILABLE`, or `FAILED` |
| `language`      | string/null                            |
| `segments`      | array                                  |
| `next_cursor`   | string/null                            |

Transcript segment:

| Field                  | Type         |
| ---------------------- | ------------ |
| `id`                   | string       |
| `sequence_number`      | integer      |
| `speaker_display_name` | string/null  |
| `start_ms`             | integer      |
| `end_ms`               | integer/null |
| `text`                 | string       |

**Authorization requirement**

The current user must have an active participant relationship with the meeting.

---

### Confidential-note contracts

#### `GET /api/v1/meetings/{meeting_id}/confidential-notes`

Returns only notes that the authenticated user may access.

**Response**

| Field        | Type                        |
| ------------ | --------------------------- |
| `items`      | array of confidential notes |
| `meeting_id` | string                      |

Confidential note:

| Field           | Type                                       |
| --------------- | ------------------------------------------ |
| `id`            | string                                     |
| `title`         | string                                     |
| `body`          | string                                     |
| `created_by`    | user summary                               |
| `created_at`    | datetime                                   |
| `updated_at`    | datetime                                   |
| `access_source` | `ORGANIZER`, `USER_GRANT`, or `ROLE_GRANT` |

A user cannot infer that inaccessible confidential notes exist.

---

#### `POST /api/v1/meetings/{meeting_id}/confidential-notes`

Creates a confidential note.

**Request**

| Field              | Type             | Required |
| ------------------ | ---------------- | -------: |
| `title`            | string           |      Yes |
| `body`             | string           |      Yes |
| `allowed_user_ids` | array of strings |       No |
| `allowed_role_ids` | array of strings |       No |

**Response**

* `201 Created`
* Returns the created note and its access configuration.

**Default policy**

Only the meeting organizer may create confidential notes.

---

#### `PATCH /api/v1/meetings/{meeting_id}/confidential-notes/{note_id}`

Updates note content.

**Request**

| Field   | Type        |
| ------- | ----------- |
| `title` | string/null |
| `body`  | string/null |

Only the meeting organizer may update the note.

---

#### `PUT /api/v1/meetings/{meeting_id}/confidential-notes/{note_id}/access`

Replaces the note’s explicit access configuration.

**Request**

| Field              | Type             |
| ------------------ | ---------------- |
| `allowed_user_ids` | array of strings |
| `allowed_role_ids` | array of strings |

Only the meeting organizer may change access grants.

All explicitly granted users must be active meeting participants.

---

#### `DELETE /api/v1/meetings/{meeting_id}/confidential-notes/{note_id}`

Deletes or soft-deletes the note.

Only the meeting organizer may perform this action.

**Response**

* `204 No Content`

---

### Recording contracts

#### `GET /api/v1/meetings/{meeting_id}/recordings`

Returns recording metadata, not recording content.

**Response item**

| Field                   | Type                                                                         |
| ----------------------- | ---------------------------------------------------------------------------- |
| `id`                    | string                                                                       |
| `title`                 | string                                                                       |
| `duration_ms`           | integer/null                                                                 |
| `created_at`            | datetime                                                                     |
| `processing_status`     | string                                                                       |
| `access_status`         | `AVAILABLE`, `ENTITLEMENT_REQUIRED`, `ENTITLEMENT_EXPIRED`, or `UNAVAILABLE` |
| `required_entitlements` | array of entitlement summaries                                               |

Meeting participation is required to view recording metadata.

---

#### `POST /api/v1/recordings/{recording_id}/access`

Requests access to the recording.

**Request**

No body beyond the authenticated session and CSRF token.

**Successful response**

| Field          | Type     |
| -------------- | -------- |
| `recording_id` | string   |
| `playback_url` | string   |
| `expires_at`   | datetime |
| `request_id`   | string   |

The playback URL must be short-lived.

**Authorization requirements**

The user must:

1. Be an active meeting participant.
2. Have every required entitlement.
3. Have entitlements in a verified and non-expired state.

**Denied response**

* `403 ENTITLEMENT_REQUIRED`
* May include a safe `upgrade_path`.
* Must not include the recording URL.

---

### Assistant action contracts

#### `GET /api/v1/assistant/actions`

Returns registered and enabled action descriptors.

This endpoint does not grant permission to execute an action.

**Response item**

| Field          | Type    |
| -------------- | ------- |
| `action_id`    | string  |
| `version`      | integer |
| `display_name` | string  |
| `description`  | string  |
| `input_schema` | object  |
| `sensitivity`  | string  |
| `output_mode`  | string  |

---

#### `POST /api/v1/assistant/actions/execute`

Executes a registered assistant action.

**Request**

| Field                  | Type        |          Required |
| ---------------------- | ----------- | ----------------: |
| `action_id`            | string      |               Yes |
| `arguments`            | object      |               Yes |
| `context.meeting_id`   | string/null | Depends on action |
| `context.recording_id` | string/null | Depends on action |
| `context.note_id`      | string/null | Depends on action |
| `client_request_id`    | string/null |                No |

**Navigation-only response**

| Field                                  | Type           |
| -------------------------------------- | -------------- |
| `execution_id`                         | string         |
| `action_id`                            | string         |
| `outcome`                              | `"NAVIGATION"` |
| `navigation.path`                      | string         |
| `navigation.method`                    | `"GET"`        |
| `navigation.requires_user_interaction` | boolean        |
| `request_id`                           | string         |

For sensitive resources, the action response must never contain:

* Transcript text
* Confidential-note title or body
* Recording URLs
* Recording content
* Entitlement secrets
* Hidden participant information

The assistant receives only a navigation directive.

---

## 2. Domain Entities

### User

Represents the application identity.

Core attributes:

* `user_id`
* `display_name`
* `primary_email`
* `avatar_url`
* `status`
* `created_at`
* `updated_at`

Invariants:

* One active application user may have multiple external identities.
* A disabled user cannot create new sessions.
* Email alone is not treated as the immutable external identity.

---

### ExternalIdentity

Maps an OIDC identity to an application user.

Core attributes:

* `external_identity_id`
* `user_id`
* `provider`
* `provider_subject`
* `provider_email`
* `email_verified`
* `last_authenticated_at`

Invariants:

* `(provider, provider_subject)` is globally unique.
* Google’s OIDC `sub` is the authoritative external identifier.
* Authentication requires a verified provider identity according to application policy.

---

### AuthSession

Represents a revocable application JWT session.

Core attributes:

* `session_id`
* `user_id`
* `jwt_id`
* `issued_at`
* `expires_at`
* `revoked_at`
* `last_seen_at`

Invariants:

* JWT identifiers are unique.
* Expired or revoked sessions cannot authorize requests.
* Raw JWT values are never stored.

---

### Meeting

Core attributes:

* `meeting_id`
* `title`
* `organizer_user_id`
* `starts_at`
* `ends_at`
* `status`
* `created_at`
* `updated_at`

Invariants:

* The organizer must also be an active meeting participant.
* Every transcript, confidential note, and recording belongs to exactly one meeting.

---

### MeetingParticipant

Represents a user’s meeting-scoped membership.

Core attributes:

* `participant_id`
* `meeting_id`
* `user_id`
* `membership_status`
* `joined_at`
* `removed_at`

Membership statuses:

* `ACTIVE`
* `REMOVED`
* `REVOKED`

Invariants:

* `(meeting_id, user_id)` is unique.
* A removed or revoked participant loses transcript and recording access.
* Removing a participant also invalidates their user-specific confidential-note grants for authorization purposes.

---

### MeetingRole

Represents a meeting-scoped role definition.

Example role identifiers:

* `CO_HOST`
* `LEGAL_REVIEWER`
* `MANAGER`
* `MINUTES_REVIEWER`

Core attributes:

* `role_id`
* `role_code`
* `display_name`
* `description`

Roles are not automatically permissions. Policies determine what each role can access.

---

### ParticipantRoleAssignment

Assigns meeting roles to participants.

Core attributes:

* `participant_id`
* `role_id`
* `assigned_by_user_id`
* `assigned_at`
* `revoked_at`

Invariants:

* Only active participants may hold meeting roles.
* Role assignments are evaluated only within the relevant meeting.

---

### Transcript

Core attributes:

* `transcript_id`
* `meeting_id`
* `status`
* `language`
* `generated_at`
* `version`

Invariants:

* A meeting has at most one active transcript version.
* Transcript access depends on current meeting participation.

---

### TranscriptSegment

Core attributes:

* `segment_id`
* `transcript_id`
* `sequence_number`
* `speaker_user_id`
* `speaker_display_name`
* `start_ms`
* `end_ms`
* `text`

Invariants:

* Sequence numbers are unique within a transcript.
* A segment cannot exist without a transcript.

---

### ConfidentialNote

Core attributes:

* `note_id`
* `meeting_id`
* `created_by_user_id`
* `title`
* `body`
* `created_at`
* `updated_at`
* `deleted_at`

Invariants:

* Only the organizer may create, modify, delete, or grant access by default.
* The organizer always has access.
* Other users require an active explicit user grant or matching role grant.
* A note cannot be accessed solely because a user can access the meeting transcript.

---

### ConfidentialNoteUserGrant

Core attributes:

* `note_id`
* `user_id`
* `granted_by_user_id`
* `granted_at`
* `revoked_at`

Invariants:

* The granted user must be an active participant in the same meeting.
* A revoked grant does not authorize access.
* A user grant does not survive participant removal.

---

### ConfidentialNoteRoleGrant

Core attributes:

* `note_id`
* `role_id`
* `granted_by_user_id`
* `granted_at`
* `revoked_at`

Invariants:

* The role is evaluated against active role assignments in the note’s meeting.
* Role membership in another meeting does not grant access.

---

### Recording

Core attributes:

* `recording_id`
* `meeting_id`
* `title`
* `storage_reference`
* `duration_ms`
* `processing_status`
* `created_at`

Invariants:

* Storage references are internal and never exposed directly.
* Playback access is issued only after authorization and entitlement verification.
* Assistant actions never receive playback URLs.

---

### EntitlementDefinition

Defines a recognized entitlement.

Core attributes:

* `entitlement_id`
* `entitlement_key`
* `display_name`
* `description`
* `verification_provider`
* `enabled`

Example entitlement keys:

* `RECORDING_ACCESS`
* `PREMIUM_MEETING_ARCHIVE`
* `ORGANIZATION_RECORDING_LICENSE`

---

### UserEntitlement

Represents a verified entitlement held by a user.

Core attributes:

* `user_entitlement_id`
* `user_id`
* `entitlement_id`
* `status`
* `source_reference`
* `verified_at`
* `expires_at`
* `revoked_at`

Statuses:

* `PENDING`
* `VERIFIED`
* `EXPIRED`
* `REVOKED`
* `FAILED_VERIFICATION`

Invariants:

* Only `VERIFIED` and non-expired entitlements authorize recording access.
* A cached entitlement must not be used beyond its verification freshness policy.

---

### RecordingEntitlementRequirement

Associates a recording with required entitlements.

Core attributes:

* `recording_id`
* `entitlement_id`
* `requirement_mode`

Initial prototype requirement mode:

* `ALL_REQUIRED`

---

### AssistantActionDefinition

Represents a backend-registered action that the assistant may request.

Core attributes:

* `action_id`
* `version`
* `display_name`
* `description`
* `effect_type`
* `sensitivity`
* `output_mode`
* `input_schema`
* `required_permissions`
* `route_template`
* `enabled`

Invariants:

* Action IDs are immutable and unique.
* Unregistered action IDs are always rejected.
* Sensitive actions must use `NAVIGATION_ONLY`.
* Action definitions never override backend authorization policies.

---

### AuditEvent

Records security-relevant decisions.

Core attributes:

* `audit_event_id`
* `request_id`
* `actor_user_id`
* `event_type`
* `resource_type`
* `resource_id`
* `action_id`
* `authorization_decision`
* `decision_reason`
* `created_at`

Sensitive content must not be written to audit logs.

---

## 3. Repository Interfaces

Repository interfaces expose persistence operations without containing authorization or application workflow logic.

### UserRepository

Required operations:

* Find user by application ID.
* Find user by verified external identity.
* Create user.
* Update user profile.
* Disable or re-enable user.

---

### ExternalIdentityRepository

Required operations:

* Find by provider and provider subject.
* Create external identity.
* Update provider profile information.
* Record successful authentication.

---

### AuthSessionRepository

Required operations:

* Create session record.
* Find active session by JWT ID.
* Revoke session.
* Revoke all sessions for a user.
* Update last-seen timestamp.
* Remove or archive expired sessions.

---

### MeetingRepository

Required operations:

* Find meeting by ID.
* List meetings visible through participant membership.
* Create or update meeting metadata.
* Verify organizer relationship.

---

### MeetingParticipantRepository

Required operations:

* Find participant by meeting and user.
* Check active participation.
* List meeting participants.
* Add participant.
* Remove or revoke participant membership.

---

### MeetingRoleRepository

Required operations:

* Find role by ID or role code.
* List roles assigned to a participant.
* Assign role to participant.
* Revoke role assignment.
* Check whether a user holds a role in a meeting.

---

### TranscriptRepository

Required operations:

* Find transcript by meeting.
* Retrieve paginated transcript segments.
* Store transcript metadata.
* Store ordered transcript segments.
* Update transcript processing status.

---

### ConfidentialNoteRepository

Required operations:

* Find note by ID and meeting.
* List notes potentially accessible to a user.
* Create note.
* Update note.
* Soft-delete note.

The repository may filter data, but the service layer remains responsible for final authorization.

---

### ConfidentialNoteGrantRepository

Required operations:

* List active user grants for a note.
* List active role grants for a note.
* Replace note user grants.
* Replace note role grants.
* Check direct user grant.
* Check role-based grant.
* Revoke grants.

---

### RecordingRepository

Required operations:

* Find recording by ID.
* List recordings for a meeting.
* Resolve internal storage reference.
* Update recording processing status.

Internal storage references must not be returned outside the infrastructure boundary.

---

### EntitlementRepository

Required operations:

* Find entitlement definition by key.
* List required entitlements for a recording.
* Find active user entitlements.
* Store verification result.
* Revoke entitlement.
* Determine whether re-verification is required.

---

### AssistantActionRegistryRepository

Required operations:

* Find enabled action by action ID.
* List enabled action definitions.
* Resolve a specific action version.
* Register or update an action definition.
* Disable an action.

Action lookup must use exact identifiers, not fuzzy matching.

---

### AuditRepository

Required operations:

* Append audit event.
* Search audit events by request, user, resource, or action.
* Preserve immutable security-event history.

---

### UnitOfWork Interface

Coordinates atomic operations involving multiple repositories.

Required capabilities:

* Begin transaction.
* Commit transaction.
* Roll back transaction.
* Expose repositories participating in the transaction.

Use cases such as creating a note with grants must be atomic.

---

## 4. Service Interfaces

### OIDCAuthenticationService

Responsibilities:

* Start Google OIDC login.
* Validate callback state and nonce.
* Exchange the authorization code.
* Validate the Google ID token.
* Resolve or create the local user.
* Return an authenticated application identity.

It must not issue frontend authorization decisions.

---

### ApplicationSessionService

Responsibilities:

* Create application JWT sessions.
* Validate JWT claims and session state.
* Rotate or revoke sessions.
* Generate CSRF tokens.
* Clear expired sessions.

Output:

* Authenticated principal
* Session expiry
* Cookie instructions
* CSRF token

---

### MeetingService

Responsibilities:

* List meetings visible to the current user.
* Retrieve meeting metadata.
* Manage participant membership.
* Resolve organizer and participant relationships.

---

### AuthorizationService

Primary authorization source of truth.

Required decisions:

* `can_view_meeting`
* `can_view_transcript`
* `can_view_confidential_note`
* `can_create_confidential_note`
* `can_manage_confidential_note`
* `can_view_recording_metadata`
* `can_access_recording`
* `can_execute_action`

Every decision returns:

* `allowed`
* Stable decision reason
* Resource scope
* Policy version

---

### TranscriptService

Responsibilities:

* Retrieve transcript metadata.
* Retrieve paginated transcript segments.
* Enforce participant-only access through `AuthorizationService`.
* Return transcript content only through transcript APIs.

Transcript content must not be returned through sensitive assistant actions.

---

### ConfidentialNoteService

Responsibilities:

* List only accessible confidential notes.
* Retrieve an authorized note.
* Create, update, or delete notes.
* Replace user and role grants.
* Validate that granted users belong to the meeting.
* Audit access and access-policy changes.

---

### EntitlementVerificationService

Responsibilities:

* Resolve required entitlements.
* Verify entitlement status with the authoritative source.
* Apply verification-freshness rules.
* Store the latest verification outcome.
* Return entitlement decision details without exposing provider secrets.

---

### RecordingAccessService

Responsibilities:

* Verify active meeting participation.
* Request entitlement verification.
* Resolve the internal recording location.
* Generate a short-lived playback URL.
* Audit recording-access decisions.

A playback URL is returned only to the browser-facing recording access endpoint.

---

### AssistantActionService

Responsibilities:

* Resolve an exact registered action ID.
* Validate arguments against the registered input schema.
* Resolve referenced resources.
* Request backend authorization.
* Enforce the registered output mode.
* Produce a navigation directive.
* Audit the action request and authorization outcome.

For sensitive actions, this service must not call data-returning transcript, note, or recording-content methods.

---

### AuditService

Responsibilities:

* Record authentication events.
* Record authorization decisions.
* Record note access and grant changes.
* Record recording-access decisions.
* Record assistant action execution.
* Redact sensitive content before persistence.

---

## 5. Action Registry Schema

### Required schema fields

| Field                      | Type        | Purpose                                       |
| -------------------------- | ----------- | --------------------------------------------- |
| `action_id`                | string      | Immutable registered identifier               |
| `version`                  | integer     | Action-contract version                       |
| `display_name`             | string      | Human-readable name                           |
| `description`              | string      | Assistant-facing purpose                      |
| `effect_type`              | enum        | `NAVIGATE`, `READ_NON_SENSITIVE`, or `MUTATE` |
| `sensitivity`              | enum        | `PUBLIC`, `INTERNAL`, `SENSITIVE`             |
| `output_mode`              | enum        | `DATA`, `METADATA_ONLY`, or `NAVIGATION_ONLY` |
| `input_schema`             | object      | Allowed argument names and types              |
| `required_context`         | array       | Required resource identifiers                 |
| `required_permissions`     | array       | Backend permission identifiers                |
| `route_template`           | string/null | Navigation target template                    |
| `entitlement_requirements` | array       | Required entitlement keys                     |
| `enabled`                  | boolean     | Whether execution is permitted                |
| `audit_level`              | enum        | `STANDARD` or `SECURITY_CRITICAL`             |
| `created_at`               | datetime    | Registration timestamp                        |
| `updated_at`               | datetime    | Last definition update                        |

### Registry constraints

1. Action IDs use namespaced identifiers.

   Examples:

   * `meeting.transcript.open`
   * `meeting.confidential_notes.open`
   * `meeting.recording.open`
   * `meeting.participants.open`

2. `action_id` and `version` form a unique action definition.

3. An unknown or disabled action ID is rejected before any resource lookup.

4. `SENSITIVE` actions must use `NAVIGATION_ONLY`.

5. A sensitive action result contains only:

   * Authorized route
   * Action execution ID
   * Resource identifier already provided by the user or trusted application context
   * Safe navigation metadata

6. The registry defines what an action may request. It does not decide whether a user may perform it.

7. Route templates may contain only registered variables.

8. The assistant cannot provide arbitrary URLs.

9. Entitlement requirements in the registry are additional requirements; they cannot bypass resource authorization.

---

## 6. Authorization Policies

### Global principles

#### Deny by default

Any action without an explicit allow policy is rejected.

#### Backend authority

The backend is the sole authorization source of truth.

The following are never treated as authorization evidence:

* Hidden or visible frontend buttons
* Assistant instructions
* LLM claims
* Client-provided roles
* Client-provided participant status
* Client-provided entitlement status
* Action registry visibility

#### Resource-scoped authorization

Permissions are evaluated against the requested meeting, note, transcript, or recording.

A role in one meeting has no effect in another meeting.

#### Current-state authorization

Every sensitive request checks the latest:

* Session status
* User status
* Meeting participation
* Organizer relationship
* Role assignments
* Note grants
* Entitlement status
* Action registration state

---

### Policy matrix

| Resource or action                                   |           Organizer | Active participant | Explicit user grant | Matching role grant | Verified entitlement |
| ---------------------------------------------------- | ------------------: | -----------------: | ------------------: | ------------------: | -------------------: |
| View meeting metadata                                |                 Yes |                Yes |                 N/A |                 N/A |                   No |
| View transcript                                      |                 Yes |                Yes |                 N/A |                 N/A |                   No |
| View confidential note                               |                 Yes |                 No |                 Yes |                 Yes |                   No |
| Create confidential note                             |                 Yes |                 No |                  No |                  No |                   No |
| Update/delete confidential note                      |                 Yes |                 No |                  No |                  No |                   No |
| Manage note grants                                   |                 Yes |                 No |                  No |                  No |                   No |
| View recording metadata                              |                 Yes |                Yes |                 N/A |                 N/A |                   No |
| Access recording playback                            | Yes, if participant |                Yes |                 N/A |                 N/A |                  Yes |
| Navigate to transcript page through assistant        |                 Yes |                Yes |                 N/A |                 N/A |                   No |
| Navigate to confidential-note page through assistant |                 Yes |                 No |                 Yes |                 Yes |                   No |
| Navigate to recording page through assistant         | Yes, if participant |                Yes |                 N/A |                 N/A |       Page-dependent |
| Receive sensitive content from assistant action      |                  No |                 No |                  No |                  No |                   No |

---

### Transcript policy

Allow when:

* Session is valid.
* User is active.
* Meeting exists.
* User has active meeting participation.

Deny when:

* Participant membership is removed or revoked.
* The meeting is outside the user’s visible resource scope.

The organizer is treated as a participant, not as an authorization bypass.

---

### Confidential-note policy

Allow note access when at least one condition is true:

1. Current user is the meeting organizer.
2. Current user has an active user-specific grant.
3. Current user has an active role assignment matching an active note role grant.

Additional conditions:

* User must still be an active meeting participant.
* Note must belong to the requested meeting.
* Deleted notes are never returned.
* Grants cannot be inferred from transcript access.
* Organizer access cannot be removed by a grant update.

Only the organizer may manage note content and access grants in the initial prototype.

---

### Recording policy

Recording playback requires all of the following:

1. Valid authenticated session.
2. Active meeting participation.
3. Recording belongs to the meeting.
4. Recording is in an accessible processing state.
5. Every required entitlement is `VERIFIED`.
6. No required entitlement is expired or revoked.
7. Verification is fresh according to policy.

A previously issued playback URL does not establish future entitlement.

---

### Assistant action policy

Execution sequence:

1. Authenticate the application session.
2. Resolve the exact registered action ID.
3. Validate action arguments.
4. Resolve referenced resources from backend data.
5. Evaluate resource authorization.
6. Evaluate entitlement requirements.
7. Enforce the action’s output mode.
8. Record an audit event.
9. Return the allowed result.

For sensitive actions:

* Output is always navigation-only.
* The assistant may direct the browser to an authorized page.
* The target page performs its own authorization check.
* Authorization is checked again when the page requests data.
* No transcript, confidential note, or recording content is passed through the assistant response.

---

### Resource-existence protection

Use `404 RESOURCE_NOT_FOUND` when revealing that a resource exists would expose information outside the user’s meeting scope.

Use `403` when:

* The resource is already legitimately visible to the user.
* Access is denied because of a clear additional requirement such as recording entitlement.

---

### Frontend policy

The basic HTML/CSS/JavaScript frontend may:

* Show or hide controls based on returned permission hints.
* Navigate using backend-provided paths.
* Display entitlement-upgrade prompts.
* Send CSRF tokens.

The frontend may not:

* Decide whether a user is an organizer.
* Trust role information from browser state.
* Construct sensitive action results.
* Read or store the application JWT.
* Convert an assistant response into sensitive content access without calling the backend.

---

## 7. Database Table Relationships

### Identity and sessions

| Parent  | Relationship | Child                 |
| ------- | ------------ | --------------------- |
| `users` | One-to-many  | `external_identities` |
| `users` | One-to-many  | `auth_sessions`       |

Key constraints:

* `external_identities(provider, provider_subject)` is unique.
* `auth_sessions.jwt_id` is unique.
* `auth_sessions.user_id` references `users.id`.

---

### Meetings and participants

| Parent     | Relationship             | Child                  |
| ---------- | ------------------------ | ---------------------- |
| `users`    | One-to-many as organizer | `meetings`             |
| `meetings` | One-to-many              | `meeting_participants` |
| `users`    | One-to-many              | `meeting_participants` |

`meeting_participants` is the join table between meetings and users.

Key constraints:

* `meeting_participants(meeting_id, user_id)` is unique.
* `meetings.organizer_user_id` references `users.id`.
* The organizer must have a corresponding active participant row.

---

### Meeting roles

| Parent                 | Relationship            | Child                       |
| ---------------------- | ----------------------- | --------------------------- |
| `meeting_participants` | One-to-many             | `meeting_participant_roles` |
| `meeting_roles`        | One-to-many             | `meeting_participant_roles` |
| `users`                | One-to-many as assigner | `meeting_participant_roles` |

Key constraint:

* An active `(participant_id, role_id)` assignment is unique.

---

### Transcripts

| Parent        | Relationship                         | Child                 |
| ------------- | ------------------------------------ | --------------------- |
| `meetings`    | One-to-one or one-to-many by version | `transcripts`         |
| `transcripts` | One-to-many                          | `transcript_segments` |
| `users`       | Optional one-to-many as speaker      | `transcript_segments` |

Key constraints:

* One active transcript version per meeting.
* `transcript_segments(transcript_id, sequence_number)` is unique.

---

### Confidential notes and grants

| Parent               | Relationship           | Child                           |
| -------------------- | ---------------------- | ------------------------------- |
| `meetings`           | One-to-many            | `confidential_notes`            |
| `users`              | One-to-many as creator | `confidential_notes`            |
| `confidential_notes` | One-to-many            | `confidential_note_user_grants` |
| `users`              | One-to-many as grantee | `confidential_note_user_grants` |
| `confidential_notes` | One-to-many            | `confidential_note_role_grants` |
| `meeting_roles`      | One-to-many            | `confidential_note_role_grants` |

Key constraints:

* `confidential_note_user_grants(note_id, user_id)` is unique for active grants.
* `confidential_note_role_grants(note_id, role_id)` is unique for active grants.
* Application validation ensures user grants target participants of the same meeting.
* Role grants are evaluated only against role assignments in the note’s meeting.

---

### Recordings and entitlements

| Parent                    | Relationship | Child                                |
| ------------------------- | ------------ | ------------------------------------ |
| `meetings`                | One-to-many  | `recordings`                         |
| `recordings`              | One-to-many  | `recording_entitlement_requirements` |
| `entitlement_definitions` | One-to-many  | `recording_entitlement_requirements` |
| `users`                   | One-to-many  | `user_entitlements`                  |
| `entitlement_definitions` | One-to-many  | `user_entitlements`                  |

`recording_entitlement_requirements` is the join table between recordings and entitlement definitions.

Key constraints:

* `entitlement_definitions.entitlement_key` is unique.
* `recording_entitlement_requirements(recording_id, entitlement_id)` is unique.
* Active user-entitlement uniqueness is defined by user, entitlement and entitlement scope.
* Raw provider verification secrets are not stored in user-facing tables.

---

### Assistant actions and audit

| Parent                                      | Relationship                  | Child          |
| ------------------------------------------- | ----------------------------- | -------------- |
| `assistant_action_definitions`              | One-to-many                   | `audit_events` |
| `users`                                     | One-to-many as actor          | `audit_events` |
| `auth_sessions`                             | One-to-many                   | `audit_events` |
| Meetings, notes, transcripts and recordings | Logical polymorphic reference | `audit_events` |

Recommended action key:

* `assistant_action_definitions(action_id, version)` is unique.

Audit-resource references use:

* `resource_type`
* `resource_id`

The audit table does not contain transcript text, confidential-note bodies, JWTs, playback URLs, or entitlement-provider secrets.

---

### Main relationship flow

`users`
→ authenticate through `external_identities`
→ receive revocable `auth_sessions`
→ join `meetings` through `meeting_participants`
→ receive meeting-scoped roles through `meeting_participant_roles`
→ access `transcripts` through participant policy
→ access `confidential_notes` through organizer, user grants, or role grants
→ access `recordings` through participant policy plus verified `user_entitlements`
→ invoke only registered `assistant_action_definitions`
→ produce immutable `audit_events` for sensitive decisions.
