# Development Tools

This directory contains development and build automation tools for OpenAdminDesk.

## Development Tools (`dev.py`)

The `dev.py` script provides a comprehensive development workflow automation tool.

### Usage

```bash
python tools/dev.py <command>
```

### Available Commands

- `install-deps` - Install development dependencies
- `test` - Run tests
- `lint` - Run linting
- `format` - Run formatting
- `security` - Run security checks
- `build` - Build application
- `type-check` - Run type checking
- `clean` - Clean build artifacts
- `pre-commit` - Run pre-commit checks
- `all` - Run all checks and build

### Examples

```bash
# Run all development checks
python tools/dev.py all

# Run tests only
python tools/dev.py test

# Run security checks
python tools/dev.py security

# Clean build artifacts
python tools/dev.py clean
```

## Build Tools (`build.py`)

The `build.py` script provides automated package building for multiple platforms.

### Usage

```bash
python tools/build.py <command>
```

### Available Commands

- `python-pkg` - Build wheel and source distribution
- `appimage` - Build Linux AppImage
- `deb` - Build Debian package
- `rpm` - Build RPM package
- `check` - Validate packaging inputs
- `windows-exe` - Build unsigned Windows preview EXE
- `all` - Build all Linux packages (python/AppImage/deb/rpm)

### Requirements

- **AppImage**: Requires `appimagetool` in `PATH`
- **Debian**: Requires `dpkg-buildpackage` and `debhelper`
- **RPM**: Requires `rpmbuild`
- **Windows EXE**: Requires Windows and `pip install -e ".[build]"`

### Examples

```bash
# Build Python packages
python tools/build.py python-pkg

# Run packaging check
python tools/build.py check

# Build Windows preview EXE
python tools/build.py windows-exe

# Build AppImage
python tools/build.py appimage

# Build all packages
python tools/build.py all
```
The Windows command writes `dist/OpenAdminDesk.exe`; it is an unsigned preview.

## Docker Support

OpenAdminDesk includes multi-stage Docker builds for optimized production images.

### Building Docker Image

```bash
# Build with Docker
docker build -t openadmindesk .

# Run the container
docker run -it --rm openadmindesk
```

### Docker Features

- Multi-stage build for smaller image size
- Non-root user for security
- Only essential dependencies included
- Optimized for production deployment

## CI/CD Integration

These tools are integrated into the GitHub Actions CI/CD pipeline:

1. **ci.yml**: Automated tests, linting, security checks, and build verification.
2. **release.yml**: Manual builds of Actions artifacts; exact version tags publish GitHub Releases.
3. **Linux Packages**: Generates wheel, sdist, AppImage, deb, and rpm packages.
4. **Windows Packages**: Generates unsigned preview EXE and SHA256SUMS.
5. **Docker**: Verifies container image builds (no automated pushing).

## Development Workflow

1. Install dependencies: `python tools/dev.py install-deps`
2. Make code changes
3. Run pre-commit checks: `python tools/dev.py pre-commit`
4. Test changes: `python tools/dev.py test`
5. Build packages: `python tools/build.py all`
6. Commit changes

## Security Considerations

All build and development tools include security best practices:

- Input validation for all user-provided data
- Command injection prevention
- Secure build environments
- Minimal dependency footprint
- Regular security updates
- Pinned and checksummed `appimagetool` in release workflow
- No signing keys or credentials bundled in the repository
