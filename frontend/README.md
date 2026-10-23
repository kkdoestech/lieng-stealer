# Liêng Scope — web UI

React 19 + Vite page for the Liêng Stealer solver. It talks to the Flask API in `../backend`.

```bash
npm install
npm run dev      # http://localhost:5173 — /api requests are proxied to http://127.0.0.1:5000
npm test         # Vitest + Testing Library (App behaviour, i18n parity, number formatting)
npm run lint     # oxlint; any warning fails
npm run build    # production files in dist/
```

Requires Node 22.22 or newer. Start the backend first (`cd ../backend && python app.py`).

- `VITE_API_URL` (build time): where the API lives in production, e.g.
  `VITE_API_URL=https://api.example.com npm run build`. Without it the page calls `/api` on its
  own origin. The value ends up in the public JavaScript bundle, so it must never be a secret.
- UI rules (colours, type, layout, copy) are in [`../DESIGN.md`](../DESIGN.md).
- All text lives in `src/i18n.js` (English and Vietnamese, same keys; `src/i18n.test.js` checks that).
