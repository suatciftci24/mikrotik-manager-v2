# MikroTik Manager V2

A clean, independent local V2 workspace. The first phase uses synthetic records only. No real MikroTik, FreeRADIUS, V1 database, production API, or live service is configured or contacted.

## Start the local demo

```bash
cd ~/Codex-Projects/MikroTik-Manager-V2 && ./dev.sh
```

Open `http://127.0.0.1:5173`. Sign in with the synthetic demo account `demo` / `demo-only` (profile email `demo@local.test`). Dashboard, Router Center, and Subscriber Center show synthetic data; the other four modules have planned-scope empty states. The browser API is served by FastAPI at loopback; `/api/health` confirms no DB or device adapter connection.

The first run creates a V2-specific Python virtual environment and installs the pinned backend/frontend dependency ranges. An internet connection to the normal package registries is needed for that initial install. PostgreSQL is not needed for the demo screens. The SQLAlchemy engine and V2-only schema are scaffolding; startup does not connect to the database or create schema. The SQL file under `migrations/versions/` is a design artifact and is not run by `dev.sh`.

The optional V2 database URL is restricted to loopback and a non-default local port; it defaults to the separate database name `mikrotik_manager_v2` on port `55432`. Do not point it at V1 or production. See [AGENTS.md](AGENTS.md) for isolation and architecture rules.
