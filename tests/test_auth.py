import pytest
from dark_alt.auth import hash_password, verify_password

def test_scrypt_password_hash_roundtrip():
    encoded=hash_password('correct-horse-battery-staple')
    assert encoded.startswith('scrypt$')
    assert verify_password('correct-horse-battery-staple',encoded)
    assert not verify_password('incorrect',encoded)
