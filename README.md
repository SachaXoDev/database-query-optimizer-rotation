# database-query-optimizer-rotation

An aiohttp/Asyncio worker for the [Database Query Optimizer course backend](https://github.com/SachaXoDev/Khodina_IU5-51B_Web_Labs_2026_Database_query_optimizer). It accepts a rotation job, returns HTTP 202 immediately, then computes new angles (radians, wrapped into `[0, 2π)`) and sends them to the main API. The worker has no database or durable queue. A second request for the same ID while a job is pending is acknowledged but does not replace it. Failed callbacks are logged, not retried.

Run the [backend `extras/async-rotation` branch](https://github.com/SachaXoDev/Khodina_IU5-51B_Web_Labs_2026_Database_query_optimizer/tree/extras/async-rotation), not the backend's default branch. The [React `extras/async-rotation` branch](https://github.com/SachaXoDev/database-query-optimizer-frontend/tree/extras/async-rotation) displays the resulting model rotations.

## Run locally

Use Python 3.11 or later. Start the main backend on port 3108 with its usual database, Redis and MinIO configuration. From the worker repository root:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
export ROTATION_MAIN_API=http://127.0.0.1:3108/api
export ROTATION_RESULT_KEY="$(openssl rand -hex 32)"
```

Launch both processes with the **same** `ROTATION_RESULT_KEY`, supplied through a private environment, never committed. For the backend also set `PORT=3108` and `ASYNC_ROTATION_URL=http://127.0.0.1:8108/rotate`. Then run `python app.py` in the worker environment.

| Worker variable | Default | Purpose |
| --- | --- | --- |
| `ROTATION_MAIN_API` | `http://127.0.0.1:3108/api` | Base URL including `/api`; worker appends `/indexes/{id}/rotation` |
| `ROTATION_RESULT_KEY` | Required | Sent in the callback's `X-Result-Key` header |
| `ROTATION_BIND` | `127.0.0.1` | Keep the unauthenticated job endpoint on loopback or a private service network |
| `ROTATION_PORT` | `8108` | Worker HTTP port |
| `ROTATION_DELAY_SECONDS` | `6` | Delay before callback; allowed range 5–10 seconds |

## Smoke check

With both processes running, replace `1` with an existing published card ID in a disposable demo database. This changes the card's saved angles.

```sh
id=1
curl -fsS -i http://127.0.0.1:8108/rotate \
  -H 'Content-Type: application/json' \
  --data "{\"id\":$id,\"rotationX\":0.5,\"rotationY\":1.0}"
sleep 8
curl -fsS "http://127.0.0.1:3108/api/indexes/$id"
```

Expect `202 Accepted` from the worker, then stored angles near `0.9488` and `2.0472` in the card response with the default delay. A `202` acknowledges scheduling only; inspect worker logs if the callback does not persist the angles.
