import re

from app.banking.state import STATE_PATTERN, new_state, nonce_of


def test_new_state_carries_port_and_returns_its_nonce() -> None:
    state, nonce = new_state(8100)

    assert re.fullmatch(STATE_PATTERN, state)
    assert state.startswith("8100.")
    assert nonce_of(state) == nonce
