"""Standalone Asyncio HTTP worker; persists only via the main service callback."""

import asyncio
import logging
import math
import os
from urllib.parse import urlparse

from aiohttp import ClientSession, ClientTimeout, web

JOBS = web.AppKey('rotation_jobs', dict)
CLIENT = web.AppKey('rotation_http_client', ClientSession)
LOGGER = logging.getLogger(__name__)


def next_rotation(x: float, y: float) -> dict[str, float]:
    return {'rotationX': (x + math.pi / 7) % math.tau,
            'rotationY': (y + math.pi / 3) % math.tau}


def build_app(api: str, key: str, delay: float = 6) -> web.Application:
    parsed = urlparse(api)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or not key:
        raise ValueError('ROTATION_MAIN_API and ROTATION_RESULT_KEY must be configured')
    if not 5 <= delay <= 10:
        raise ValueError('ROTATION_DELAY_SECONDS must be in [5,10]')

    app = web.Application(client_max_size=4096)
    app[JOBS] = {}

    async def client_context(_: web.Application):
        async with ClientSession(timeout=ClientTimeout(total=4)) as client:
            app[CLIENT] = client
            yield
            jobs = tuple(app[JOBS].values())
            for job in jobs:
                job.cancel()
            await asyncio.gather(*jobs, return_exceptions=True)

    app.cleanup_ctx.append(client_context)

    async def write(id_: int, x: float, y: float):
        try:
            await asyncio.sleep(delay)
            async with app[CLIENT].put(
                f'{api.rstrip("/")}/indexes/{id_}/rotation',
                headers={'X-Result-Key': key}, json=next_rotation(x, y),
                allow_redirects=False,
            ) as response:
                if not 200 <= response.status < 300:
                    LOGGER.error('Rotation for %s rejected: HTTP %s', id_, response.status)
        except Exception as exc:
            LOGGER.error('Rotation for %s failed: %s', id_, exc)
        finally:
            app[JOBS].pop(id_, None)

    async def rotate(request: web.Request):
        try:
            data = await request.json()
            id_, x, y = data['id'], data['rotationX'], data['rotationY']
            if type(id_) is not int or not 1 <= id_ <= 2147483647:
                raise ValueError
            if any(type(v) not in (int, float) or not math.isfinite(v) for v in (x, y)):
                raise ValueError
        except (TypeError, KeyError, ValueError, OverflowError):
            raise web.HTTPBadRequest(text='Expected positive integer id and finite rotationX/rotationY')
        if id_ not in app[JOBS]:
            app[JOBS][id_] = asyncio.create_task(write(id_, x, y))
        return web.json_response({'id': id_, 'delaySeconds': delay}, status=202)

    app.router.add_post('/rotate', rotate)
    return app


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    web.run_app(build_app(os.environ.get('ROTATION_MAIN_API', 'http://127.0.0.1:3108/api'),
                          os.environ['ROTATION_RESULT_KEY'],
                          float(os.environ.get('ROTATION_DELAY_SECONDS', '6'))),
                host=os.environ.get('ROTATION_BIND', '127.0.0.1'),
                port=int(os.environ.get('ROTATION_PORT', '8108')))
