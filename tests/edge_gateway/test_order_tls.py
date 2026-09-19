import pytest
from edge_gateway.__main__ import validate_listener


def test_lan_listener_requires_explicit_tls_files(tmp_path):
    assert validate_listener("127.0.0.1", None, None) == {}
    with pytest.raises(ValueError, match="TLS"):
        validate_listener("0.0.0.0", None, None)
    with pytest.raises(ValueError):
        validate_listener("192.168.1.5", "relative.pem", "relative-key.pem")
