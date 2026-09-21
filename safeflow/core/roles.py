"""Generic role-based access control and response redaction.

Enforces field-level redaction based on Pydantic field annotations without
requiring core to import or know about specific plugin models.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class UserRole(str, Enum):
    CREATOR = "creator"
    ANALYST = "analyst"
    ADMIN = "admin"


class CreatorStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    REJECTED = "REJECTED"


class CreatorResponse(BaseModel):
    """Sanitized, non-revealing response presented to end-users/creators."""
    model_config = ConfigDict(extra="forbid")
    status: CreatorStatus
    message: str
    media_id: str | None = None
    appeal_token: str | None = None


class RoleRedactor:
    """Generic redactor inspecting field metadata on Pydantic models."""

    @classmethod
    def redact(cls, data: BaseModel | dict[str, Any], role: UserRole | str) -> dict[str, Any]:
        """Redact fields from a Pydantic model or dict according to caller role."""
        if isinstance(role, str):
            role = UserRole(role.lower())

        if isinstance(data, BaseModel):
            return cls._redact_model(data, role)
        elif isinstance(data, dict):
            return cls._redact_dict(data, role)
        elif isinstance(data, list):
            return [cls.redact(item, role) if isinstance(item, (BaseModel, dict)) else item for item in data]  # type: ignore[return-value]
        return data  # type: ignore[return-value]

    @classmethod
    def _redact_model(cls, model: BaseModel, role: UserRole) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for field_name, field_info in model.model_fields.items():
            # Check visibility metadata
            extra = field_info.json_schema_extra
            visibility = None
            if isinstance(extra, dict):
                visibility = extra.get("visibility")

            # Determine if current role can view this field
            if not cls._can_view(role, visibility):
                continue

            val = getattr(model, field_name)
            if isinstance(val, BaseModel):
                result[field_name] = cls._redact_model(val, role)
            elif isinstance(val, list):
                result[field_name] = [
                    cls._redact_model(x, role) if isinstance(x, BaseModel)
                    else (cls._redact_dict(x, role) if isinstance(x, dict) else x)
                    for x in val
                ]
            elif isinstance(val, dict):
                result[field_name] = cls._redact_dict(val, role)
            else:
                result[field_name] = val

        return result

    @classmethod
    def _redact_dict(cls, data: dict[str, Any], role: UserRole) -> dict[str, Any]:
        # For plain dicts, strip common analyst keys if role is CREATOR
        if role == UserRole.CREATOR:
            forbidden_keys = {
                "nudity_score", "explicit_score", "suggestive_score", "ocr_explicit_text",
                "backend_scores", "model_name", "model_version", "reasons", "evidence",
                "counter_evidence", "families_triggered", "tags", "scores", "internal_tag",
                "suggestive_presentation", "raw_signals"
            }
            return {
                k: cls._redact_item(v, role)
                for k, v in data.items()
                if k not in forbidden_keys and not k.startswith("_")
            }
        elif role == UserRole.ANALYST:
            # Analysts can see everything except admin-exclusive keys
            return {
                k: cls._redact_item(v, role)
                for k, v in data.items()
                if not k.startswith("_admin")
            }
        return data

    @classmethod
    def _redact_item(cls, item: Any, role: UserRole) -> Any:
        if isinstance(item, BaseModel):
            return cls._redact_model(item, role)
        elif isinstance(item, dict):
            return cls._redact_dict(item, role)
        elif isinstance(item, list):
            return [cls._redact_item(x, role) for x in item]
        return item

    @classmethod
    def _can_view(cls, role: UserRole, visibility: str | None) -> bool:
        if visibility is None or visibility == "public":
            return True
        if visibility == "analyst":
            return role in (UserRole.ANALYST, UserRole.ADMIN)
        if visibility == "admin":
            return role == UserRole.ADMIN
        return True

    @classmethod
    def to_creator_response(
        cls,
        decision: str,
        media_id: str | None = None,
        appeal_token: str | None = None
    ) -> CreatorResponse:
        """Create a standardized, non-revealing response for a creator upload."""
        dec = decision.upper()
        if dec in ("ALLOW", "ALLOW_TAGGED"):
            return CreatorResponse(
                status=CreatorStatus.ACCEPTED,
                message="Your profile image has been approved and published.",
                media_id=media_id
            )
        elif dec == "REVIEW":
            return CreatorResponse(
                status=CreatorStatus.UNDER_REVIEW,
                message="Your profile image is pending review by our moderation team. A default placeholder will be displayed in the interim.",
                media_id=media_id,
                appeal_token=appeal_token
            )
        else:  # BLOCK
            return CreatorResponse(
                status=CreatorStatus.REJECTED,
                message="The uploaded image does not meet community guidelines.",
                media_id=media_id,
                appeal_token=appeal_token
            )
