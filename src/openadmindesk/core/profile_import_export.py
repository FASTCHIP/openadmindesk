"""Profile import/export utilities."""

from __future__ import annotations

import json
import csv
from typing import List

from openadmindesk.core.profile import Profile

SECRET_PROFILE_FIELDS = {"password", "private_key_passphrase", "rdp_gateway_password"}


def _public_profile_dict(profile: Profile) -> dict:
    """Return profile metadata safe for plain JSON/CSV export."""
    profile_dict = profile.__dict__.copy()
    for field in SECRET_PROFILE_FIELDS:
        profile_dict.pop(field, None)
    if 'session_type' in profile_dict:
        profile_dict['session_type'] = profile_dict['session_type'].value
    return {k: v for k, v in profile_dict.items() if v is not None}


def _sanitize_profile_data(profile_data: dict) -> dict:
    """Drop secret fields from imported profile metadata."""
    return {k: v for k, v in profile_data.items() if k not in SECRET_PROFILE_FIELDS}


class ProfileImporter:
    """Utilities for importing profiles."""
    
    @staticmethod
    def import_from_json(file_path: str) -> List[Profile]:
        """Import profiles from JSON file."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            profiles = []
            if isinstance(data, list):
                for profile_data in data:
                    profile = Profile(**_sanitize_profile_data(profile_data))
                    profiles.append(profile)
            elif isinstance(data, dict):
                profile = Profile(**_sanitize_profile_data(data))
                profiles.append(profile)
            
            return profiles
        except Exception:
            return []
    
    @staticmethod
    def import_from_csv(file_path: str) -> List[Profile]:
        """Import profiles from CSV file."""
        try:
            profiles = []
            with open(file_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    profile = Profile(**_sanitize_profile_data(row))
                    profiles.append(profile)
            return profiles
        except Exception:
            return []


class ProfileExporter:
    """Utilities for exporting profiles."""
    
    @staticmethod
    def export_to_json(profiles: List[Profile], file_path: str) -> bool:
        """Export profiles to JSON file."""
        try:
            # Convert profiles to dict format
            data = []
            for profile in profiles:
                data.append(_public_profile_dict(profile))
            
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            return False
    
    @staticmethod
    def export_to_csv(profiles: List[Profile], file_path: str) -> bool:
        """Export profiles to CSV file."""
        try:
            if not profiles:
                return False
            
            # Get field names that are safe for plain CSV export.
            fieldnames = list(_public_profile_dict(profiles[0]).keys())
            
            with open(file_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for profile in profiles:
                    writer.writerow(_public_profile_dict(profile))
            return True
        except Exception:
            return False