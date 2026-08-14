"""
State Pattern pour les paiements CloudBaby.

Chaque état encapsule les transitions autorisées et le comportement
associé. Le PaymentService est le Context qui délègue à l'état courant.

Transitions:
                        installment_paid (partiel)
  PENDING ─────────────────────────────────────────► PARTIALLY_PAID
     │                                                       │
     │  installment_paid (total)                             │ installment_paid (total)
     ▼                                                       ▼
   PAID ◄──────────────────────────────────────────────── PAID

  PENDING ──► CANCELLED  (annulation volontaire)
  PENDING / PARTIALLY_PAID ──► FAILED  (échec provider sans paiement)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.payment import Payment


class PaymentState(ABC):
    """Interface commune pour tous les états d'un paiement."""

    @abstractmethod
    def on_installment_confirmed(self, payment: "Payment", amount_paid: int) -> None:
        """Appelé quand une tranche est confirmée comme payée."""
        ...

    @abstractmethod
    def on_installment_failed(self, payment: "Payment", reason: str) -> None:
        """Appelé quand une tranche échoue chez le provider."""
        ...

    @abstractmethod
    def on_cancel(self, payment: "Payment", reason: str) -> None:
        """Appelé pour annuler le paiement."""
        ...

    @abstractmethod
    def is_terminal(self) -> bool:
        """Un état terminal ne peut plus changer."""
        ...

    @abstractmethod
    def status_value(self) -> str:
        """Valeur string persistée en base."""
        ...


# ─────────────────────────────────────────────────────────────────────────────
# Concrete States
# ─────────────────────────────────────────────────────────────────────────────


class PendingState(PaymentState):
    """Aucune tranche payée. Paiement en attente."""

    def on_installment_confirmed(self, payment: "Payment", amount_paid: int) -> None:
        payment.paid_amount += amount_paid
        if payment.paid_amount >= payment.total_amount:
            _apply_state(payment, PaidState())
        else:
            _apply_state(payment, PartiallyPaidState())

    def on_installment_failed(self, payment: "Payment", reason: str) -> None:
        # Pas encore de montant encaissé → on passe en FAILED
        payment.failure_reason = reason
        _apply_state(payment, FailedState())

    def on_cancel(self, payment: "Payment", reason: str) -> None:
        payment.failure_reason = reason
        _apply_state(payment, CancelledState())

    def is_terminal(self) -> bool:
        return False

    def status_value(self) -> str:
        return "pending"


class PartiallyPaidState(PaymentState):
    """Au moins une tranche payée, mais pas la totalité."""

    def on_installment_confirmed(self, payment: "Payment", amount_paid: int) -> None:
        payment.paid_amount += amount_paid
        if payment.paid_amount >= payment.total_amount:
            _apply_state(payment, PaidState())
        # else: stay partially_paid

    def on_installment_failed(self, payment: "Payment", reason: str) -> None:
        # De l'argent a déjà été encaissé → on ne passe pas en FAILED,
        # on reste PARTIALLY_PAID (une tranche individuelle a échoué).
        # Le service logguera l'échec sur la tranche elle-même.
        pass

    def on_cancel(self, payment: "Payment", reason: str) -> None:
        # Annulation impossible quand de l'argent a déjà été encaissé.
        raise ValueError(
            "Impossible d'annuler un paiement partiellement payé. "
            "Utilisez le remboursement."
        )

    def is_terminal(self) -> bool:
        return False

    def status_value(self) -> str:
        return "partially_paid"


class PaidState(PaymentState):
    """Paiement totalement encaissé. État terminal."""

    def on_installment_confirmed(self, payment: "Payment", amount_paid: int) -> None:
        raise ValueError("Le paiement est déjà complet.")

    def on_installment_failed(self, payment: "Payment", reason: str) -> None:
        raise ValueError("Le paiement est déjà complet.")

    def on_cancel(self, payment: "Payment", reason: str) -> None:
        raise ValueError("Impossible d'annuler un paiement terminé. Utilisez le remboursement.")

    def is_terminal(self) -> bool:
        return True

    def status_value(self) -> str:
        return "paid"


class FailedState(PaymentState):
    """Paiement échoué (aucun montant encaissé). État terminal."""

    def on_installment_confirmed(self, payment: "Payment", amount_paid: int) -> None:
        raise ValueError("Le paiement est en état d'échec.")

    def on_installment_failed(self, payment: "Payment", reason: str) -> None:
        pass  # Déjà en échec

    def on_cancel(self, payment: "Payment", reason: str) -> None:
        raise ValueError("Le paiement a déjà échoué.")

    def is_terminal(self) -> bool:
        return True

    def status_value(self) -> str:
        return "failed"


class CancelledState(PaymentState):
    """Paiement annulé manuellement. État terminal."""

    def on_installment_confirmed(self, payment: "Payment", amount_paid: int) -> None:
        raise ValueError("Le paiement est annulé.")

    def on_installment_failed(self, payment: "Payment", reason: str) -> None:
        raise ValueError("Le paiement est annulé.")

    def on_cancel(self, payment: "Payment", reason: str) -> None:
        pass  # Déjà annulé

    def is_terminal(self) -> bool:
        return True

    def status_value(self) -> str:
        return "cancelled"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _apply_state(payment: "Payment", state: PaymentState) -> None:
    """Applique l'état sur le modèle ORM (met à jour le champ status)."""
    payment.status = state.status_value()


def resolve_state(status: str) -> PaymentState:
    """Reconstruit l'état à partir de la valeur persistée en base."""
    mapping: dict[str, PaymentState] = {
        "pending": PendingState(),
        "partially_paid": PartiallyPaidState(),
        "paid": PaidState(),
        "failed": FailedState(),
        "cancelled": CancelledState(),
    }
    state = mapping.get(status)
    if state is None:
        raise ValueError(f"Statut de paiement inconnu: {status!r}")
    return state
