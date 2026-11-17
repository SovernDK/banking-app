import base64
import re

from app.banking.state import STATE_PATTERN, new_state, nonce_of


def test_new_state_carries_port_and_returns_its_nonce() -> None:
    state, nonce = new_state(8100)

    assert re.fullmatch(STATE_PATTERN, state)
    assert state.startswith("8100.")
    assert nonce_of(state) == nonce


def test_new_state_carries_public_origin_for_the_relay_when_given() -> None:
    state, nonce = new_state(8100, "https://yiji.home.net")

    assert re.fullmatch(STATE_PATTERN, state)
    target = state.partition(".")[0]
    assert base64.urlsafe_b64decode(target + "=" * (-len(target) % 4)) == b"https://yiji.home.net"
    assert nonce_of(state) == nonce
