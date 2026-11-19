# Examiner dashboard

React + Vite + TypeScript. Reads the Examiner API (`uv run examiner serve`, port 8002); the dev server proxies `/api` to it.

```bash
npm install
npm run dev        # http://localhost:5173
npm test           # vitest
npm run typecheck
```

Design direction: `../DIRECTION.md`. UI checks: `ui-verify.config.json` (design:ui-verify).
