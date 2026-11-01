# Contribution Doggo — design notes

## Product intent

A polished, lightweight animation for SamSurve's GitHub profile. It is a visual companion: it never writes to or changes GitHub contribution history.

## Current prototype

- Dark navy panel with restrained purple accents.
- Contribution calendar fetched from GitHub's GraphQL API.
- Original corgi illustration drawn in Pillow.
- Dog travels across the calendar, pauses at the highest-contribution day, sniffs, and leaves a short paw-print trail.
- Animated GIF published to the `output` branch.

## Current limitations

- The first implementation selects the single highest-count day in the returned contribution calendar, not every active square.
- The animation is a generated snapshot, refreshed daily; it cannot react to new contributions in real time while a README is open.
- The current dog artwork is procedural vector-style drawing. A future art pass can replace it with a custom sprite sheet while preserving the renderer and workflow.

## Security

The workflow expects a `DOGGO_TOKEN` Actions secret. Never commit a personal access token, `.env` file, or credential.
