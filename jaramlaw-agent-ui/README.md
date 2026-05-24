# JaramLaw Agent UI

React + Express UI for the parent `jaramlaw-agent` Python workflow.

The server calls `src/jaramlaw_agent/orchestrator.py` through a Python bridge first. If the bridge is unavailable, the UI falls back to deterministic local rules so the workspace remains usable.

## Run

```bash
npm install
npm run build

# production static server
$env:PORT="3001"; $env:NODE_ENV="production"; npm start

# development server
$env:PORT="3001"; $env:DISABLE_HMR="true"; npm run dev
```

Open `http://localhost:3001`.

## API Surface

- `GET /api/health`: bridge, workflow, seed data, audit status
- `GET /api/history`: consultation sessions
- `POST /api/consult`: runs the Python 14-node workflow, then returns a UI session
- `POST /api/summarize`: document summary fallback
- `GET /api/security-logs`: local cryptographic/audit event stream

