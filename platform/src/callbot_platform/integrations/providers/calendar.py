"""Calendar provider adapters (Google Calendar + Outlook/Graph)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from callbot_platform.integrations.catalog import PROVIDER_CATALOG
from callbot_platform.integrations.constants import HealthStatus, ProviderKey
from callbot_platform.integrations.errors import AuthExpiredError, IntegrationError
from callbot_platform.integrations.http import request_with_retry
from callbot_platform.integrations.protocols import (
    ExternalAppointment,
    HealthResult,
    SyncPage,
)
from callbot_platform.integrations.providers.base import BaseProviderAdapter


def _parse_google_event(item: dict[str, Any]) -> ExternalAppointment:
    start = item.get("start") or {}
    end = item.get("end") or {}
    starts_raw = start.get("dateTime") or start.get("date")
    ends_raw = end.get("dateTime") or end.get("date")
    tz = start.get("timeZone") or end.get("timeZone")
    return ExternalAppointment(
        external_id=str(item["id"]),
        title=item.get("summary"),
        starts_at=_parse_dt(starts_raw),
        ends_at=_parse_dt(ends_raw),
        timezone=tz,
        status=item.get("status"),
        raw={"provider": "google_calendar", "etag": item.get("etag")},
    )


def _parse_outlook_event(item: dict[str, Any]) -> ExternalAppointment:
    start = item.get("start") or {}
    end = item.get("end") or {}
    return ExternalAppointment(
        external_id=str(item["id"]),
        title=item.get("subject"),
        starts_at=_parse_dt(start.get("dateTime")),
        ends_at=_parse_dt(end.get("dateTime")),
        timezone=start.get("timeZone") or end.get("timeZone"),
        status="cancelled" if item.get("isCancelled") else "confirmed",
        raw={"provider": "outlook_calendar", "@odata.etag": item.get("@odata.etag")},
    )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _bearer(credentials: dict[str, Any] | None) -> str:
    if not credentials or not credentials.get("access_token"):
        raise AuthExpiredError("Missing access token")
    return str(credentials["access_token"])


class GoogleCalendarAdapter(BaseProviderAdapter):
    def __init__(self) -> None:
        self.descriptor = PROVIDER_CATALOG[ProviderKey.GOOGLE_CALENDAR.value]

    def health_check(self, *, credentials: dict[str, Any] | None) -> HealthResult:
        base = super().health_check(credentials=credentials)
        if base.status != HealthStatus.HEALTHY:
            return base
        token = credentials.get("access_token") if credentials else None
        if not token:
            return HealthResult(
                status=HealthStatus.AUTH_REQUIRED, message="Access token missing"
            )
        try:
            request_with_retry(
                "GET",
                "https://www.googleapis.com/calendar/v3/users/me/calendarList",
                headers={"Authorization": f"Bearer {token}"},
                params={"maxResults": "1"},
                max_retries=1,
            )
        except IntegrationError as exc:
            if exc.code in {"AUTH_EXPIRED", "AUTH_REVOKED"}:
                return HealthResult(
                    status=HealthStatus.AUTH_REQUIRED, message=exc.message
                )
            return HealthResult(status=HealthStatus.ERROR, message=exc.message)
        return HealthResult(status=HealthStatus.HEALTHY, message="Google Calendar OK")

    def list_calendars(
        self, *, credentials: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        token = _bearer(credentials)
        response = request_with_retry(
            "GET",
            "https://www.googleapis.com/calendar/v3/users/me/calendarList",
            headers={"Authorization": f"Bearer {token}"},
            max_retries=2,
        )
        items = response.json().get("items") or []
        return [
            {
                "id": i.get("id"),
                "summary": i.get("summary"),
                "primary": bool(i.get("primary")),
                "time_zone": i.get("timeZone"),
            }
            for i in items
            if isinstance(i, dict)
        ]

    def sync_page(
        self,
        *,
        tenant_id: UUID,
        credentials: dict[str, Any] | None,
        cursor: str | None,
        direction: str,
    ) -> SyncPage:
        _ = (tenant_id, direction)
        if not credentials or not credentials.get("access_token"):
            return SyncPage(items=[], done=True)
        token = str(credentials["access_token"])
        calendar_id = (credentials.get("extra") or {}).get("calendar_id") or "primary"
        params: dict[str, Any] = {
            "maxResults": 100,
            "singleEvents": "true",
            "orderBy": "updated",
        }
        if cursor:
            params["pageToken"] = cursor
        else:
            sync_token = (credentials.get("extra") or {}).get("sync_token")
            if sync_token:
                params["syncToken"] = sync_token
        try:
            response = request_with_retry(
                "GET",
                f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
                max_retries=2,
            )
        except IntegrationError:
            # Without live credentials / sandbox, sync returns empty page.
            return SyncPage(items=[], done=True)
        data = response.json()
        items = [
            _parse_google_event(i)
            for i in (data.get("items") or [])
            if isinstance(i, dict) and i.get("id")
        ]
        next_token = data.get("nextPageToken")
        return SyncPage(
            items=items,
            next_cursor=next_token,
            done=not bool(next_token),
        )

    def create_event(
        self,
        *,
        credentials: dict[str, Any] | None,
        calendar_id: str,
        title: str,
        starts_at: datetime,
        ends_at: datetime,
        timezone: str | None = None,
    ) -> ExternalAppointment:
        token = _bearer(credentials)
        body: dict[str, Any] = {
            "summary": title,
            "start": {
                "dateTime": starts_at.isoformat(),
                **({"timeZone": timezone} if timezone else {}),
            },
            "end": {
                "dateTime": ends_at.isoformat(),
                **({"timeZone": timezone} if timezone else {}),
            },
        }
        response = request_with_retry(
            "POST",
            f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json_body=body,
            max_retries=2,
        )
        return _parse_google_event(response.json())

    def update_event(
        self,
        *,
        credentials: dict[str, Any] | None,
        calendar_id: str,
        event_id: str,
        title: str | None = None,
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
        timezone: str | None = None,
    ) -> ExternalAppointment:
        token = _bearer(credentials)
        body: dict[str, Any] = {}
        if title is not None:
            body["summary"] = title
        if starts_at is not None:
            body["start"] = {
                "dateTime": starts_at.isoformat(),
                **({"timeZone": timezone} if timezone else {}),
            }
        if ends_at is not None:
            body["end"] = {
                "dateTime": ends_at.isoformat(),
                **({"timeZone": timezone} if timezone else {}),
            }
        response = request_with_retry(
            "PATCH",
            f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json_body=body,
            max_retries=2,
        )
        return _parse_google_event(response.json())

    def delete_event(
        self,
        *,
        credentials: dict[str, Any] | None,
        calendar_id: str,
        event_id: str,
    ) -> None:
        token = _bearer(credentials)
        request_with_retry(
            "DELETE",
            f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}",
            headers={"Authorization": f"Bearer {token}"},
            max_retries=2,
        )


class OutlookCalendarAdapter(BaseProviderAdapter):
    def __init__(self) -> None:
        self.descriptor = PROVIDER_CATALOG[ProviderKey.OUTLOOK_CALENDAR.value]

    def health_check(self, *, credentials: dict[str, Any] | None) -> HealthResult:
        base = super().health_check(credentials=credentials)
        if base.status != HealthStatus.HEALTHY:
            return base
        token = credentials.get("access_token") if credentials else None
        if not token:
            return HealthResult(
                status=HealthStatus.AUTH_REQUIRED, message="Access token missing"
            )
        try:
            request_with_retry(
                "GET",
                "https://graph.microsoft.com/v1.0/me/calendars",
                headers={"Authorization": f"Bearer {token}"},
                params={"$top": "1"},
                max_retries=1,
            )
        except IntegrationError as exc:
            if exc.code in {"AUTH_EXPIRED", "AUTH_REVOKED"}:
                return HealthResult(
                    status=HealthStatus.AUTH_REQUIRED, message=exc.message
                )
            return HealthResult(status=HealthStatus.ERROR, message=exc.message)
        return HealthResult(status=HealthStatus.HEALTHY, message="Outlook Calendar OK")

    def list_calendars(
        self, *, credentials: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        token = _bearer(credentials)
        response = request_with_retry(
            "GET",
            "https://graph.microsoft.com/v1.0/me/calendars",
            headers={"Authorization": f"Bearer {token}"},
            max_retries=2,
        )
        items = response.json().get("value") or []
        return [
            {
                "id": i.get("id"),
                "summary": i.get("name"),
                "primary": bool(i.get("isDefaultCalendar")),
                "time_zone": None,
            }
            for i in items
            if isinstance(i, dict)
        ]

    def sync_page(
        self,
        *,
        tenant_id: UUID,
        credentials: dict[str, Any] | None,
        cursor: str | None,
        direction: str,
    ) -> SyncPage:
        _ = (tenant_id, direction)
        if not credentials or not credentials.get("access_token"):
            return SyncPage(items=[], done=True)
        token = str(credentials["access_token"])
        url = cursor or "https://graph.microsoft.com/v1.0/me/events?$top=50"
        try:
            response = request_with_retry(
                "GET",
                url,
                headers={"Authorization": f"Bearer {token}"},
                max_retries=2,
            )
        except IntegrationError:
            return SyncPage(items=[], done=True)
        data = response.json()
        items = [
            _parse_outlook_event(i)
            for i in (data.get("value") or [])
            if isinstance(i, dict) and i.get("id")
        ]
        next_link = data.get("@odata.nextLink")
        return SyncPage(items=items, next_cursor=next_link, done=not bool(next_link))

    def create_event(
        self,
        *,
        credentials: dict[str, Any] | None,
        title: str,
        starts_at: datetime,
        ends_at: datetime,
        timezone: str = "UTC",
    ) -> ExternalAppointment:
        token = _bearer(credentials)
        body = {
            "subject": title,
            "start": {"dateTime": starts_at.isoformat(), "timeZone": timezone},
            "end": {"dateTime": ends_at.isoformat(), "timeZone": timezone},
        }
        response = request_with_retry(
            "POST",
            "https://graph.microsoft.com/v1.0/me/events",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json_body=body,
            max_retries=2,
        )
        return _parse_outlook_event(response.json())

    def update_event(
        self,
        *,
        credentials: dict[str, Any] | None,
        event_id: str,
        title: str | None = None,
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
        timezone: str = "UTC",
    ) -> ExternalAppointment:
        token = _bearer(credentials)
        body: dict[str, Any] = {}
        if title is not None:
            body["subject"] = title
        if starts_at is not None:
            body["start"] = {"dateTime": starts_at.isoformat(), "timeZone": timezone}
        if ends_at is not None:
            body["end"] = {"dateTime": ends_at.isoformat(), "timeZone": timezone}
        response = request_with_retry(
            "PATCH",
            f"https://graph.microsoft.com/v1.0/me/events/{event_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json_body=body,
            max_retries=2,
        )
        return _parse_outlook_event(response.json())

    def delete_event(
        self, *, credentials: dict[str, Any] | None, event_id: str
    ) -> None:
        token = _bearer(credentials)
        request_with_retry(
            "DELETE",
            f"https://graph.microsoft.com/v1.0/me/events/{event_id}",
            headers={"Authorization": f"Bearer {token}"},
            max_retries=2,
        )
