# Quickstart

Status: Implemented—not externally validated.

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
make setup
cp .env.example .env
# set ANCHORTEXT_API_KEY in .env, then export it for the process
export ANCHORTEXT_API_KEY="choose-a-key"
make dev
```

The API listens on `127.0.0.1:8000`. Send `X-API-Key` on each `/v1` call. The review page asks for the same key once and stores it in a cookie.

`make setup` does not install PaddleOCR. Add it when you want live detection:

```bash
uv sync --extra ocr
```

`make demo` and `make check` run the test suite. Those tests do not call S3 or download a model.

Reference JSON is read from S3 at detect time. The process needs credentials that can `GetObject` the registered URI. See [configuration.md](configuration.md).
