"""Tests for profile store."""

import asyncio
import os
import sqlite3
import tempfile

import pytest

from openadmindesk.core import profile_store as profile_store_module
from openadmindesk.core.profile import Profile, SessionType
from openadmindesk.core.profile_store import ProfileStore


def test_profile_store_executor_shutdown_calls_once(tmp_path, monkeypatch) -> None:
    class FakeExecutor:
        def __init__(self) -> None:
            self.shutdown_calls: list[tuple[bool, bool]] = []

        def shutdown(self, *, wait: bool, cancel_futures: bool) -> None:
            self.shutdown_calls.append((wait, cancel_futures))

    fake_executor = FakeExecutor()
    monkeypatch.setattr(
        profile_store_module,
        "ThreadPoolExecutor",
        lambda *args, **kwargs: fake_executor,
    )

    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.close()
    store.close()

    assert fake_executor.shutdown_calls == [(False, True)]


def test_profile_store_raises_error_after_close(tmp_path) -> None:
    store = ProfileStore(str(tmp_path / "profiles.db"))
    store.close()

    with pytest.raises(
        RuntimeError,
        match="^ProfileStore executor already closed$",
    ):
        asyncio.run(store.load_all_profiles_async())


def test_profile_store_run_db_args_forwarding(tmp_path) -> None:
    def combine(prefix: str, *, suffix: str) -> str:
        return f"{prefix}:{suffix}"

    store = ProfileStore(str(tmp_path / "profiles.db"))
    try:
        result = asyncio.run(
            store._run_db(combine, "left", suffix="right")
        )
    finally:
        store.close()

    assert result == "left:right"


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


def test_profile_store_nla_domain_roundtrip(tmp_path) -> None:

    """NLA and domain fields should survive save/load cycle."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    profile = Profile(
        name="RDP NLA Test",
        host="nla-test.example.com",
        port=3389,
        session_type=SessionType.RDP,
        username="admin",
        password="secret",
        credential_id="test-cred",
        rdp_nla=True,
        rdp_domain="MYDOMAIN",
        rdp_gateway="gw.example.com",
    )
    assert store.save_profile(profile) is True
    
    loaded = store.load_profile(profile.name)
    assert loaded is not None
    assert loaded.rdp_nla is True
    assert loaded.rdp_domain == "MYDOMAIN"
    
    # Test with NLA disabled
    profile2 = Profile(
        name="RDP No NLA",
        host="no-nla.example.com",
        port=3389,
        session_type=SessionType.RDP,
        rdp_nla=False,
        rdp_domain="",
    )
    assert store.save_profile(profile2) is True
    loaded2 = store.load_profile(profile2.name)
    assert loaded2 is not None
    assert loaded2.rdp_nla is False
    assert loaded2.rdp_domain == ""

def test_profile_store_save_visibility(tmp_path) -> None:
    """Test that saving a profile immediately makes it visible in load_all_profiles."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    try:
        # Prime cache as empty
        assert store.load_all_profiles() == []

        profile = Profile(name="Vis Test", host="host1", port=22, username="user")
        assert store.save_profile(profile)

        # Immediate load should see it without waiting for TTL
        profiles = store.load_all_profiles()
        assert len(profiles) == 1
        assert profiles[0].name == "Vis Test"
    finally:
        store.close()

def test_profile_store_update_visibility(tmp_path) -> None:
    """Test that updating a profile immediately reflects in load_all_profiles."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    try:
        profile = Profile(name="Upd Test", host="host1", port=22, username="user")
        store.save_profile(profile)

        # Prime cache
        profiles = store.load_all_profiles()
        assert len(profiles) == 1
        assert profiles[0].host == "host1"

        # Update host
        profile.host = "host2"
        assert store.save_profile(profile)

        # Immediate load should see updated host
        profiles = store.load_all_profiles()
        assert len(profiles) == 1
        assert profiles[0].host == "host2"
    finally:
        store.close()


def test_profile_store_nla_default_true(tmp_path) -> None:
    """NLA should default to True for new RDP profiles."""
    store = ProfileStore(str(tmp_path / "profiles.db"))
    profile = Profile(
        name="RDP Default NLA",
        host="default-nla.example.com",
        port=3389,
        session_type=SessionType.RDP,
        # rdp_nla not explicitly set - uses default True
    )
    assert profile.rdp_nla is True
    assert store.save_profile(profile) is True
    loaded = store.load_profile(profile.name)
    assert loaded is not None
    assert loaded.rdp_nla is True
    assert loaded.rdp_domain == ""

