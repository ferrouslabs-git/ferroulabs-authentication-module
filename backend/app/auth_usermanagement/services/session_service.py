"""Session revocation service functions."""
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from ..models.session import Session as AuthSession


def utc_now() -> datetime:
    """Return naive UTC datetime compatible with existing DB DateTime columns."""
    return datetime.now(UTC).replace(tzinfo=None)


def revoke_user_session(db: Session, user_id: UUID, session_id: UUID) -> AuthSession | None:
    """Revoke a specific session if it belongs to the user and is active."""
    auth_session = db.query(AuthSession).filter(
        AuthSession.id == session_id,
        AuthSession.user_id == user_id,
        AuthSession.revoked_at.is_(None),
    ).first()

    if not auth_session:
        return None

    auth_session.revoked_at = utc_now()
    db.commit()
    db.refresh(auth_session)
    return auth_session


def revoke_all_user_sessions(
    db: Session,
    user_id: UUID,
    except_session_id: UUID | None = None,
) -> int:
    """Revoke all active sessions for a user and return number revoked."""
    query = db.query(AuthSession).filter(
        AuthSession.user_id == user_id,
        AuthSession.revoked_at.is_(None),
    )

    if except_session_id:
        query = query.filter(AuthSession.id != except_session_id)

    sessions = query.all()
    if not sessions:
        return 0

    now = utc_now()
    for auth_session in sessions:
        auth_session.revoked_at = now

    db.commit()
    return len(sessions)
