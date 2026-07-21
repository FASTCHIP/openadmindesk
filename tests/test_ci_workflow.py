"""
Contract tests for the CI workflow configuration.
Ensures that the CI pipeline maintains required security, tooling, and build steps.
"""

from pathlib import Path
import yaml
from typing import Any, Dict

def _workflow_text() -> str:
    """Read the CI workflow file as text."""
    path = Path(".github/workflows/ci.yml")
    return path.read_text(encoding="utf-8")

def _workflow_data() -> Dict[str, Any]:
    """Parse the CI workflow file as YAML."""
    text = _workflow_text()
    data = yaml.safe_load(text)
    assert isinstance(data, dict), "Workflow file must be a YAML mapping"
    return data

def _get_steps(job_name: str, data: Dict[str, Any]) -> list:
    """Extract steps for a given job."""
    job = data.get("jobs", {}).get(job_name, {})
    return job.get("steps", [])

def test_workflow_triggers():
    """Verify workflow triggers and branch constraints."""
    data = _workflow_data()
    # PyYAML 1.1 may map 'on' to boolean True if it's empty or structured oddly
    # Normalize 'on' key
    on = data.get("on", data.get(True))
    assert on is not None, "Workflow must have 'on' trigger section"
    
    # Check push and pull_request triggers
    for trigger in ["push", "pull_request"]:
        assert trigger in on, f"Trigger '{trigger}' missing"
        branches = on[trigger].get("branches", [])
        assert branches == ["main"], f"Trigger '{trigger}' must be restricted to ['main']"

def test_workflow_permissions_concurrency():
    """Verify permissions and concurrency settings."""
    data = _workflow_data()
    
    # Permissions
    permissions = data.get("permissions", {})
    assert permissions.get("contents") == "read", "Permissions 'contents' must be 'read'"
    
    # Concurrency
    concurrency = data.get("concurrency", {})
    assert concurrency.get("group") == "ci-${{ github.workflow }}-${{ github.ref }}", "Incorrect concurrency group"
    assert concurrency.get("cancel-in-progress") is True, "Concurrency cancel-in-progress must be true"

def test_workflow_tooling_and_install():
    """Verify tooling installation, lockfile validation, and test commands."""
    text = _workflow_text()
    data = _workflow_data()
    
    # Lockfile validation: once in each job (total 2)
    assert text.count("poetry check --lock") == 2, "Poetry lock check should appear exactly twice"
    assert text.count("Validate lockfile") == 2, "Step 'Validate lockfile' should appear exactly twice"
    
    # Poetry installation
    assert text.count('python -m pip install "poetry==2.3.2"') == 2, "Pinned Poetry install should appear exactly twice"
    assert "pip install poetry" not in text.replace('python -m pip install "poetry==2.3.2"', ""), "Bare 'pip install poetry' should be absent"
    
    # Lint job specifics
    lint_steps = _get_steps("lint-and-test", data)
    lint_runs = [s.get("run", "") for s in lint_steps if s.get("run")]
    lint_runs_text = "\n".join(lint_runs)
    
    assert "poetry install --with dev --no-interaction" in lint_runs_text, "Lint job must use --no-interaction"
    assert "poetry run ruff check src tools tests" in lint_runs_text, "Ruff command must be 'poetry run ruff check src tools tests'"
    assert "xvfb-run --auto-servernum poetry run pytest -q --tb=short" in lint_runs_text, "Xvfb pytest command missing"
    
    # Direct import symbols
    assert "from openadmindesk.core.rdp_client import RdpCertTrustStore" in lint_runs_text
    assert "from openadmindesk.core.tunnel_manager import TunnelManager" in lint_runs_text
    assert "from openadmindesk.core.settings import AppSettings" in lint_runs_text
    assert "from openadmindesk.ui.tools_hub import ToolsHub" in lint_runs_text
    
    # Build job specifics: no poetry install
    build_steps = _get_steps("build-check", data)
    build_runs = [s.get("run", "") for s in build_steps if s.get("run")]
    build_runs_text = "\n".join(build_runs)
    assert "poetry install" not in build_runs_text, "Build job should not have 'poetry install'"

def test_workflow_build_job():
    """Verify the build-check job configuration."""
    data = _workflow_data()
    job = data.get("jobs", {}).get("build-check", {})
    
    assert job.get("needs") == "lint-and-test", "build-check must depend on lint-and-test"
    
    build_steps = job.get("steps", [])
    build_runs = [s.get("run", "") for s in build_steps if s.get("run")]
    build_runs_text = "\n".join(build_runs)
    
    assert "poetry build" in build_runs_text, "poetry build missing in build-check"
    assert "python tools/build.py python-pkg" in build_runs_text, "python tools/build.py python-pkg missing in build-check"

def test_workflow_forbidden_and_versions():
    """Verify forbidden patterns and action versions."""
    text = _workflow_text()
    data = _workflow_data()
    
    # Forbidden patterns
    assert "PYTHONPATH" not in text, "PYTHONPATH should not be used in CI"
    assert "|| true" not in text, "|| true should not be used in CI"
    
    # Action versions
    all_uses = []
    for job in data.get("jobs", {}).values():
        for step in job.get("steps", []):
            if "uses" in step:
                all_uses.append(step["uses"])
    
    assert all_uses.count("actions/checkout@v7") == 2, "Should use actions/checkout@v7 exactly twice"
    assert all_uses.count("actions/setup-python@v6") == 2, "Should use actions/setup-python@v6 exactly twice"
