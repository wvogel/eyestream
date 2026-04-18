# Contributing to Eyestream

Thanks for your interest in contributing! Eyestream is a small, focused project — contributions of all sizes are welcome.

## Development setup

```bash
git clone https://github.com/wvogel/eyestream.git
cd eyestream
cp .env.example .env
cp oauth2-proxy.env.example oauth2-proxy.env
# Edit both .env files with your settings
docker network create shared-npm 2>/dev/null || true
docker compose up -d --build
```

The admin UI is then served via your reverse proxy on the `shared-npm` network.

## Running tests

```bash
pip install -r tests/requirements-test.txt
pytest tests/ -v
```

Tests run against a temporary SQLite/PostgreSQL setup. Python 3.11+ is required.

## Code style

- Python: PEP 8, 4 spaces, type hints where useful
- JavaScript: 2 spaces, no framework — vanilla DOM
- CSS: BEM-ish naming, prefer CSS variables from `base.css`
- Templates: Jinja2, escape user input (auto-escaping is on)
- SQL: parameterized queries only, no string concatenation

## Commit messages

Conventional-ish prefix is preferred:
- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation only
- `refactor:` no behavior change
- `chore:` build/tooling
- `security:` security fix

## Pull requests

1. Fork the repo, create a branch from `main`
2. Make your change with a clear commit message
3. Add or update tests if behavior changed
4. Make sure `pytest` passes
5. Open a PR against `main` — fill out the template

For larger changes, please open an issue first to discuss the approach.

## Reporting bugs

Use the bug report template. Include:
- Eyestream version (footer of the admin UI)
- Browser + OS
- Steps to reproduce
- Expected vs. actual behavior
- Relevant logs from `docker compose logs app worker`

## Security

Please do **not** open public issues for security vulnerabilities. See [SECURITY.md](SECURITY.md).

## License

By contributing you agree that your contributions are licensed under the [MIT License](LICENSE).
