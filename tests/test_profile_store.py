"""Tests for profile store."""

import tempfile
import os
import sqlite3
from openadmindesk.core.profile import Profile, SessionType
from openadmindesk.core.profile_store import ProfileStore


def test_profile_store_creation() -> None:
    """Test profile store creation."""
    # Use temporary database for testing
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        store = ProfileStore(db_path)
        assert store is not None
    finally:
        # Clean up
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_profile_store_save_and_load() -> None:
    """Test saving and loading profiles."""
    # Use temporary database for testing
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        store = ProfileStore(db_path)

        # Create and save a profile
        profile = Profile(
            name="Test Server",
            host="example.com",
            port=22,
            username="user"
        )

        success = store.save_profile(profile)
        assert success

        # Load the profile
        loaded_profile = store.load_profile("Test Server")
        assert loaded_profile is not None
        assert loaded_profile.name == "Test Server"
        assert loaded_profile.host == "example.com"
        assert loaded_profile.port == 22
        assert loaded_profile.username == "user"

    finally:
        # Clean up
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_profile_store_load_all() -> None:
    """Test loading all profiles."""
    # Use temporary database for testing
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        store = ProfileStore(db_path)

        # Save multiple profiles
        profile1 = Profile(
            name="Server 1",
            host="server1.com",
            port=22,
            username="user1"
        )

        profile2 = Profile(
            name="Server 2",
            host="server2.com",
            port=22,
            username="user2"
        )

        store.save_profile(profile1)
        store.save_profile(profile2)

        # Load all profiles
        profiles = store.load_all_profiles()
        assert len(profiles) == 2

        # Check that we got the right profiles
        profile_names = [p.name for p in profiles]
        assert "Server 1" in profile_names
        assert "Server 2" in profile_names

    finally:
        # Clean up
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_profile_store_delete() -> None:
    """Test deleting profiles."""
    # Use temporary database for testing
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        store = ProfileStore(db_path)

        # Create and save a profile
        profile = Profile(
            name="Test Server",
            host="example.com",
            port=22,
            username="user"
        )

        store.save_profile(profile)

        # Verify it exists
        loaded_profile = store.load_profile("Test Server")
        assert loaded_profile is not None

        # Delete the profile
        success = store.delete_profile("Test Server")
        assert success

        # Verify it's deleted
        loaded_profile = store.load_profile("Test Server")
        assert loaded_profile is None

    finally:
        # Clean up
        if os.path.exists(db_path):
            os.unlink(db_path)

def test_profile_store_persists_password_when_no_vault() -> None:
    """Password is stored in DB when provided directly (vault not used)."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        store = ProfileStore(db_path)
        profile = Profile(
            name="NoVault Server",
            host="example.com",
            port=22,
            username="user",
            password="plain-password",
            private_key_passphrase="key-pass",
            rdp_gateway_password="rdp-pass",
        )

        assert store.save_profile(profile)
        store.clear_cache()

        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                """
                SELECT password, private_key_passphrase, rdp_gateway_password
                FROM profiles
                WHERE name = ?
                """,
                ("NoVault Server",),
            ).fetchone()

        # All secrets are stored (no vault to delegate to)
        assert row[0] == "plain-password"
        assert row[1] == "key-pass"
        assert row[2] == "rdp-pass"

        loaded_profile = store.load_profile("NoVault Server")
        assert loaded_profile is not None
        assert loaded_profile.password == "plain-password"
        assert loaded_profile.private_key_passphrase == "key-pass"
        assert loaded_profile.rdp_gateway_password == "rdp-pass"
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_profile_store_rejects_no_credential_id_for_passwords() -> None:
    """Test that profiles with passwords but no credential_id are allowed (rejection False) but logged."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        store = ProfileStore(db_path)
        profile = Profile(
            name="Test Server",
            host="example.com",
            port=22,
            username="user",
            password="plain-password",
            private_key_passphrase="key-pass",
        )

        # Should succeed (rejection False) but log warnings
        assert store.save_profile(profile)

        # Verify passwords are stored in DB
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                """
                SELECT password, private_key_passphrase
                FROM profiles
                WHERE name = ?
                """,
                ("Test Server",),
            ).fetchone()

        assert row[0] == "plain-password"
        assert row[1] == "key-pass"
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_profile_store_rejects_no_credential_id_for_gateway_password() -> None:
    """Test that profiles with gateway password but no rdp_gateway_credential_id are allowed (rejection False) but logged."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        store = ProfileStore(db_path)
        profile = Profile(
            name="Test RDP Server",
            host="example.com",
            port=22,
            username="user",
            session_type=SessionType.RDP,
            rdp_gateway="gateway.example.com",
            rdp_gateway_password="gateway-password",
        )

        # Should succeed (rejection False) but log warnings
        assert store.save_profile(profile)

        # Verify gateway password is stored in DB
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                """
                SELECT rdp_gateway_password
                FROM profiles
                WHERE name = ?
                """,
                ("Test RDP Server",),
            ).fetchone()

        assert row[0] == "gateway-password"
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_profile_store_persists_null_for_credential_backed_profiles() -> None:
    """Test that credential-backed saves persist SQL NULL for passwords without mutating caller."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        store = ProfileStore(db_path)
        profile = Profile(
            name="Credential Backed Server",
            host="example.com",
            port=22,
            username="user",
            credential_id="cred-123",
            password="plain-password",
            private_key_passphrase="key-pass",
            rdp_gateway_password="rdp-pass",
        )

        # Save the profile
        assert store.save_profile(profile)

        # Verify that passwords are stored as NULL in DB (not in DB)
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                """
                SELECT password, private_key_passphrase, rdp_gateway_password
                FROM profiles
                WHERE name = ?
                """,
                ("Credential Backed Server",),
            ).fetchone()

        # Passwords should be NULL in DB since credential_id is set
        assert row[0] is None
        assert row[1] is None
        assert row[2] is None

        # But caller's profile object should still have the passwords
        assert profile.password == "plain-password"
        assert profile.private_key_passphrase == "key-pass"
        assert profile.rdp_gateway_password == "rdp-pass"

        # Load the profile and verify it's NULL
        loaded_profile = store.load_profile("Credential Backed Server")
        assert loaded_profile is not None
        assert loaded_profile.password is None
        assert loaded_profile.private_key_passphrase is None
        assert loaded_profile.rdp_gateway_password is None

    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_profile_store_evicts_cache_on_successful_save() -> None:
    """Test that successful save evicts profile cache so immediate load reflects DB NULL."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        store = ProfileStore(db_path)
        profile = Profile(
            name="Cache Test Server",
            host="example.com",
            port=22,
            username="user",
            credential_id="cred-123",
            password="plain-password",
        )

        # Save the profile with credential_id (should store NULL in DB)
        assert store.save_profile(profile)

        # Load the profile to populate cache
        loaded_profile = store.load_profile("Cache Test Server")
        assert loaded_profile is not None
        assert loaded_profile.password is None  # Should be NULL from DB

        # Now update the profile with a password (but no credential_id)
        profile.password = "new-password"
        profile.credential_id = None  # Remove credential_id

        # Save again - should store the password in DB
        assert store.save_profile(profile)

        # Load again - should get the new password
        loaded_profile = store.load_profile("Cache Test Server")
        assert loaded_profile is not None
        assert loaded_profile.password == "new-password"

    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)
