from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import (
    CreditLedgerEntry,
    CreditWallet,
    UsageEvent,
    User,
)


def ensure_wallet(db: Session, user: User, *, lock: bool = False) -> CreditWallet:
    query = select(CreditWallet).where(
        CreditWallet.product_id == user.product_id,
        CreditWallet.user_id == user.id,
    )
    if lock:
        query = query.with_for_update()
    wallet = db.scalar(query)
    if wallet:
        return wallet

    wallet = CreditWallet(
        product_id=user.product_id,
        organization_id=user.organization_id,
        user_id=user.id,
        balance_micros=0,
    )
    db.add(wallet)
    db.flush()
    return wallet


def balance_micros(db: Session, user: User) -> int:
    return int(ensure_wallet(db, user).balance_micros)


def available_micros(db: Session, user: User) -> int:
    wallet = ensure_wallet(db, user)
    return int(wallet.balance_micros) - int(wallet.reserved_micros)


def credit(
    db: Session,
    user: User,
    *,
    amount_micros: int,
    entry_type: str,
    idempotency_key: str,
    note: str = "",
    payment_amount_micros: int = 0,
    currency: str = "CNY",
    payment_order_id: str = "",
    reference_id: str = "",
    operator_user_id: str | None = None,
) -> tuple[CreditWallet, CreditLedgerEntry, bool]:
    if amount_micros <= 0:
        raise ValueError("入账 Credits 必须大于 0")
    wallet = ensure_wallet(db, user, lock=True)
    existing = db.scalar(select(CreditLedgerEntry).where(
        CreditLedgerEntry.wallet_id == wallet.id,
        CreditLedgerEntry.idempotency_key == idempotency_key,
    ))
    if existing:
        return wallet, existing, False
    wallet.balance_micros += amount_micros
    wallet.version += 1
    entry = CreditLedgerEntry(
        product_id=user.product_id,
        organization_id=user.organization_id,
        user_id=user.id,
        wallet_id=wallet.id,
        entry_type=entry_type,
        credits_delta_micros=amount_micros,
        balance_after_micros=wallet.balance_micros,
        payment_amount_micros=payment_amount_micros,
        currency=currency,
        payment_order_id=payment_order_id,
        reference_id=reference_id,
        operator_user_id=operator_user_id,
        idempotency_key=idempotency_key,
        note=note,
    )
    db.add(entry)
    db.flush()
    return wallet, entry, True


def reserve(db: Session, user: User, event: UsageEvent, amount_micros: int) -> CreditWallet:
    wallet = ensure_wallet(db, user, lock=True)
    if wallet.status != "active":
        raise ValueError("Credits 钱包暂不可用")
    if wallet.balance_micros - wallet.reserved_micros < amount_micros:
        raise ValueError("Credits 余额不足")
    wallet.reserved_micros += amount_micros
    wallet.version += 1
    event.wallet_id = wallet.id
    event.product_id = user.product_id
    event.reserved_credits_micros = amount_micros
    return wallet


def settle(db: Session, event: UsageEvent, actual_micros: int) -> CreditLedgerEntry | None:
    if not event.wallet_id:
        return None
    wallet = db.scalar(select(CreditWallet).where(CreditWallet.id == event.wallet_id).with_for_update())
    if not wallet:
        raise ValueError("Credits 钱包不存在")
    key = f"usage:{event.id}:debit"
    existing = db.scalar(select(CreditLedgerEntry).where(
        CreditLedgerEntry.wallet_id == wallet.id,
        CreditLedgerEntry.idempotency_key == key,
    ))
    if existing:
        return existing
    wallet.reserved_micros = max(0, wallet.reserved_micros - int(event.reserved_credits_micros or 0))
    wallet.balance_micros -= actual_micros
    wallet.version += 1
    entry = CreditLedgerEntry(
        product_id=event.product_id,
        organization_id=event.organization_id,
        user_id=event.user_id,
        wallet_id=wallet.id,
        entry_type="usage_debit",
        credits_delta_micros=-actual_micros,
        balance_after_micros=wallet.balance_micros,
        usage_event_id=event.id,
        idempotency_key=key,
        note=f"{event.capability} 用量结算",
        detail={"pricing_version": event.pricing_version},
    )
    db.add(entry)
    db.flush()
    return entry


def release(db: Session, event: UsageEvent) -> None:
    if not event.wallet_id or not event.reserved_credits_micros:
        return
    wallet = db.scalar(select(CreditWallet).where(CreditWallet.id == event.wallet_id).with_for_update())
    if wallet:
        wallet.reserved_micros = max(0, wallet.reserved_micros - int(event.reserved_credits_micros))
        wallet.version += 1
    event.reserved_credits_micros = 0
