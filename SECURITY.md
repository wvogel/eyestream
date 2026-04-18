# Security Policy

## Supported versions

Only the latest release is supported with security fixes.

## Reporting a vulnerability

**Please do not open public GitHub issues for security vulnerabilities.**

Instead, report them privately via GitHub's [Private Vulnerability Reporting](https://github.com/wvogel/eyestream/security/advisories/new).

You can expect:
- An acknowledgement within a few days
- A discussion of the issue and impact
- A coordinated disclosure timeline (typically 30–90 days depending on severity)

## Scope

In scope:
- The Eyestream app itself (`app/`, `worker/`, `nginx-public/`)
- The default Docker Compose configuration

Out of scope:
- Vulnerabilities in upstream dependencies (please report to the upstream project — we'll pull updates)
- Misconfiguration of the reverse proxy or OAuth2-Proxy in your own deployment
- Issues that require physical access to the server

## What we do for security

- All SQL queries are parameterized
- Templates auto-escape user input
- HTTP security headers (X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy)
- CSRF protection via Origin/Referer validation
- SRI hashes on CDN scripts
- Path-traversal protection on file serving
- No secrets in the repository
- Authentication delegated to OAuth2-Proxy (no homegrown auth)
