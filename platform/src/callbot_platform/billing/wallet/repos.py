"""Wallet persistence helpers (tenant-scoped)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.db.models.wallet import (
    UsageCharge,
    Wallet,
    WalletReservation,
    WalletSettings,
    WalletTopup,
    WalletTransaction,
)


class WalletRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_wallet(self, tenant_id: UUID) -> Wallet | None:
        return self._session.scalar(select(Wallet).where(Wallet.tenant_id == tenant_id))

    def get_wallet_for_update(self, tenant_id: UUID) -> Wallet | None:
        return self._session.scalar(
            select(Wallet).where(Wallet.tenant_id == tenant_id).with_for_update()
        )

    def get_settings(self, tenant_id: UUID) -> WalletSettings | None:
        return self._session.scalar(
            select(WalletSettings).where(WalletSettings.tenant_id == tenant_id)
        )

    def get_transaction_by_idempotency(
        self, tenant_id: UUID, idempotency_key: str
    ) -> WalletTransaction | None:
        return self._session.scalar(
            select(WalletTransaction).where(
                WalletTransaction.tenant_id == tenant_id,
                WalletTransaction.idempotency_key == idempotency_key,
            )
        )

    def list_transactions(
        self, tenant_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> list[WalletTransaction]:
        return list(
            self._session.scalars(
                select(WalletTransaction)
                .where(WalletTransaction.tenant_id == tenant_id)
                .order_by(WalletTransaction.created_at.desc())
                .offset(max(offset, 0))
                .limit(min(max(limit, 1), 200))
            ).all()
        )

    def get_topup(self, tenant_id: UUID, topup_id: UUID) -> WalletTopup | None:
        return self._session.scalar(
            select(WalletTopup).where(
                WalletTopup.id == topup_id,
                WalletTopup.tenant_id == tenant_id,
            )
        )

    def get_topup_by_checkout_session(self, session_id: str) -> WalletTopup | None:
        return self._session.scalar(
            select(WalletTopup).where(
                WalletTopup.stripe_checkout_session_id == session_id
            )
        )

    def get_usage_charge_for_call(
        self, tenant_id: UUID, call_id: UUID
    ) -> UsageCharge | None:
        return self._session.scalar(
            select(UsageCharge).where(
                UsageCharge.tenant_id == tenant_id,
                UsageCharge.call_id == call_id,
            )
        )

    def get_reservation_by_idempotency(
        self, tenant_id: UUID, idempotency_key: str
    ) -> WalletReservation | None:
        return self._session.scalar(
            select(WalletReservation).where(
                WalletReservation.tenant_id == tenant_id,
                WalletReservation.idempotency_key == idempotency_key,
            )
        )
