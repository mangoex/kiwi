"""Synthetic private original encryption, no production key or file."""

import base64
import importlib
import json

import pytest
from restaurant_os.config import get_settings


@pytest.fixture(autouse=True)
def keyring(monkeypatch):
    monkeypatch.setenv(
        "RESTAURANTOS_FISCAL_ENCRYPTION_KEYS",
        json.dumps({"test": base64.b64encode(bytes(range(32))).decode()}),
    )
    monkeypatch.setenv("RESTAURANTOS_FISCAL_ACTIVE_ENCRYPTION_KEY_ID", "test")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def api():
    return importlib.import_module("restaurant_os.supplier_xml_crypto")


@pytest.mark.parametrize(
    "original",
    [b"<r>private original</r>", "<r>é</r>".encode("utf-16"), b"x" * 1048576],
    ids=["small", "utf16", "one-mib"],
)
def test_exact_original_ciphertext_and_nonce(original):
    crypto = api()
    first = crypto.seal_original(original, "supplier-xml:org:A:original:id:hash")
    second = crypto.seal_original(original, "supplier-xml:org:A:original:id:hash")
    assert first != second and "private original" not in first
    assert crypto.unseal_original(first, "supplier-xml:org:A:original:id:hash") == original


@pytest.mark.parametrize("change", ["context", "ciphertext", "version", "extra", "nonce", "key"])
def test_tampering_never_returns_original(change):
    crypto = api()
    value = json.loads(crypto.seal_original(b"<r/>", "scope"))
    if change == "ciphertext":
        value["ciphertext"] = base64.b64encode(b"wrong").decode()
    if change == "version":
        value["version"] = True
    if change == "extra":
        value["extra"] = "untrusted"
    if change == "nonce":
        value["nonce"] = "AA=="
    if change == "key":
        value["key_id"] = "unknown"
    with pytest.raises(RuntimeError, match="supplier_xml_crypto_unavailable"):
        crypto.unseal_original(json.dumps(value), "different" if change == "context" else "scope")


def test_missing_key_and_oversize_fail_closed(monkeypatch):
    crypto = api()
    with pytest.raises(RuntimeError, match="supplier_xml_crypto_unavailable"):
        crypto.seal_original(b"x" * 1048577, "scope")
    monkeypatch.delenv("RESTAURANTOS_FISCAL_ACTIVE_ENCRYPTION_KEY_ID")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="supplier_xml_crypto_unavailable"):
        crypto.seal_original(b"<r/>", "scope")
