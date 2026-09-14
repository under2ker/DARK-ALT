# DARK//ALT

Premium dark wallpaper archive and aggregation engine.

## Current milestone — v0.9

### Download engine
- Original, 4K, 2K, FHD and custom-size variants.
- Fit, fill, crop, center, stretch and blurred-background modes.
- JPEG, WebP and PNG output.
- No upscaling unless explicitly requested.
- EXIF orientation correction and high-quality Lanczos resizing.
- 40 MB source limit and 8K output pixel limit.
- Direct original-source redirects; transformed images are streamed without permanent caching.
- Download variant selection is available in the wallpaper detail modal.

### Sources
- Working Wikimedia Commons provider with fail-closed robots policy.
- Working NASA Image and Video Library provider with original asset manifests and attribution metadata.
- Openverse provider module prepared with bearer-token authentication and disabled until `OPENVERSE_ACCESS_TOKEN` is configured.
- Provider-specific download/cache/redistribution permissions remain in `providers.yaml`.

### Semantic archive and discovery
- Lightweight semantic classifier for scene, style, mood and generated tags.
- Mood and category APIs.
- Similarity ranking using tags, mood, ratio, dominant color and perceptual hashes.
- Favorites-based recommendations with quality fallback.
- Multi-word semantic search across title, description, JSON tags/categories, moods and scene/style.
- Server-side cursor pagination plus automatic infinite-scroll loading in the frontend.

### Archive navigation and discovery
- Sidebar navigation is linked to Explore, Collections, Categories, Sources, Favorites and About.
- New `discover.html` page for categories, moods, generated tags and trending records.
- New `about.html` page documenting archive principles and system map.
- URL-driven category, mood and text-query states.
- Detail view now fetches visual-similarity results and supports adding a wallpaper to an authenticated collection.
- Keyboard shortcut `Ctrl/Cmd + K` focuses the archive search field.

### Personalization and privacy
- Persistent preferences for moods, tones, resolutions, default download preset and safe-content threshold.
- Preference-aware recommendations when a new user has no favorites yet.
- Account controls for exporting personal data and clearing recently viewed/search history.
- Catalog safe-by-default NSFW threshold with an optional authenticated preference for questionable content.
- Alembic revision `4d1074ebbbfd_user_preferences.py` for the preference model.

### Discovery, analytics and operations
- View events, search events and download history.
- Trending ranking combines views, favorites, downloads and quality.
- Recently viewed API for authenticated users.
- Expanded filters: orientation, dimensions, license, AI flag, brightness and quality range.
- In-memory rate limiting and security headers with request IDs.
- robots.txt checks before provider crawling; disallowed provider endpoints fail closed.
- Admin telemetry endpoint for views, favorites, downloads, searches, users and jobs.

### Existing systems
- User registration, JWT authentication, persistent favorites and collections.
- Download history.
- SHA-256 and perceptual duplicate detection.
- Dominant color, tone, brightness, saturation, sharpness and quality analysis.
- Celery/Redis background queue and scheduler configuration.
- SQLite development database and PostgreSQL production configuration.

## Local development

Terminal 1:
```powershell
cd E:\DARK_ALT
py -m pip install -r requirements.txt
py -m uvicorn backend:app --host 127.0.0.1 --port 8000 --reload
```

Terminal 2:
```powershell
cd E:\DARK_ALT
py -m http.server 8080
```

- Archive: `http://localhost:8080/index.html`
- Account: `http://localhost:8080/account.html`
- Provider dashboard: `http://localhost:8080/admin.html`
- OpenAPI: `http://127.0.0.1:8000/docs`

## Download API

```text
GET /api/download-options/{slug}
GET /api/downloads/{slug}/file
```

Example:

```text
/api/downloads/obsidian-horizon/file?preset=FHD&mode=fit&format=JPEG
```

Custom example:

```text
/api/downloads/obsidian-horizon/file?preset=CUSTOM&width=1920&height=1200&mode=blur_background&format=WEBP
```

## Openverse

Configure the access token before enabling the provider:

```env
OPENVERSE_ACCESS_TOKEN=...
```

Then set `openverse.enabled: true` in `providers.yaml`.

### Operations and security
- Admin API protected by `X-Admin-Key`.
- Provider enable/disable actions and audit log.
- Admin dashboard controls for crawling, image analysis and semantic classification.
- Admin key and JWT secret are configurable through environment variables.

## Docker

```powershell
docker compose up -d
```

Docker is not installed on this development computer. Direct crawl, analysis and download transformation work without Docker; Redis/Celery execution awaits a local Docker or Redis installation.

## Next milestone

- PostgreSQL deployment validation with Alembic migrations.
- Redis/Celery production deployment when Docker/Redis is available.
- Openverse activation after a valid access token is configured.
- Provider adapters for Wallhaven and additional permitted sources.
- Admin roles, secret rotation and stronger rate limiting.


## GitHub Pages demo

The Pages workflow publishes a static interactive demo from the frontend assets. It includes the current archive snapshot in `demo-data.js`, browsing, filtering, detail previews and direct source-image downloads. The FastAPI API, accounts, admin operations, crawling, generated download variants and personal data remain backend features and require a separate Python host.
