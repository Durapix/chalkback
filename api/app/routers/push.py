from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app import push
from app.models import PushSubscription, Role
from app.security import DB, CurrentUser

router = APIRouter(prefix="/push", tags=["push"])


class Keys(BaseModel):
    p256dh: str = Field(min_length=1, max_length=255)
    auth: str = Field(min_length=1, max_length=255)


class SubscriptionIn(BaseModel):
    endpoint: str = Field(max_length=1024)
    keys: Keys


class EndpointIn(BaseModel):
    endpoint: str = Field(max_length=1024)


@router.get("/key")
def vapid_key(user: CurrentUser):
    """The public key a browser needs to subscribe to this server's notifications."""
    return {"public_key": push.public_key()}


@router.post("/subscriptions", status_code=204)
def subscribe(body: SubscriptionIn, user: CurrentUser, db: DB):
    """Remember this device for the signed-in student's reminders."""
    if user.role != Role.student:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Students only")
    if not push.is_push_endpoint(body.endpoint):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Not a browser push service")
    sub = db.scalars(
        select(PushSubscription).where(PushSubscription.endpoint == body.endpoint)
    ).first()
    if sub is None:
        sub = PushSubscription(endpoint=body.endpoint)
        db.add(sub)
    sub.user_id, sub.p256dh, sub.auth = user.id, body.keys.p256dh, body.keys.auth
    db.commit()


@router.post("/unsubscribe", status_code=204)
def unsubscribe(body: EndpointIn, user: CurrentUser, db: DB):
    """Forget this device (the student turned notifications off here)."""
    sub = db.scalars(
        select(PushSubscription).where(
            PushSubscription.endpoint == body.endpoint, PushSubscription.user_id == user.id
        )
    ).first()
    if sub is not None:
        db.delete(sub)
        db.commit()
