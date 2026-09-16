import socket
import time


def check_tcp_reachability(host: str, port: int = 22, timeout: float = 3.0) -> tuple[bool, float | None]:
    """Check whether a device's management port is reachable.

    Performs only a TCP handshake (SYN/ACK) against `port` -- no protocol
    data is sent and no authentication is attempted, so this is safe to run
    against any device without altering its state.
    """
    start = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            latency_ms = (time.monotonic() - start) * 1000
            return True, round(latency_ms, 2)
    except (OSError, socket.timeout):
        return False, None
