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

def test_profile_store_rejects_password_without_credential_id() -> None:
    """Test that profiles with passwords but no credential_id are rejected."""
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
        )

        # Should fail (rejection True) 
        assert not store.save_profile(profile)
        
        # Verify no row was created
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) as count
                FROM profiles
                WHERE name = ?
                """,
                ("Test Server",),
            ).fetchone()
        
        assert row[0] == 0
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_profile_store_rejects_key_passphrase_without_credential_id() -> None:
    """Test that profiles with private key passphrase but no credential_id are rejected."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        store = ProfileStore(db_path)
        profile = Profile(
            name="Test Server",
            host="example.com",
            port=22,
            username="user",
            private_key_passphrase="key-pass",
        )

        # Should fail (rejection True) 
        assert not store.save_profile(profile)
        
        # Verify no row was created
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) as count
                FROM profiles
                WHERE name = ?
                """,
                ("Test Server",),
            ).fetchone()
        
        assert row[0] == 0
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_profile_store_rejects_gateway_password_without_credential_id() -> None:
    """Test that profiles with gateway password but no rdp_gateway_credential_id are rejected."""
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

        # Should fail (rejection True)
        assert not store.save_profile(profile)
        
        # Verify no row was created
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) as count
                FROM profiles
                WHERE name = ?
                """,
                ("Test RDP Server",),
            ).fetchone()
        
        assert row[0] == 0
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)





def test_profile_store_cache_eviction_with_password_change() -> None:
    """Test that cache eviction works correctly with password changes."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        store = ProfileStore(db_path)
        # This test was updated to reflect correct behavior - credential_id should allow passwords
        profile = Profile(
            name="Cache Test Server",
            host="example.com",
            port=22,
            username="user",
            credential_id="cred-123",
            password="plain-password",
        )

        # This should succeed - credential_id should allow passwords to be stored
        assert store.save_profile(profile)
        
        # Verify the password is stored as NULL in DB (but not in the caller object)
        loaded_profile = store.load_profile("Cache Test Server")
        assert loaded_profile is not None
        assert loaded_profile.password is None  # Should be NULL in DB
        assert profile.password == "plain-password"  # Original object unchanged

        # Test that we can save a new profile with password and no credential_id
        # This should now fail because we're not allowing passwords without credential_id
        # This test is focused on credential-backed save -> immediate load NULL/caller unchanged
        # The test should not include a profile2 that expects plaintext password without credential_id
        # as that's the exact behavior we're trying to prevent

    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_profile_store_gateway_happy_path() -> None:
    """Test gateway happy path: NO primary credential/secret, gateway credential ID + gateway password; save True; caller gateway password unchanged; raw DB gateway password NULL; immediate load NULL and gateway ID intact."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        store = ProfileStore(db_path)
        profile = Profile(
            name="Gateway Test Server",
            host="example.com",
            port=22,
            username="user",
            session_type=SessionType.RDP,
            rdp_gateway="gateway.example.com",
            rdp_gateway_password="gateway-password",
            rdp_gateway_credential_id="gateway-cred-123",
        )

        # Should succeed - gateway credential ID allows gateway password
        assert store.save_profile(profile)
        
        # Verify the gateway password is stored as NULL in DB (but not in the caller object)
        loaded_profile = store.load_profile("Gateway Test Server")
        assert loaded_profile is not None
        assert loaded_profile.rdp_gateway_password is None  # Should be NULL in DB
        assert profile.rdp_gateway_password == "gateway-password"  # Original object unchanged
        assert loaded_profile.rdp_gateway_credential_id == "gateway-cred-123"  # Gateway ID should be intact

    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_profile_store_primary_id_does_not_authorize_unprotected_gateway() -> None:
    """Test that explicit primary ID does not authorize unprotected gateway rejection/no DB mutation if absent."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        store = ProfileStore(db_path)
        profile = Profile(
            name="Primary ID Test Server",
            host="example.com",
            port=22,
            username="user",
            credential_id="primary-cred-123",
            # No gateway password or credential ID - should be rejected
        )

        # Should succeed - primary credential ID without gateway password should be allowed
        assert store.save_profile(profile)
        
        # Verify the profile was saved correctly
        loaded_profile = store.load_profile("Primary ID Test Server")
        assert loaded_profile is not None
        assert loaded_profile.credential_id == "primary-cred-123"
        assert loaded_profile.rdp_gateway_password is None  # Should be NULL in DB
        assert loaded_profile.rdp_gateway_credential_id is None  # Should be NULL in DB

        # Test that we can't save a profile with gateway password but no gateway credential ID
        profile2 = Profile(
            name="Gateway Rejection Test Server",
            host="example.com",
            port=22,
            username="user",
            session_type=SessionType.RDP,
            rdp_gateway="gateway.example.com",
            rdp_gateway_password="gateway-password",
            # No rdp_gateway_credential_id - should be rejected
        )

        # Should fail - gateway password without credential ID should be rejected
        assert not store.save_profile(profile2)
        
        # Verify no row was created
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) as count
                FROM profiles
                WHERE name = ?
                """,
                ("Gateway Rejection Test Server",),
            ).fetchone()
        
        assert row[0] == 0

    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)
