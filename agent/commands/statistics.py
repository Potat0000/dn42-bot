import re
import subprocess

import base
from aiohttp import web
from tools import set_sentry, simple_run


@base.routes.post("/ping")
@set_sentry
async def ping_test(request):
    secret = request.headers.get("X-DN42-Bot-Api-Secret-Token")
    if secret == base.SECRET:
        target = await request.text()
    else:
        return web.Response(status=403)
    try:
        output = simple_run(f"ping -c 5 -w 6 {target}", timeout=8)
    except subprocess.TimeoutExpired:
        return web.Response(status=408)
    return web.Response(body=output)


@base.routes.post("/trace")
@set_sentry
async def trace_test(request):
    secret = request.headers.get("X-DN42-Bot-Api-Secret-Token")
    if secret == base.SECRET:
        target = await request.text()
    else:
        return web.Response(status=403)
    try:
        output = simple_run(f"traceroute -q1 -N32 -w1 {target}", timeout=8)
    except subprocess.TimeoutExpired:
        try:
            output = simple_run(f"traceroute -q1 -N32 -w1 -n {target}", timeout=8)
        except subprocess.TimeoutExpired:
            return web.Response(status=408)
    output = [i for i in output.splitlines()[::-1] if not re.match(r"^\s*$", i)]
    total = 0
    while re.match(r"^\s*\d+(?:\s+\*)+$", output[0]):
        output.pop(0)
        total += 1
    output = "\n".join(output[::-1])
    if total > 0:
        output += f"\n\n{total} hops not responding."
    return web.Response(body=output)


@base.routes.post("/tcping")
@set_sentry
async def tcping_test(request):
    secret = request.headers.get("X-DN42-Bot-Api-Secret-Token")
    if secret == base.SECRET:
        target = await request.text()
    else:
        return web.Response(status=403)
    try:
        output = simple_run(f"tcping -n 5 {target}", timeout=10)
    except subprocess.TimeoutExpired:
        return web.Response(status=408)
    output = re.sub(r"\n\nPing (?:stopped|interrupted).\n\n", "\n", output)
    return web.Response(body=output)


@base.routes.post("/route")
@set_sentry
async def get_route(request):
    secret = request.headers.get("X-DN42-Bot-Api-Secret-Token")
    if secret == base.SECRET:
        target = await request.text()
    else:
        return web.Response(status=403)
    try:
        if ":" in target:
            output = simple_run(f"birdc show route table {base.BIRD_TABLE_6} for {target} all primary")
        else:
            output = simple_run(f"birdc show route table {base.BIRD_TABLE_4} for {target} all primary")
    except subprocess.TimeoutExpired:
        return web.Response(status=408)
    return web.Response(body=output)


@base.routes.post("/path")
@set_sentry
async def get_path(request):
    secret = request.headers.get("X-DN42-Bot-Api-Secret-Token")
    if secret == base.SECRET:
        target = await request.text()
    else:
        return web.Response(status=403)
    try:
        if ":" in target:
            output = simple_run(f"birdc show route table {base.BIRD_TABLE_6} for {target} all primary")
        else:
            output = simple_run(f"birdc show route table {base.BIRD_TABLE_4} for {target} all primary")
    except subprocess.TimeoutExpired:
        return web.Response(status=408)
    for line in output.splitlines():
        if "BGP.as_path" in line:
            return web.Response(body=line.split(":")[1].strip())
    return web.Response(status=404)
