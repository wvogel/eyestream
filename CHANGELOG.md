# Changelog

All notable changes to Eyestream are documented here.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [4.2] — 2026-04

### Security
- HTTP security headers (X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy)
- CSRF protection via Origin/Referer validation
- Health endpoint no longer exposes internal paths
- SRI integrity hashes on CDN scripts (HLS.js)
- Removed Google Fonts dependency — system fonts only (GDPR compliant)

### Added
- Worker healthcheck via touchfile (`/tmp/.worker_alive`)
- Brand logo with fire-gradient animation (60s, clock-synced)
- DE/EN architecture diagrams (SVG + PNG for blog use)

### Changed
- Encoding progress weighted by rendition height (more accurate ETA)
- Worker heartbeat + CPU display also during encoding (not just idle)
- All UI actions update the DOM in place — no full page reload anymore
- Re-encode button disabled on click, cancel button replaces actions immediately
- Pagination: dropdown opens upward in bottom pagination bar
- Search field aligned with video title column
- Footer order: Version · Copyright · Links

### Fixed
- Custom poster preserved across re-encode
- Empty state on `/` properly styled inside a card
- Re-encode double-click protection (backend rejects if already queued/encoding)

### Removed
- Icon font (`icons.woff2`) — replaced with inline SVGs (copyright-clean)
- Scroll-to-top button (was always invisible)
- `LOGO_INVERS_URL` env var — only `LOGO_URL` remains

## [4.0] — 2026-04

### Added
- Open-source release: all branding configurable via environment variables
- `.env.example` and `oauth2-proxy.env.example` as configuration templates
- i18n: German + English with header toggle
- Monitoring endpoint `/health/detailed` with subsystem checks
- 55+ automated tests (unit + API + security)
- Embed player: favicon, dynamic tab title, hover previews (960px)
- Documentation: admin handbook, user guide, architecture diagrams

### Changed
- Full rename: Departments → Categories (DB schema, API, CSS, JS, templates, tests)
- DB credentials moved from `docker-compose.yml` to `.env`
- CSS variable `--se-blue` renamed to `--primary`
- All hardcoded domains, logos, company names removed from code

## [3.x] — 2026-04

- Categories with filter functionality
- Custom HTML dropdowns (flame style)
- Statistics page with pie chart, trend graph, worker status
- Referer analysis from NPM logs
- Activity log
- Embed player with oEmbed and hover previews
- SSE instead of polling for encoding progress
- Dark/Light/Auto theme toggle
- Video disable/enable
- Custom poster from any video frame (ffmpeg from original)
- Search suggestions (autocomplete)
- Modular code split (db, helpers, routes)
- Initial security audit (XSS, path traversal, rate limiting)

## [2.0] — 2026-02

- CMAF/fMP4 HLS encoding
- Atomic re-encode (no downtime)
- FIFO queue
- Admin UI with dark mode
