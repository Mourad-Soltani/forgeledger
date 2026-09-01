"""Multi-user API keys — Mourad.Soltani / ForgeLedger."""

import hashlib
import os
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .database import get_db
from . import models


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def auth_required() -> bool:
    return os.environ.get("FORGELEDGER_REQUIRE_AUTH", "").lower() in {"1", "true", "yes"}


def bootstrap_owner_key(db: Session) -> Optional[str]:
    owner = db.query(models.ApiKey).filter(models.ApiKey.role == "owner").first()
    env_key = os.environ.get("FORGELEDGER_OWNER_API_KEY", "").strip()
    if owner:
        if env_key:
            h = _hash(env_key)
            if owner.key_hash != h:
                owner.key_hash = h
                db.commit()
        return None
    raw = env_key or f"fl_owner_{secrets.token_urlsafe(24)}"
    row = models.ApiKey(name="owner", role="owner", key_hash=_hash(raw), active=True)
    db.add(row)
    db.commit()
    return None if env_key else raw


def create_api_key(db: Session, name: str, role: str = "member") -> dict:
    role = role if role in {"owner", "member", "readonly"} else "member"
    raw = f"fl_{role}_{secrets.token_urlsafe(24)}"
    row = models.ApiKey(name=name or "member", role=role, key_hash=_hash(raw), active=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "name": row.name,
        "role": row.role,
        "key": raw,
        "author": "Mourad.Soltani",
    }


def resolve_key(db: Session, token: str) -> Optional[models.ApiKey]:
    if not token:
        return None
    h = _hash(token.strip())
    return (
        db.query(models.ApiKey)
        .filter(models.ApiKey.key_hash == h, models.ApiKey.active.is_(True))
        .first()
    )


def get_current_principal(request: Request, db: Session = Depends(get_db)):
    if not auth_required():
        return {"role": "owner", "name": "local", "id": None, "auth": False}
    auth = request.headers.get("authorization") or ""
    token = ""
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
    token = token or request.headers.get("x-api-key") or ""
    row = resolve_key(db, token)
    if not row:
        raise HTTPException(401, "Invalid or missing API key")
    return {"role": row.role, "name": row.name, "id": row.id, "auth": True}


def require_role(*roles: str):
    allowed = set(roles) | {"owner"}

    def dep(principal=Depends(get_current_principal)):
        if principal.get("role") not in allowed:
            raise HTTPException(403, "Insufficient role")
        return principal

    return dep
