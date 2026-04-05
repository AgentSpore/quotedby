# QuotedBy — AI Citation Checker & Defamation Monitor

> Monitor what AI models say about your brand. Detect fake claims. Defend your reputation.

## What is this?

AI models are the new search engines. QuotedBy monitors what they say about your brand, detects false claims, and helps you defend your reputation.

## Features

- **25 free AI models** loaded dynamically from OpenRouter
- **Visibility score** — how often AI mentions your product
- **Competitor comparison** — benchmark vs rivals
- **Defamation detection** — false claims, outdated info, competitor confusion
- **Expandable context** — see full AI responses
- **5 color themes** — Cyan Matrix, Green Hacker, Amber Terminal, Purple Void, Red Alert
- **i18n** — English, Russian, Chinese
- **Mobile responsive**

## Quick Start

```bash
uv sync
export OPENROUTER_API_KEY=your_key
uv run uvicorn quotedby.main:app --port 8891
```

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /models | 25 free AI models |
| POST | /projects | Create project |
| POST | /projects/{id}/scan | Scan with selected models |
| GET | /projects/{id}/dashboard | Visibility dashboard |
| POST | /projects/{id}/defamation-check | Defamation scan |

## Architecture

```
quotedby/
  api/          — Routes
  services/     — Business logic
  repositories/ — Database
  schemas/      — Pydantic models
  static/       — Frontend
```

## License

MIT
