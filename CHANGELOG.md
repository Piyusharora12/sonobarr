# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- OpenAI-powered "AI Assist" modal that turns natural language prompts into fresh discovery sessions.
- OpenAI API key/model settings persisted alongside other admin configuration.

### Changed
- Settings JSON now stores OpenAI configuration metadata.

## [0.5.0] - 2025-10-08
### Added
- Application factory bootstrapping with modular blueprints, services, and Socket.IO handlers.
- CSRF protection via Flask-WTF across all forms and API posts.
- Flask-Migrate integration that automatically initializes and upgrades the database on container start.

### Changed
- Docker entrypoint now exports `PYTHONPATH`, prepares the migrations directory under the mounted config volume, and runs migrations before Gunicorn boots.
- Release version metadata is injected at build time and surfaced in the footer badge.

## [0.4.0] - 2025-10-08
### Added
- Software version and update status in footer

### Fixed
- Actually use .env file instead of environment docker variables

## [0.3.0] - 2025-10-08
### Added
- Fallback to play iTunes previews when a YouTube API key is unavailable.

## [0.2.0] - 2025-10-07
### Added
- Full user management and authentication workflow.
- Super-admin bootstrap settings.

## [0.1.0] - 2025-10-06
### Added
- Revamped user interface with progress spinners and a “Load more” button.
- YouTube-based audio prehear support.

### Removed
- Spotify integration.
