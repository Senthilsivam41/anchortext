# Anchortext

Pay-as-you-go API that reads oriented engineering text from a 2D image and matches it to a registered reference.

Maturity: lab. Status: Implemented—not externally validated.

Callers send a 2D image. The service returns engineering text annotations, holds low-confidence regions for the caller to review, and charges once per image by work level (`standard` or `oriented`).

## Demo

`make demo` runs the test suite. It does not call S3 or download a model.

## Setup

See [docs/quickstart.md](docs/quickstart.md).

```bash
make setup
make dev
```

## Commands

| Command | What it does |
|---|---|
| `make setup` | Install locked dependencies with uv |
| `make dev` | API on `127.0.0.1:8000` |
| `make demo` | Deterministic test run |
| `make check` | Same test gate used before a change is called done |

## Architecture

See [docs/architecture.md](docs/architecture.md).

## Configuration

See [docs/configuration.md](docs/configuration.md) and `.env.example`.

## Portfolio

This product is standalone. It reads caller-registered JSON from S3. [portfolio.yaml](portfolio.yaml) is the catalog entry.

## Security

The API key is hashed at rest. Images and transcripts stay on this host. Do not commit `.env`, the SQLite file, or stored images.

No license file is published.
