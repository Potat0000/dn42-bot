#!/usr/bin/env python3

import base
import commands  # noqa: F401
import sentry_sdk
from aiohttp import web

if base.SENTRY_DSN:
    sentry_sdk.init(
        dsn=base.SENTRY_DSN,
        traces_sample_rate=0,
    )


@base.routes.post("/version")
async def version(request):
    return web.Response(body=str(base.AGENT_VERSION))


app = web.Application()
app.add_routes(base.routes)
web.run_app(app, host=base.HOST, port=base.PORT)
