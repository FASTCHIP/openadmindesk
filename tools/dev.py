"""Development tools for OpenAdminDesk."""

import subprocess
import sys


def run_command(cmd: list, cwd: str = None) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True
        )
        return result
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {' '.join(cmd)}")
        print(f"Error: {e}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        raise


def install_dev_dependencies():
    """Install development dependencies."""
    print("Installing development dependencies...")
    run_command([sys.executable, "-m", "pip", "install", "poetry"])
    run_command([sys.executable, "-m", "poetry", "install", "--with", "dev"])


def run_tests():
    """Run the test suite."""
    print("Running tests...")
    run_command([sys.executable, "-m", "poetry", "run", "pytest", "tests/", "-v", "--cov=src/openadmindesk"])


def run_linting():
    """Run code linting."""
    print("Running linting...")
    run_command([sys.executable, "-m", "poetry", "run", "ruff", "check", "src/"])


def run_formatting():
    """Run code formatting."""
    print("Running formatting...")
    run_command([sys.executable, "-m", "poetry", "run", "ruff", "format", "src/"])


def run_security_checks():
    """Run security checks."""
    print("Running security checks...")
    run_command([sys.executable, "-m", "poetry", "run", "bandit", "-r", "src/"])
    run_command([sys.executable, "-m", "poetry", "run", "safety", "check"])


def build_application():
    """Build the application."""
    print("Building application...")
    run_command([sys.executable, "-m", "poetry", "build"])


def run_type_checking():
    """Run type checking."""
    print("Running type checking...")
    try:
        run_command([sys.executable, "-m", "poetry", "run", "mypy", "src/"])
    except subprocess.CalledProcessError:
        print("Type checking failed, but continuing...")


def clean_build_artifacts():
    """Clean build artifacts."""
    print("Cleaning build artifacts...")
    build_dirs = ["build", "dist", "*.egg-info"]
    for pattern in build_dirs:
        run_command([sys.executable, "-c", f"""
import glob
import shutil
for path in glob.glob('{pattern}'):
    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.remove(path)
        """])


def pre_commit_hook():
    """Run pre-commit checks."""
    print("Running pre-commit checks...")
    run_linting()
    run_formatting()
    run_tests()
    run_security_checks()


def main():
    """Main entry point for dev tools."""
    if len(sys.argv) < 2:
        print("Usage: python dev.py <command>")
        print("Available commands:")
        print("  install-deps    - Install development dependencies")
        print("  test           - Run tests")
        print("  lint           - Run linting")
        print("  format         - Run formatting")
        print("  security       - Run security checks")
        print("  build          - Build application")
        print("  type-check     - Run type checking")
        print("  clean          - Clean build artifacts")
        print("  pre-commit     - Run pre-commit checks")
        print("  all            - Run all checks and build")
        return

    command = sys.argv[1]

    if command == "install-deps":
        install_dev_dependencies()
    elif command == "test":
        run_tests()
    elif command == "lint":
        run_linting()
    elif command == "format":
        run_formatting()
    elif command == "security":
        run_security_checks()
    elif command == "build":
        build_application()
    elif command == "type-check":
        run_type_checking()
    elif command == "clean":
        clean_build_artifacts()
    elif command == "pre-commit":
        pre_commit_hook()
    elif command == "all":
        run_linting()
        run_formatting()
        run_tests()
        run_security_checks()
        build_application()
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
