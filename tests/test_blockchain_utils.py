import pytest

from nictbw.blockchain.utils import raw_tx_bytes_to_hex, raw_tx_hex_to_bytes


def test_raw_tx_hex_to_bytes_accepts_plain_hex() -> None:
    assert raw_tx_hex_to_bytes("00a1ff") == b"\x00\xa1\xff"


def test_raw_tx_hex_to_bytes_accepts_prefixed_hex() -> None:
    assert raw_tx_hex_to_bytes("0x00A1ff") == b"\x00\xa1\xff"


def test_raw_tx_hex_to_bytes_rejects_odd_length() -> None:
    with pytest.raises(ValueError, match="even number"):
        raw_tx_hex_to_bytes("abc")


def test_raw_tx_hex_to_bytes_rejects_invalid_characters() -> None:
    with pytest.raises(ValueError, match="invalid hexadecimal"):
        raw_tx_hex_to_bytes("0x00zz")


def test_raw_tx_bytes_to_hex_without_prefix() -> None:
    assert raw_tx_bytes_to_hex(b"\x00\xa1\xff") == "00a1ff"


def test_raw_tx_bytes_to_hex_with_prefix() -> None:
    assert raw_tx_bytes_to_hex(b"\x00\xa1\xff", prefix=True) == "0x00a1ff"


def test_raw_tx_bytes_to_hex_accepts_memoryview() -> None:
    assert raw_tx_bytes_to_hex(memoryview(b"\x12\x34")) == "1234"


def test_raw_tx_bytes_to_hex_rejects_non_bytes_like() -> None:
    with pytest.raises(ValueError, match="bytes-like"):
        raw_tx_bytes_to_hex("1234")  # type: ignore[arg-type]
