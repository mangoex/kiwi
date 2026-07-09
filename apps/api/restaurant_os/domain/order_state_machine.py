from enum import StrEnum

from restaurant_os.domain.errors import StateTransitionError


class OrderState(StrEnum):
    DRAFT = "DRAFT"
    ACCEPTED = "ACCEPTED"
    SENT_TO_PRODUCTION = "SENT_TO_PRODUCTION"
    IN_PRODUCTION = "IN_PRODUCTION"
    READY = "READY"
    IN_DELIVERY = "IN_DELIVERY"
    DELIVERED = "DELIVERED"
    CLOSED = "CLOSED"

    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    RETURNED = "RETURNED"

class OrderStateMachine:
    # Definimos las transiciones permitidas según el SDD 7.1
    VALID_TRANSITIONS: dict[OrderState, set[OrderState]] = {
        OrderState.DRAFT: {
            OrderState.ACCEPTED,
            OrderState.CANCELLED,
            OrderState.REJECTED
        },
        OrderState.ACCEPTED: {
            OrderState.SENT_TO_PRODUCTION,
            OrderState.CANCELLED
        },
        OrderState.SENT_TO_PRODUCTION: {
            OrderState.IN_PRODUCTION,
            OrderState.CANCELLED,
            OrderState.FAILED
        },
        OrderState.IN_PRODUCTION: {
            OrderState.READY,
            OrderState.CANCELLED
        },
        OrderState.READY: {
            OrderState.IN_DELIVERY,
            OrderState.DELIVERED,  # Para pedidos en mostrador / para recoger
            OrderState.CANCELLED
        },
        OrderState.IN_DELIVERY: {
            OrderState.DELIVERED,
            OrderState.RETURNED,
            OrderState.FAILED,
            OrderState.CANCELLED
        },
        OrderState.DELIVERED: {
            OrderState.CLOSED,
            OrderState.RETURNED
        },
        OrderState.CLOSED: set(),
        OrderState.CANCELLED: set(),
        OrderState.REJECTED: set(),
        OrderState.FAILED: set(),
        OrderState.RETURNED: {
            OrderState.CLOSED
        }
    }

    @classmethod
    def transition(cls, current_state: OrderState, next_state: OrderState) -> OrderState:
        """
        Valida e intenta realizar una transición de estado.
        Lanza StateTransitionError si la transición no es válida.
        """
        allowed_states = cls.VALID_TRANSITIONS.get(current_state, set())
        
        if next_state not in allowed_states:
            raise StateTransitionError(
                f"Transición inválida: de {current_state.value} a {next_state.value}"
            )
            
        return next_state
