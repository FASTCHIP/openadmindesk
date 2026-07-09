# Test Plan

## Unit Tests

Required early tests:

- profile validation accepts valid SSH profiles,
- profile validation rejects missing host/name and invalid ports,
- SSH argv builder maps options correctly,
- SSH argv builder never uses shell strings,
- tunnel argument builder validates ports and targets,
- vault encrypt/decrypt round trip works with fake secrets,
- wrong vault password fails,
- no plaintext secret appears in serialized vault data.

## UI Smoke Tests

When PySide6 is available:

- main window creates without crashing,
- connection tree widget creates,
- tab workspace creates,
- profile editor validates required fields,
- vault dialog shows locked and unlocked states.

## Integration Tests

Integration tests that require real SSH servers must be optional and clearly
marked. They must never use real production credentials.

## Manual Checks

For UI changes, record:

- screen size tested,
- scaling factor if relevant,
- what was clicked,
- observed result.

## Packaging Checks

Before release:

- build AppImage,
- launch AppImage on clean Ubuntu LTS,
- launch AppImage on one RHEL-family distribution,
- verify SSH command availability,
- verify X11/Xwayland dependency detection.

