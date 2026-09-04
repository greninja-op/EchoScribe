"""Unit tests for CredentialVault with keyring and local encrypted fallback."""
import os
import shutil
import tempfile
import uuid
from pathlib import Path
import pytest

from src.auth.credential_vault import CredentialVault


@pytest.fixture
def temp_vault():
    temp_dir = Path(tempfile.mkdtemp())
    service = f"test-vault-{uuid.uuid4().hex[:8]}"
    vault = CredentialVault(data_dir=temp_dir, service_name=service)
    yield vault, temp_dir
    # Cleanup test key if written to keyring
    try:
        vault.delete_key("deepgram")
    except Exception:
        pass
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_vault_key_lifecycle(temp_vault):
    vault, temp_dir = temp_vault

    # Initially empty
    assert not vault.has_key("deepgram")
    assert vault.get_key("deepgram") is None

    # Set key
    test_key = "dg_live_abcdef1234567890abcdef12345678"
    assert vault.set_key("deepgram", test_key)
    assert vault.has_key("deepgram")
    assert vault.get_key("deepgram") == test_key

    # Masked key
    masked = vault.get_masked_key("deepgram")
    assert masked.startswith("dg_l")
    assert masked.endswith("5678")
    assert "••••••••" in masked

    # Delete key
    assert vault.delete_key("deepgram")
    assert not vault.has_key("deepgram")
    assert vault.get_key("deepgram") is None


def test_vault_encrypted_file_fallback(temp_vault):
    vault, temp_dir = temp_vault
    # Force disabling keyring to exercise local encrypted fallback
    vault._keyring_available = False

    test_key = "dg_secret_test_key_xyz987654321"
    vault.set_key("deepgram", test_key)

    # Ensure encrypted file exists and does NOT contain raw key
    vault_file = temp_dir / ".vault.enc"
    assert vault_file.exists()
    content = vault_file.read_text(encoding="utf-8")
    assert test_key not in content

    # New vault instance loading from same dir
    vault2 = CredentialVault(data_dir=temp_dir, service_name=vault.service_name)
    vault2._keyring_available = False
    assert vault2.get_key("deepgram") == test_key
