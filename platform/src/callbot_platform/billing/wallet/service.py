"""Atomic USD wallet credit/debit/reserve operations."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.billing.wallet.constants import (
    DEFAULT_CRITICAL_BALANCE_CENTS,
    DEFAULT_LOW_BALANCE_CENTS,
    IN_PROGRESS_EXPOSURE_CENTS,
    WALLET_CURRENCY,
)
from callbot_platform.billing.wallet.repos import WalletRepository
from callbot_platform.db.models.wallet import (
    Wallet,
    WalletReservation,
    WalletSettings,
    WalletTransaction,
)


class WalletError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class WalletService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = WalletRepository(session)

    def ensure_wallet(self, tenant_id: UUID) -> Wallet:
        existing = self._repo.get_wallet(tenant_id)
        if existing is not None:
            return existing
        wallet = Wallet(
            tenant_id=tenant_id,
            currency=WALLET_CURRENCY,
            available_balance_cents=0,
            reserved_balance_cents=0,
            status="ACTIVE",
        )
        self._session.add(wallet)
        settings = WalletSettings(
            tenant_id=tenant_id,
            low_balance_cents=DEFAULT_LOW_BALANCE_CENTS,
            critical_balance_cents=DEFAULT_CRITICAL_BALANCE_CENTS,
            auto_topup_enabled=False,
        )
        self._session.add(settings)
        self._session.flush()
        return wallet

    def get_balance(self, tenant_id: UUID) -> dict[str, Any]:
        wallet = self.ensure_wallet(tenant_id)
        settings = self._repo.get_settings(tenant_id)
        return {
            "wallet_id": str(wallet.id),
            "tenant_id": str(tenant_id),
            "currency": wallet.currency,
            "available_balance_cents": int(wallet.available_balance_cents),
            "reserved_balance_cents": int(wallet.reserved_balance_cents),
            "status": wallet.status,
            "low_balance_cents": int(
                settings.low_balance_cents if settings else DEFAULT_LOW_BALANCE_CENTS
            ),
            "critical_balance_cents": int(
                settings.critical_balance_cents
                if settings
                else DEFAULT_CRITICAL_BALANCE_CENTS
            ),
            "auto_topup_enabled": bool(
                settings.auto_topup_enabled if settings else False
            ),
        }

    def list_transactions(
        self, tenant_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        self.ensure_wallet(tenant_id)
        rows = self._repo.list_transactions(tenant_id, limit=limit, offset=offset)
        return [self._serialize_txn(r) for r in rows]

    def credit(
        self,
        tenant_id: UUID,
        *,
        amount_cents: int,
        idempotency_key: str,
        reference_type: str | None = None,
        reference_id: str | None = None,
        description: str | None = None,
        transaction_type: str = "CREDIT",
    ) -> WalletTransaction:
        if amount_cents <= 0:
            raise WalletError("invalid_amount", "Credit amount must be positive")
        return self._apply(
            tenant_id,
            signed_amount_cents=amount_cents,
            idempotency_key=idempotency_key,
            transaction_type=transaction_type,
            reference_type=reference_type,
            reference_id=reference_id,
            description=description,
        )

    def debit(
        self,
        tenant_id: UUID,
        *,
        amount_cents: int,
        idempotency_key: str,
        reference_type: str | None = None,
        reference_id: str | None = None,
        description: str | None = None,
        allow_zero: bool = False,
    ) -> WalletTransaction:
        if amount_cents < 0 or (amount_cents == 0 and not allow_zero):
            raise WalletError("invalid_amount", "Debit amount must be positive")
        if amount_cents == 0:
            # No-op ledger row for zero overage.
            return self._apply(
                tenant_id,
                signed_amount_cents=0,
                idempotency_key=idempotency_key,
                transaction_type="DEBIT",
                reference_type=reference_type,
                reference_id=reference_id,
                description=description or "Zero amount",
                allow_insufficient=True,
            )
        return self._apply(
            tenant_id,
            signed_amount_cents=-amount_cents,
            idempotency_key=idempotency_key,
            transaction_type="DEBIT",
            reference_type=reference_type,
            reference_id=reference_id,
            description=description,
        )

    def can_start_billable_call(self, tenant_id: UUID) -> bool:
        wallet = self.ensure_wallet(tenant_id)
        if wallet.status != "ACTIVE":
            return False
        return int(wallet.available_balance_cents) > 0

    def freeze(self, tenant_id: UUID, *, reason: str) -> Wallet:
        wallet = self._lock_wallet(tenant_id)
        wallet.status = "FROZEN"
        self._session.flush()
        _ = reason
        return wallet

    def unfreeze(self, tenant_id: UUID) -> Wallet:
        wallet = self._lock_wallet(tenant_id)
        if wallet.status == "CLOSED":
            raise WalletError("wallet_closed", "Closed wallets cannot be reopened")
        wallet.status = "ACTIVE"
        self._session.flush()
        return wallet

    def _lock_wallet(self, tenant_id: UUID) -> Wallet:
        self.ensure_wallet(tenant_id)
        wallet = self._repo.get_wallet_for_update(tenant_id)
        if wallet is None:
            # SQLite / race: ensure again without lock.
            wallet = self.ensure_wallet(tenant_id)
        return wallet

    def reserve(
        self,
        tenant_id: UUID,
        *,
        amount_cents: int | None = None,
        idempotency_key: str,
        reference_type: str | None = None,
        reference_id: str | None = None,
    ) -> WalletReservation:
        """Hold funds for an in-progress call (optional exposure control)."""
        amount = int(
            amount_cents if amount_cents is not None else IN_PROGRESS_EXPOSURE_CENTS
        )
        if amount <= 0:
            raise WalletError("invalid_amount", "Reservation amount must be positive")
        key = (idempotency_key or "").strip()
        if not key:
            raise WalletError("invalid_idempotency", "Idempotency key is required")
        existing = self._repo.get_reservation_by_idempotency(tenant_id, key)
        if existing is not None:
            return existing

        wallet = self._lock_wallet(tenant_id)
        if wallet.status != "ACTIVE":
            raise WalletError("wallet_not_active", "Wallet is not active")
        available = int(wallet.available_balance_cents)
        if available < amount:
            raise WalletError("insufficient_funds", "Insufficient wallet balance")
        wallet.available_balance_cents = available - amount
        wallet.reserved_balance_cents = int(wallet.reserved_balance_cents) + amount
        row = WalletReservation(
            wallet_id=wallet.id,
            tenant_id=tenant_id,
            amount_cents=amount,
            status="OPEN",
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=key,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def release_reservation(
        self, tenant_id: UUID, *, idempotency_key: str
    ) -> WalletReservation | None:
        key = (idempotency_key or "").strip()
        row = self._repo.get_reservation_by_idempotency(tenant_id, key)
        if row is None or row.status != "OPEN":
            return row
        wallet = self._lock_wallet(tenant_id)
        amount = int(row.amount_cents)
        wallet.reserved_balance_cents = max(
            0, int(wallet.reserved_balance_cents) - amount
        )
        wallet.available_balance_cents = int(wallet.available_balance_cents) + amount
        row.status = "RELEASED"
        self._session.flush()
        return row

    def _apply(
        self,
        tenant_id: UUID,
        *,
        signed_amount_cents: int,
        idempotency_key: str,
        transaction_type: str,
        reference_type: str | None,
        reference_id: str | None,
        description: str | None,
        allow_insufficient: bool = False,
    ) -> WalletTransaction:
        key = (idempotency_key or "").strip()
        if not key:
            raise WalletError("invalid_idempotency", "Idempotency key is required")

        wallet = self._lock_wallet(tenant_id)
        existing = self._repo.get_transaction_by_idempotency(tenant_id, key)
        if existing is not None:
            return existing

        if wallet.status == "CLOSED":
            raise WalletError("wallet_closed", "Wallet is closed")
        if wallet.status == "FROZEN" and signed_amount_cents < 0:
            raise WalletError("wallet_frozen", "Wallet is frozen")

        available = int(wallet.available_balance_cents)
        next_balance = available + signed_amount_cents
        if next_balance < 0 and not allow_insufficient:
            raise WalletError(
                "insufficient_funds",
                "Insufficient wallet balance",
            )
        if next_balance < 0:
            next_balance = 0

        wallet.available_balance_cents = next_balance
        txn = WalletTransaction(
            wallet_id=wallet.id,
            tenant_id=tenant_id,
            transaction_type=transaction_type,
            amount_cents=abs(signed_amount_cents),
            currency=WALLET_CURRENCY,
            balance_after_cents=next_balance,
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=key,
            description=description,
        )
        try:
            with self._session.begin_nested():
                self._session.add(txn)
                self._session.flush()
        except IntegrityError:
            # Concurrent duplicate idempotency key — return the winner.
            replay = self._repo.get_transaction_by_idempotency(tenant_id, key)
            if replay is not None:
                # Undo optimistic balance update from this loser txn.
                wallet.available_balance_cents = available
                self._session.flush()
                return replay
            raise
        if signed_amount_cents < 0:
            try:
                from callbot_platform.billing.wallet.alerts import (
                    WalletAlertService,
                )

                WalletAlertService(self._session).evaluate_after_balance_change(
                    tenant_id, balance_cents=next_balance
                )
            except Exception as alert_exc:
                # Alerts must never fail money movement.
                _ = alert_exc
        return txn

    @staticmethod
    def _serialize_txn(row: WalletTransaction) -> dict[str, Any]:
        signed = int(row.amount_cents)
        if row.transaction_type in {"DEBIT"}:
            signed = -signed
        return {
            "id": str(row.id),
            "transaction_type": row.transaction_type,
            "amount_cents": int(row.amount_cents),
            "signed_amount_cents": signed,
            "currency": row.currency,
            "balance_after_cents": int(row.balance_after_cents),
            "reference_type": row.reference_type,
            "reference_id": row.reference_id,
            "description": row.description,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
