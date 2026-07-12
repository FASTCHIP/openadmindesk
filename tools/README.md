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

- `python-pkg` - Build Python packages (wheel and source)
- `appimage` - Build AppImage package
- `deb` - Build Debian package
- `rpm` - Build RPM package
- `all` - Build all packages

### Requirements

- **AppImage**: Requires `appimagetool` and `wget`
- **Debian**: Requires `dpkg-buildpackage`
- **RPM**: Requires `rpmbuild`

### Examples

```bash
# Build Python packages
python tools/build.py python-pkg

# Build AppImage
python tools/build.py appimage

# Build all packages
python tools/build.py all
```

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

1. **Testing**: Automated test runs on multiple Python versions
2. **Security**: Bandit and safety checks for vulnerabilities
3. **Linting**: Code quality checks with ruff
4. **Building**: Multi-platform package generation
5. **Docker**: Container image building and pushing

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