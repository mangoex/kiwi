from __future__ import annotations

import pytest
from restaurant_os.domain.errors import StateTransitionError
from restaurant_os.domain.order_state_machine import OrderState, OrderStateMachine


def test_valid_happy_path_transitions():
    """Prueba el flujo ideal de un pedido (ej: a domicilio) de DRAFT a CLOSED."""
    state = OrderState.DRAFT
    state = OrderStateMachine.transition(state, OrderState.ACCEPTED)
    assert state == OrderState.ACCEPTED
    
    state = OrderStateMachine.transition(state, OrderState.SENT_TO_PRODUCTION)
    assert state == OrderState.SENT_TO_PRODUCTION
    
    state = OrderStateMachine.transition(state, OrderState.IN_PRODUCTION)
    assert state == OrderState.IN_PRODUCTION
    
    state = OrderStateMachine.transition(state, OrderState.READY)
    assert state == OrderState.READY
    
    state = OrderStateMachine.transition(state, OrderState.IN_DELIVERY)
    assert state == OrderState.IN_DELIVERY
    
    state = OrderStateMachine.transition(state, OrderState.DELIVERED)
    assert state == OrderState.DELIVERED
    
    state = OrderStateMachine.transition(state, OrderState.CLOSED)
    assert state == OrderState.CLOSED

def test_valid_pickup_transitions():
    """Prueba el flujo ideal para un pedido en mostrador o para recoger."""
    state = OrderState.READY
    state = OrderStateMachine.transition(state, OrderState.DELIVERED)
    assert state == OrderState.DELIVERED

def test_cancellation_from_various_states():
    """Prueba que los pedidos se puedan cancelar desde estados previos a la entrega."""
    cancellable_states = [
        OrderState.DRAFT,
        OrderState.ACCEPTED,
        OrderState.SENT_TO_PRODUCTION,
        OrderState.IN_PRODUCTION,
        OrderState.READY,
        OrderState.IN_DELIVERY
    ]
    
    for state in cancellable_states:
        new_state = OrderStateMachine.transition(state, OrderState.CANCELLED)
        assert new_state == OrderState.CANCELLED

def test_invalid_transitions():
    """Prueba transiciones que no están permitidas."""
    with pytest.raises(StateTransitionError) as exc_info:
        OrderStateMachine.transition(OrderState.DRAFT, OrderState.IN_PRODUCTION)
    assert "Transición inválida: de DRAFT a IN_PRODUCTION" in str(exc_info.value)
    
    with pytest.raises(StateTransitionError):
        OrderStateMachine.transition(OrderState.CLOSED, OrderState.DRAFT)
        
    with pytest.raises(StateTransitionError):
        OrderStateMachine.transition(OrderState.CANCELLED, OrderState.ACCEPTED)

def test_alternate_terminal_states():
    """Prueba estados alternos y retornos."""
    assert (
        OrderStateMachine.transition(OrderState.DRAFT, OrderState.REJECTED)
        == OrderState.REJECTED
    )
    assert (
        OrderStateMachine.transition(OrderState.SENT_TO_PRODUCTION, OrderState.FAILED)
        == OrderState.FAILED
    )
    assert (
        OrderStateMachine.transition(OrderState.IN_DELIVERY, OrderState.FAILED)
        == OrderState.FAILED
    )
    assert (
        OrderStateMachine.transition(OrderState.IN_DELIVERY, OrderState.RETURNED)
        == OrderState.RETURNED
    )
    
    # Después de devuelto se puede cerrar
    assert OrderStateMachine.transition(OrderState.RETURNED, OrderState.CLOSED) == OrderState.CLOSED
