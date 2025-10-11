import re
from datetime import datetime, timezone

import base
from aiohttp import web
from tools import set_sentry, simple_run


def get_blacklist():
    with open("/etc/bird/config/blacklist.conf", "r") as f:
        raw = f.read()
    if match := re.search(r"define DN42_BLACKLIST_ASNS\s*=\s*\[(.*?)\];", raw, re.S):
        blocked_asns = {
            int(asn): (
                datetime.strptime(time, "%Y-%m-%dT%H:%M:%S").timestamp(),
                name.strip(),
            )
            for asn, time, name in re.findall(
                r"\s*(\d+)[, ]   # (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})   (.+)",
                match.group(1),
            )
        }
    else:
        blocked_asns = None
    return blocked_asns


def gen_blacklist(blocked_asns):
    text = "define DN42_BLACKLIST_ASNS = [\n"
    if blocked_asns:
        asns = sorted(
            [(asn, time, name) for asn, (time, name) in blocked_asns.items()],
            key=lambda x: x[0],
        )
        for asn, time, name in asns[:-1]:
            time_str = datetime.fromtimestamp(time, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
            text += f"    {asn},   # {time_str}   {name}\n"
        time_str = datetime.fromtimestamp(asns[-1][1], tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        text += f"    {asns[-1][0]}    # {time_str}   {asns[-1][2]}\n"
    text += "];"
    return text


@base.routes.post("/get_blocked")
@set_sentry
async def get_blocked(request):
    secret = request.headers.get("X-DN42-Bot-Api-Secret-Token")
    if secret != base.SECRET:
        return web.Response(status=403)
    blocked_asns = get_blacklist()
    if blocked_asns is None:
        return web.Response(body="blacklist parse error", status=500)
    return web.json_response(blocked_asns)


@base.routes.post("/block")
@set_sentry
async def block(request):
    secret = request.headers.get("X-DN42-Bot-Api-Secret-Token")
    if secret == base.SECRET:
        try:
            asn_info = await request.json()
            asn = int(asn_info["ASN"])
            name = asn_info["Name"]
            time = int(asn_info["Time"])
        except BaseException:
            return web.Response(status=400)
    else:
        return web.Response(status=403)
    blocked_asns = get_blacklist()
    if blocked_asns is None:
        return web.Response(body="blacklist parse error", status=500)
    if asn in blocked_asns:
        return web.Response(status=409)
    blocked_asns[asn] = (time, name)
    try:
        with open("/etc/bird/config/blacklist.conf", "r") as f:
            old = f.read()
        new = re.sub(
            r"define DN42_BLACKLIST_ASNS\s*=\s*\[.*?\];",
            gen_blacklist(blocked_asns),
            old,
            flags=re.S,
        )
        with open("/etc/bird/config/blacklist.conf", "w") as f:
            f.write(new)
    except BaseException:
        return web.Response(body="blacklist write error", status=500)
    simple_run("birdc c")
    return web.Response(status=200)


@base.routes.post("/unblock")
@set_sentry
async def unblock(request):
    secret = request.headers.get("X-DN42-Bot-Api-Secret-Token")
    if secret == base.SECRET:
        try:
            asn = int(await request.text())
        except BaseException:
            return web.Response(status=400)
    else:
        return web.Response(status=403)
    blocked_asns = get_blacklist()
    if blocked_asns is None:
        return web.Response(body="blacklist parse error", status=500)
    if asn not in blocked_asns:
        return web.Response(status=404)
    blocked_asns.pop(asn)
    try:
        with open("/etc/bird/config/blacklist.conf", "r") as f:
            old = f.read()
        new = re.sub(
            r"define DN42_BLACKLIST_ASNS\s*=\s*\[.*?\];",
            gen_blacklist(blocked_asns),
            old,
            flags=re.S,
        )
        with open("/etc/bird/config/blacklist.conf", "w") as f:
            f.write(new)
    except BaseException:
        return web.Response(body="blacklist write error", status=500)
    simple_run("birdc c")
    return web.Response(status=200)


@base.routes.post("/unblock_all")
@set_sentry
async def unblock_all(request):
    secret = request.headers.get("X-DN42-Bot-Api-Secret-Token")
    if secret != base.SECRET:
        return web.Response(status=403)
    try:
        with open("/etc/bird/config/blacklist.conf", "r") as f:
            old = f.read()
        new = re.sub(
            r"define DN42_BLACKLIST_ASNS\s*=\s*\[.*?\];",
            gen_blacklist({}),
            old,
            flags=re.S,
        )
        with open("/etc/bird/config/blacklist.conf", "w") as f:
            f.write(new)
    except BaseException:
        return web.Response(body="blacklist write error", status=500)
    simple_run("birdc c")
    return web.Response(status=200)
