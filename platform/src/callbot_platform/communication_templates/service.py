"""Communication template CRUD, seed, render, and NotificationService enqueue."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.communication_templates.constants import (
    ALL_TEMPLATE_KEYS,
    EMAIL_TEMPLATE_KEYS,
    SMS_TEMPLATE_KEYS,
    TEMPLATE_VARIABLES,
    TemplateStatus,
    VersionStatus,
)
from callbot_platform.communication_templates.context import (
    build_template_context,
    preview_context,
)
from callbot_platform.communication_templates.defaults import DEFAULT_TEMPLATES
from callbot_platform.communication_templates.errors import CommunicationTemplateError
from callbot_platform.communication_templates.preferences import customer_allows
from callbot_platform.communication_templates.renderer import (
    render,
    validate_template_text,
)
from callbot_platform.communication_templates.serialize import (
    serialize_template,
)
from callbot_platform.db.models import Customer, CustomerPhone
from callbot_platform.db.models.communication_templates import (
    CommunicationTemplate,
    CommunicationTemplateVersion,
)
from callbot_platform.scheduling.notifications import NotificationService
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)


class CommunicationTemplateService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def ensure_defaults(self, tenant_id: UUID, *, actor: str = "system") -> int:
        existing = {
            (r.channel, r.template_key)
            for r in self._session.scalars(
                select(CommunicationTemplate).where(
                    CommunicationTemplate.tenant_id == tenant_id
                )
            ).all()
        }
        created = 0
        for channel, key, name, desc, subject, body in DEFAULT_TEMPLATES:
            if (channel, key) in existing:
                continue
            try:
                with self._session.begin_nested():
                    tmpl = CommunicationTemplate(
                        tenant_id=tenant_id,
                        channel=channel,
                        template_key=key,
                        name=name,
                        description=desc,
                        status=TemplateStatus.ACTIVE.value,
                        active_version=1,
                        created_by=actor,
                        updated_by=actor,
                    )
                    self._session.add(tmpl)
                    self._session.flush()
                    self._session.add(
                        CommunicationTemplateVersion(
                            tenant_id=tenant_id,
                            template_id=tmpl.id,
                            version=1,
                            subject_template=subject,
                            body_template=body,
                            status=VersionStatus.ACTIVE.value,
                            created_by=actor,
                        )
                    )
                    self._session.flush()
                    created += 1
            except IntegrityError:
                self._session.expire_all()
                continue
        if created:
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="communication_templates.seeded",
                resource_ids={"count": created},
                payload_summary={},
            )
        return created

    def list(
        self,
        tenant_id: UUID,
        *,
        channel: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        self.ensure_defaults(tenant_id)
        stmt = select(CommunicationTemplate).where(
            CommunicationTemplate.tenant_id == tenant_id
        )
        if channel:
            stmt = stmt.where(CommunicationTemplate.channel == channel.upper())
        if status:
            stmt = stmt.where(CommunicationTemplate.status == status.upper())
        rows = list(
            self._session.scalars(
                stmt.order_by(
                    CommunicationTemplate.channel.asc(),
                    CommunicationTemplate.template_key.asc(),
                )
            ).all()
        )
        out: list[dict[str, Any]] = []
        for row in rows:
            active = self._active_version(tenant_id, row)
            out.append(serialize_template(row, active=active))
        return out

    def get(self, tenant_id: UUID, template_id: UUID) -> dict[str, Any]:
        row = self._require(tenant_id, template_id)
        versions = list(
            self._session.scalars(
                select(CommunicationTemplateVersion)
                .where(
                    CommunicationTemplateVersion.tenant_id == tenant_id,
                    CommunicationTemplateVersion.template_id == template_id,
                )
                .order_by(CommunicationTemplateVersion.version.asc())
            ).all()
        )
        active = next(
            (v for v in versions if v.version == row.active_version),
            versions[-1] if versions else None,
        )
        return serialize_template(row, active=active, versions=versions)

    def update(
        self,
        tenant_id: UUID,
        template_id: UUID,
        *,
        actor: str,
        name: str | None = None,
        description: str | None = None,
        subject_template: str | None = None,
        body_template: str | None = None,
        publish: bool = False,
    ) -> dict[str, Any]:
        row = self._require(tenant_id, template_id, for_update=True)
        if row.status == TemplateStatus.ARCHIVED.value:
            raise CommunicationTemplateError(
                "archived", "Cannot update an archived template"
            )
        now = datetime.now(UTC)
        if name is not None:
            row.name = name.strip()[:128]
        if description is not None:
            row.description = description.strip()[:2000] or None

        active = self._active_version(tenant_id, row)
        if active is None:
            raise CommunicationTemplateError("no_version", "Template has no version")

        new_subject = (
            subject_template
            if subject_template is not None
            else active.subject_template
        )
        new_body = body_template if body_template is not None else active.body_template
        if body_template is not None or subject_template is not None:
            errs = validate_template_text(
                channel=row.channel,
                template_key=row.template_key,
                body=new_body or "",
                subject=new_subject,
            )
            if errs:
                raise CommunicationTemplateError(
                    "invalid_template", "; ".join(errs), retryable=False
                )
            if publish:
                # Immutable new version
                for v in self._session.scalars(
                    select(CommunicationTemplateVersion).where(
                        CommunicationTemplateVersion.tenant_id == tenant_id,
                        CommunicationTemplateVersion.template_id == row.id,
                        CommunicationTemplateVersion.status
                        == VersionStatus.ACTIVE.value,
                    )
                ).all():
                    v.status = VersionStatus.SUPERSEDED.value
                next_ver = int(row.active_version) + 1
                ver = CommunicationTemplateVersion(
                    tenant_id=tenant_id,
                    template_id=row.id,
                    version=next_ver,
                    subject_template=new_subject if row.channel == "EMAIL" else None,
                    body_template=new_body or "",
                    status=VersionStatus.ACTIVE.value,
                    created_by=actor,
                )
                self._session.add(ver)
                row.active_version = next_ver
            else:
                # Edit in place only when still at draft semantics — for ACTIVE
                # templates we create a draft version without activating.
                draft = CommunicationTemplateVersion(
                    tenant_id=tenant_id,
                    template_id=row.id,
                    version=int(row.active_version) + 1,
                    subject_template=new_subject if row.channel == "EMAIL" else None,
                    body_template=new_body or "",
                    status=VersionStatus.DRAFT.value,
                    created_by=actor,
                )
                try:
                    with self._session.begin_nested():
                        self._session.add(draft)
                        self._session.flush()
                except IntegrityError:
                    # Concurrent draft — overwrite latest draft
                    self._session.expire_all()
                    existing_draft = self._session.scalar(
                        select(CommunicationTemplateVersion).where(
                            CommunicationTemplateVersion.tenant_id == tenant_id,
                            CommunicationTemplateVersion.template_id == row.id,
                            CommunicationTemplateVersion.status
                            == VersionStatus.DRAFT.value,
                        )
                    )
                    if existing_draft is None:
                        raise
                    existing_draft.subject_template = (
                        new_subject if row.channel == "EMAIL" else None
                    )
                    existing_draft.body_template = new_body or ""
                    existing_draft.created_by = actor

        row.updated_by = actor
        row.updated_at = now
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="communication_template.updated",
            resource_ids={"template_id": str(row.id)},
            payload_summary={"publish": publish},
        )
        return self.get(tenant_id, template_id)

    def publish(
        self, tenant_id: UUID, template_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        row = self._require(tenant_id, template_id, for_update=True)
        draft = self._session.scalar(
            select(CommunicationTemplateVersion)
            .where(
                CommunicationTemplateVersion.tenant_id == tenant_id,
                CommunicationTemplateVersion.template_id == template_id,
                CommunicationTemplateVersion.status == VersionStatus.DRAFT.value,
            )
            .order_by(CommunicationTemplateVersion.version.desc())
            .limit(1)
        )
        if draft is None:
            raise CommunicationTemplateError("no_draft", "No draft version to publish")
        errs = validate_template_text(
            channel=row.channel,
            template_key=row.template_key,
            body=draft.body_template,
            subject=draft.subject_template,
        )
        if errs:
            raise CommunicationTemplateError(
                "invalid_template", "; ".join(errs), retryable=False
            )
        for v in self._session.scalars(
            select(CommunicationTemplateVersion).where(
                CommunicationTemplateVersion.tenant_id == tenant_id,
                CommunicationTemplateVersion.template_id == template_id,
                CommunicationTemplateVersion.status == VersionStatus.ACTIVE.value,
            )
        ).all():
            v.status = VersionStatus.SUPERSEDED.value
        draft.status = VersionStatus.ACTIVE.value
        row.active_version = draft.version
        row.status = TemplateStatus.ACTIVE.value
        row.updated_by = actor
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="communication_template.published",
            resource_ids={
                "template_id": str(row.id),
                "version": draft.version,
            },
            payload_summary={},
        )
        return self.get(tenant_id, template_id)

    def archive(
        self, tenant_id: UUID, template_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        row = self._require(tenant_id, template_id, for_update=True)
        row.status = TemplateStatus.ARCHIVED.value
        row.updated_by = actor
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="communication_template.archived",
            resource_ids={"template_id": str(row.id)},
            payload_summary={},
        )
        return self.get(tenant_id, template_id)

    def validate(
        self,
        tenant_id: UUID,
        template_id: UUID,
        *,
        body: str | None = None,
        subject: str | None = None,
    ) -> dict[str, Any]:
        row = self._require(tenant_id, template_id)
        active = self._active_version(tenant_id, row)
        body_t = body if body is not None else (active.body_template if active else "")
        subject_t = (
            subject
            if subject is not None
            else (active.subject_template if active else None)
        )
        errors = validate_template_text(
            channel=row.channel,
            template_key=row.template_key,
            body=body_t or "",
            subject=subject_t,
        )
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "allowed_variables": sorted(
                TEMPLATE_VARIABLES.get(row.template_key, frozenset())
            ),
        }

    def preview(
        self,
        tenant_id: UUID,
        template_id: UUID,
        *,
        body: str | None = None,
        subject: str | None = None,
    ) -> dict[str, Any]:
        row = self._require(tenant_id, template_id)
        active = self._active_version(tenant_id, row)
        body_t = body if body is not None else (active.body_template if active else "")
        subject_t = (
            subject
            if subject is not None
            else (active.subject_template if active else None)
        )
        rendered = render(
            body_t or "",
            preview_context(),
            channel=row.channel,
            template_key=row.template_key,
            subject=subject_t,
        )
        return {
            "channel": row.channel,
            "template_key": row.template_key,
            "version": row.active_version,
            "rendered": rendered["body"],
            "rendered_subject": rendered["subject"] or None,
        }

    def render_and_enqueue(
        self,
        *,
        tenant_id: UUID,
        channel: str,
        template_key: str,
        payload: dict[str, Any],
        idempotency_key: str,
        appointment_id: UUID | None = None,
        customer_id: UUID | None = None,
        review_url: str | None = None,
    ) -> dict[str, Any]:
        """Resolve active template, render, enqueue via NotificationService."""
        channel_u = channel.upper()
        key = template_key.strip().upper()
        self._assert_key_channel(channel_u, key)
        self.ensure_defaults(tenant_id)

        cust_id = customer_id or (
            UUID(str(payload["customer_id"])) if payload.get("customer_id") else None
        )
        allowed, reason = customer_allows(
            self._session,
            tenant_id=tenant_id,
            customer_id=cust_id,
            channel=channel_u,
            template_key=key,
        )
        if not allowed:
            logger.info(
                "communication_skipped_preference tenant_id=%s template_key=%s reason=%s",
                tenant_id,
                key,
                reason,
            )
            return {
                "status": "skipped",
                "reason": reason,
                "template_key": key,
                "channel": channel_u,
            }

        row = self._session.scalar(
            select(CommunicationTemplate).where(
                CommunicationTemplate.tenant_id == tenant_id,
                CommunicationTemplate.channel == channel_u,
                CommunicationTemplate.template_key == key,
                CommunicationTemplate.status == TemplateStatus.ACTIVE.value,
            )
        )
        if row is None:
            raise CommunicationTemplateError(
                "template_not_found",
                f"No active template for {channel_u}/{key}",
                retryable=False,
            )
        version = self._active_version(tenant_id, row)
        if version is None:
            raise CommunicationTemplateError(
                "no_version", "Template has no active version", retryable=False
            )

        ctx_payload = dict(payload)
        if review_url:
            ctx_payload["review_url"] = review_url
        context = build_template_context(
            self._session, tenant_id=tenant_id, payload=ctx_payload
        )
        rendered = render(
            version.body_template,
            context,
            channel=channel_u,
            template_key=key,
            subject=version.subject_template,
        )

        to = self._resolve_recipient(tenant_id, cust_id, channel_u, context)
        if not to:
            raise CommunicationTemplateError(
                "missing_recipient",
                f"No {channel_u.lower()} recipient",
                retryable=False,
            )

        body_out = rendered["body"]
        if channel_u == "EMAIL" and rendered["subject"]:
            # Existing outbox has no subject column — preserve in body + payload.
            body_out = f"{rendered['subject']}\n\n{rendered['body']}"

        meta = {
            "template_id": str(row.id),
            "template_key": key,
            "template_version": version.version,
            "subject": rendered["subject"] or None,
            "customer_id": str(cust_id) if cust_id else None,
            "channel": channel_u,
        }
        logger.info(
            "communication_template_rendered tenant_id=%s channel=%s template_key=%s version=%s",
            tenant_id,
            channel_u,
            key,
            version.version,
        )
        svc = NotificationService(self._session)
        if channel_u == "SMS":
            result = svc.enqueue_sms(
                tenant_id=tenant_id,
                to_address=to,
                body=body_out,
                appointment_id=appointment_id,
                idempotency_key=idempotency_key,
            )
        else:
            result = svc.enqueue_email(
                tenant_id=tenant_id,
                to_address=to,
                body=body_out,
                appointment_id=appointment_id,
                idempotency_key=idempotency_key,
            )
        # Attach template metadata onto outbox payload when newly created
        outbox_id = result.get("outbox_id")
        if outbox_id and not result.get("idempotent"):
            from callbot_platform.db.models import NotificationOutbox

            outbox = self._session.get(NotificationOutbox, UUID(str(outbox_id)))
            if outbox is not None:
                outbox.payload = {**(outbox.payload or {}), **meta}
                self._session.flush()
        logger.info(
            "communication_notification_queued tenant_id=%s channel=%s template_key=%s outbox_id=%s",
            tenant_id,
            channel_u,
            key,
            outbox_id,
        )
        return {
            **result,
            "id": outbox_id,
            "template_key": key,
            "template_version": version.version,
            "channel": channel_u,
            "rendered_subject": rendered["subject"] or None,
        }

    def variable_catalog(self, template_key: str | None = None) -> dict[str, Any]:
        if template_key:
            key = template_key.upper()
            return {
                "template_key": key,
                "variables": sorted(TEMPLATE_VARIABLES.get(key, frozenset())),
            }
        return {
            "sms_keys": sorted(SMS_TEMPLATE_KEYS),
            "email_keys": sorted(EMAIL_TEMPLATE_KEYS),
            "by_template": {
                k: sorted(v) for k, v in sorted(TEMPLATE_VARIABLES.items())
            },
        }

    def _resolve_recipient(
        self,
        tenant_id: UUID,
        customer_id: UUID | None,
        channel: str,
        context: dict[str, Any],
    ) -> str | None:
        if channel == "SMS":
            phone = context.get("customer.phone") or ""
            if phone:
                return str(phone)
            if customer_id:
                row = self._session.scalar(
                    select(CustomerPhone).where(
                        CustomerPhone.tenant_id == tenant_id,
                        CustomerPhone.customer_id == customer_id,
                    )
                )
                return row.e164 if row else None
            return None
        email = context.get("customer.email") or ""
        if email:
            return str(email)
        if customer_id:
            cust = self._session.scalar(
                select(Customer).where(
                    Customer.id == customer_id, Customer.tenant_id == tenant_id
                )
            )
            return cust.email if cust else None
        return None

    def _assert_key_channel(self, channel: str, key: str) -> None:
        if key not in ALL_TEMPLATE_KEYS:
            raise CommunicationTemplateError(
                "invalid_template_key", f"Unknown template key: {key}", retryable=False
            )
        if channel == "SMS" and key not in SMS_TEMPLATE_KEYS:
            raise CommunicationTemplateError(
                "channel_mismatch",
                f"Template key {key} is not valid for SMS",
                retryable=False,
            )
        if channel == "EMAIL" and key not in EMAIL_TEMPLATE_KEYS:
            raise CommunicationTemplateError(
                "channel_mismatch",
                f"Template key {key} is not valid for EMAIL",
                retryable=False,
            )

    def _active_version(
        self, tenant_id: UUID, row: CommunicationTemplate
    ) -> CommunicationTemplateVersion | None:
        return self._session.scalar(
            select(CommunicationTemplateVersion).where(
                CommunicationTemplateVersion.tenant_id == tenant_id,
                CommunicationTemplateVersion.template_id == row.id,
                CommunicationTemplateVersion.version == row.active_version,
            )
        )

    def _require(
        self,
        tenant_id: UUID,
        template_id: UUID,
        *,
        for_update: bool = False,
    ) -> CommunicationTemplate:
        stmt = select(CommunicationTemplate).where(
            CommunicationTemplate.id == template_id,
            CommunicationTemplate.tenant_id == tenant_id,
        )
        if for_update:
            stmt = stmt.with_for_update()
        row = self._session.scalar(stmt)
        if row is None:
            raise CommunicationTemplateError("template_not_found", "Template not found")
        return row
