"""Contract tests for the GitHub release workflow."""

from __future__ import annotations

from pathlib import Path


def _workflow_text() -> str:
    return Path(".github/workflows/release.yml").read_text()


def test_release_workflow_triggers_and_metadata() -> None:
    text = _workflow_text()

    assert "name: Build release artifacts" in text
    assert "workflow_dispatch:" in text
    assert "push:" in text
    assert "tags:" in text and "'v*'" in text
    assert "contents: read" in text
    assert "group: release-${{ github.ref }}" in text
    assert "cancel-in-progress: false" in text
    assert "runs-on: ubuntu-latest" in text
    assert "open('pyproject.toml', 'rb')" in text
    assert '>> "$GITHUB_OUTPUT"' in text
    assert "$GITHUB_REF_TYPE" in text
    assert "$GITHUB_REF_NAME" in text
    assert '"v$VERSION"' in text
    assert "pull_request:" not in text


def test_windows_release_job_builds_and_smokes_preview() -> None:
    text = _workflow_text()

    assert "runs-on: windows-latest" in text
    assert 'python -m pip install ".[build]"' in text
    assert "python tools/build.py check" in text
    assert "python tools/build.py windows-exe" in text
    assert text.count("shell: pwsh") == 2
    assert "Start-Process" in text and "-PassThru" in text
    assert "$process.ExitCode" in text
    assert "OpenAdminDesk-$env:VERSION-windows-x86_64.exe" in text
    assert "SHA256SUMS-windows" in text
    assert "actions/upload-artifact@v4" in text
    assert "retention-days: 14" in text
    assert "$LASTEXITCODE" not in text
    assert "NoNewWindow" not in text


def test_linux_release_job_uses_pinned_tools_and_real_builds() -> None:
    text = _workflow_text()

    assert "runs-on: ubuntu-24.04" in text
    assert 'python -m pip install "poetry==2.3.2" .' in text
    assert "https://api.github.com/repos/AppImage/appimagetool/releases/assets/324406882" in text
    assert "a6d71e2b6cd66f8e8d16c37ad164658985e0cf5fcaa950c90a482890cb9d13e0" in text
    assert "sha256sum --check" in text
    for command in ("check", "python-pkg", "appimage", "deb", "rpm"):
        assert f"python tools/build.py {command}" in text
    assert 'HOME="$RUNNER_TEMP/rpm-home"' in text
    assert "dist/openadmindesk-*-py3-none-any.whl" in text
    assert "dist/openadmindesk-*.tar.gz" in text
    assert "dist/OpenAdminDesk-x86_64.AppImage" in text
    assert "dist/openadmindesk_*_all.deb" in text
    assert "dist/openadmindesk-*-1.noarch.rpm" in text
    assert "APPIMAGE_EXTRACT_AND_RUN=1" in text
    assert "dpkg-deb -f" in text
    assert "rpm -qp --qf" in text
    assert "SHA256SUMS-linux" in text
    for forbidden in (
        "AppImage/AppImageKit",
        "openadomindesk",
        "rpm -qpq",
        "|| true",
        "python-package-name",
        "pip install appimage",
        "pip install deb",
    ):
        assert forbidden not in text


def test_tag_release_job_merges_and_publishes_assets() -> None:
    text = _workflow_text()

    assert "needs: [metadata, windows, linux]" in text
    assert "if: startsWith(github.ref, 'refs/tags/v')" in text
    assert "contents: write" in text
    assert "actions/download-artifact@v4" in text
    assert 'pattern: "*-${{ needs.metadata.outputs.version }}"' in text
    assert "merge-multiple: true" in text
    assert "rm -f release-dist/SHA256SUMS-linux release-dist/SHA256SUMS-windows" in text
    assert "OpenAdminDesk-$VERSION-windows-x86_64.exe" in text
    assert "OpenAdminDesk-$VERSION-linux-x86_64.AppImage" in text
    assert "sha256sum -- * > SHA256SUMS" in text
    assert "sha256sum --check SHA256SUMS" in text
    assert "GH_TOKEN: ${{ github.token }}" in text
    assert 'gh release view "$tag"' in text
    assert 'gh release upload "$tag" release-dist/* --clobber' in text
    assert 'gh release create "$tag"' in text
    assert "--verify-tag" in text and "--notes-file" in text
    assert r'if [[ ! "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then' in text
    assert "prerelease_args+=(--prerelease)" in text
    assert "unsigned preview" in text and "No credentials are bundled" in text
    assert "softprops/action-gh-release" not in text


def test_release_workflow_has_expected_job_and_action_counts() -> None:
    text = _workflow_text()

    assert text.count("runs-on:") == 4
    assert text.count("actions/checkout@v4") == 4
    assert text.count("actions/upload-artifact@v4") == 2
    assert text.count("actions/download-artifact@v4") == 1
    for job in ("metadata", "windows", "linux", "release"):
        assert text.count(f"  {job}:\n") == 1

