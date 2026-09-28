# Configuration

Copy `.env.example` to `.env`. Do not commit `.env`.

| Variable | Default | Purpose |
|---|---|---|
| `ANCHORTEXT_API_KEY` | empty | Hashed at startup. Required for `/v1` and the review page |
| `ANCHORTEXT_DATABASE_URL` | `sqlite:///./data/anchortext.db` | Ledger for match config, review tasks, and the one charge per image |
| `ANCHORTEXT_IMAGE_DIR` | `./data/images` | Stored images shown on the review page |

The database file and image directory are local runtime state and are gitignored.

S3 access uses the standard AWS credential chain (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, or an instance role). Those values are not Anchortext settings. A registered source must be an `s3://bucket/key` URI whose body is JSON.

The API port in local development is 8000, bound to `127.0.0.1` by `make dev`.
