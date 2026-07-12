"""Tests for profile import/export."""

import tempfile
import os
import json
from openadmindesk.core.profile import Profile
from openadmindesk.core.profile_import_export import ProfileImporter, ProfileExporter


def test_profile_importer_json() -> None:
    """Test importing profiles from JSON."""
    # Create test data
    test_data = [
        {
            "name": "Test Server 1",
            "host": "example1.com",
            "port": 22,
            "username": "user1"
        },
        {
            "name": "Test Server 2",
            "host": "example2.com",
            "port": 22,
            "username": "user2"
        }
    ]
    
    # Write test JSON file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        tmp.write(json.dumps(test_data))
        tmp_path = tmp.name
    
    try:
        # Import profiles
        profiles = ProfileImporter.import_from_json(tmp_path)
        assert len(profiles) == 2
        assert profiles[0].name == "Test Server 1"
        assert profiles[1].name == "Test Server 2"
    finally:
        # Clean up
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_profile_exporter_json() -> None:
    """Test exporting profiles to JSON."""
    # Create test profiles
    profiles = [
        Profile(
            name="Test Server 1",
            host="example1.com",
            port=22,
            username="user1"
        ),
        Profile(
            name="Test Server 2",
            host="example2.com",
            port=22,
            username="user2"
        )
    ]
    
    # Export to JSON
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        success = ProfileExporter.export_to_json(profiles, tmp_path)
        assert success
        
        # Verify file was created
        assert os.path.exists(tmp_path)
        
        # Verify content
        with open(tmp_path, 'r') as f:
            content = f.read()
            assert "Test Server 1" in content
            assert "Test Server 2" in content
    finally:
        # Clean up
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_profile_importer_csv() -> None:
    """Test importing profiles from CSV."""
    # Create test CSV content
    csv_content = """name,host,port,username
Test Server 1,example1.com,22,user1
Test Server 2,example2.com,22,user2"""
    
    # Write test CSV file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp:
        tmp.write(csv_content)
        tmp_path = tmp.name
    
    try:
        # Import profiles
        profiles = ProfileImporter.import_from_csv(tmp_path)
        assert len(profiles) == 2
        assert profiles[0].name == "Test Server 1"
        assert profiles[1].name == "Test Server 2"
    finally:
        # Clean up
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_profile_exporter_csv() -> None:
    """Test exporting profiles to CSV."""
    # Create test profiles
    profiles = [
        Profile(
            name="Test Server 1",
            host="example1.com",
            port=22,
            username="user1"
        ),
        Profile(
            name="Test Server 2",
            host="example2.com",
            port=22,
            username="user2"
        )
    ]
    
    # Export to CSV
    with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        success = ProfileExporter.export_to_csv(profiles, tmp_path)
        assert success
        
        # Verify file was created
        assert os.path.exists(tmp_path)
        
        # Verify content
        with open(tmp_path, 'r') as f:
            content = f.read()
            assert "Test Server 1" in content
            assert "Test Server 2" in content
    finally:
        # Clean up
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

def test_profile_export_omits_plaintext_secrets() -> None:
    """Plain JSON/CSV export should contain metadata, not credentials."""
    profile = Profile(
        name="Secret Server",
        host="example.com",
        port=22,
        username="user",
        password="plain-password",
        private_key_passphrase="plain-key-passphrase",
        rdp_gateway_password="plain-rdp-password",
        credential_id="vault-account-1",
    )

    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp:
        json_path = tmp.name
    with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as tmp:
        csv_path = tmp.name

    try:
        assert ProfileExporter.export_to_json([profile], json_path)
        assert ProfileExporter.export_to_csv([profile], csv_path)

        with open(json_path, 'r') as f:
            json_content = f.read()
        with open(csv_path, 'r') as f:
            csv_content = f.read()

        for content in (json_content, csv_content):
            assert "plain-password" not in content
            assert "plain-key-passphrase" not in content
            assert "plain-rdp-password" not in content
            assert "credential_id" in content
    finally:
        for path in (json_path, csv_path):
            if os.path.exists(path):
                os.unlink(path)


def test_profile_import_drops_plaintext_secret_fields() -> None:
    """Imported profile metadata should not hydrate plaintext credentials."""
    test_data = {
        "name": "Imported Secret",
        "host": "example.com",
        "port": 22,
        "username": "user",
        "password": "plain-password",
        "private_key_passphrase": "plain-key-passphrase",
        "rdp_gateway_password": "plain-rdp-password",
        "credential_id": "vault-account-1",
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        tmp.write(json.dumps(test_data))
        tmp_path = tmp.name

    try:
        profiles = ProfileImporter.import_from_json(tmp_path)
        assert len(profiles) == 1
        assert profiles[0].password is None
        assert profiles[0].private_key_passphrase is None
        assert profiles[0].rdp_gateway_password is None
        assert profiles[0].credential_id == "vault-account-1"
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
