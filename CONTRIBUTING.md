# Contributing

Thanks for helping make JobSwipe clearer and more useful for people starting
their careers. Keep changes focused, explain user-visible behavior in a pull
request, and include tests for new filtering, parsing, and local-state behavior.

## Development checks

- Backend: `python -m pytest backend/tests`
- Frontend: `cd frontend && npm test && npm run build`
- Full local app: follow the development commands in [README.md](README.md).

Do not commit `.env` files, API credentials, generated SQLite databases, or
personal CV data. Provider integrations must keep credentials on the server.
When adding a provider, document its official API terms and source behavior.

## Security reports

Please do not publish secrets or sensitive personal data in issues. For a
potential security issue, contact the project maintainers privately before
disclosing it publicly.
