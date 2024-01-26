#!/usr/bin/env python3

import json
import os
import re
import shlex
import subprocess

import sentry_sdk
from aiohttp import web
from IPy import IP

AGENT_VERSION = 16

try:
    with open("agent_config.json", 'r') as f:
        raw_config = json.load(f)
    PORT = raw_config['PORT']
    SECRET = raw_config['SECRET']
    OPEN = raw_config['OPEN']
    MAX_PEERS = raw_config['MAX_PEERS'] if raw_config['MAX_PEERS'] > 0 else 0
    NET_SUPPORT = raw_config['NET_SUPPORT']
    EXTRA_MSG = raw_config['EXTRA_MSG']
    MY_DN42_LINK_LOCAL_ADDRESS = IP(raw_config['MY_DN42_LINK_LOCAL_ADDRESS'])
    MY_DN42_ULA_ADDRESS = IP(raw_config['MY_DN42_ULA_ADDRESS'])
    MY_DN42_IPv4_ADDRESS = IP(raw_config['MY_DN42_IPv4_ADDRESS'])
    MY_WG_PUBLIC_KEY = raw_config['MY_WG_PUBLIC_KEY']
except BaseException:
    print("Failed to load config file. Exiting.")
    exit(1)

if raw_config['SENTRY_DSN']:
    sentry_sdk.init(
        dsn=raw_config['SENTRY_DSN'],
        traces_sample_rate=0,
    )

routes = web.RouteTableDef()


def simple_run(command, timeout=3):
    try:
        output = (
            subprocess.check_output(shlex.split(command), timeout=timeout, stderr=subprocess.STDOUT)
            .decode("utf-8")
            .strip()
        )
    except subprocess.CalledProcessError as e:
        output = e.output.decode("utf-8").strip()
    return output


def get_current_peer_num():
    wg_conf = [i[5:-5] for i in os.listdir('/etc/wireguard') if i.startswith('dn42-') and i.endswith('.conf')]
    bird_conf = [i[:-5] for i in os.listdir('/etc/bird/dn42_peers') if i.endswith('.conf')]
    wg_conf_len = len([i for i in wg_conf if i.isdigit()])
    bird_conf_len = len([i for i in bird_conf if i.isdigit()])
    if wg_conf_len != bird_conf_len:
        return None
    else:
        return wg_conf_len


def set_sentry(func):
    async def wrapper(request):
        if raw_config['SENTRY_DSN']:
            with sentry_sdk.start_transaction(name=f"Agent {request.rel_url}", sampled=True) as transaction:
                transaction.set_tag('url', request.rel_url)
                ret = await func(request)
                transaction.set_http_status(ret.status)
            return ret
        else:
            return func(request)

    return wrapper


@routes.post('/version')
async def version(request):
    return web.Response(body=str(AGENT_VERSION))


@routes.post('/pre_peer')
@set_sentry
async def pre_peer(request):
    secret = request.headers.get("X-DN42-Bot-Api-Secret-Token")
    if secret != SECRET:
        return web.Response(status=403)
    current_peer_num = get_current_peer_num()
    if current_peer_num is None:
        return web.Response(body="wireguard and bird config not match", status=500)
    return web.json_response(
        {
            'existed': current_peer_num,
            'max': MAX_PEERS,
            'open': OPEN,
            'net_support': NET_SUPPORT,
            'lla': str(MY_DN42_LINK_LOCAL_ADDRESS),
            'msg': EXTRA_MSG,
        }
    )


@routes.post('/info')
@set_sentry
async def get_info(request):
    secret = request.headers.get("X-DN42-Bot-Api-Secret-Token")
    if secret == SECRET:
        try:
            asn = int(await request.text())
        except BaseException:
            return web.Response(status=400)
    else:
        return web.Response(status=403)

    wg_exist = os.path.isfile(f'/etc/wireguard/dn42-{asn}.conf')
    bird_exist = os.path.isfile(f'/etc/bird/dn42_peers/{asn}.conf')
    if not wg_exist and not bird_exist:
        return web.Response(status=404)
    elif wg_exist and not bird_exist:
        return web.Response(body='wg only', status=500)
    elif not wg_exist and bird_exist:
        return web.Response(body='bird only', status=500)

    wg_regex = (
        r"\[Interface\]\n"
        r"ListenPort = ([0-9]+)\n"
        r"Table = off\n"
        r"(?:MTU = [0-9]+\n)?"
        r"PostUp = wg set %i private-key /etc/wireguard/dn42-privatekey\n"
        r"PostUp = ip addr add (fe80::[0-9a-f:]+)/64(?: peer (fe80::[0-9a-f:]+)/64)? dev %i\n"
        r"PostUp = ip addr add " + str(MY_DN42_ULA_ADDRESS) + r"/128(?: peer (f[cd][0-9a-f:]+)/128)? dev %i\n"
        r"PostUp = ip addr add " + str(MY_DN42_IPv4_ADDRESS) + r"/32(?: peer (172.[0-9.]+)/32)? dev %i\n"
        r"PostUp = sysctl -w net\.ipv6\.conf\.%i\.autoconf=0\n\n"
        r"\[Peer\]\n"
        r"PublicKey = (.{43}=)\n"
        r"(?:Endpoint = (.+:[0-9]{,5})\n)?"
        r"AllowedIPs = "
    )
    bird_regex_v4 = r"protocol bgp DN42_" + str(asn) + r"_v4 from dn42_peers \{\n" r"(?:(?: +.*?\n)*?.*\n)+?" r"\}"
    bird_regex_v4_only = (
        r" {4}ipv6 \{\n"
        r"(?: {4,}.*?\n)*?"
        r"(?:(?: {8}import none;\n(?: {4,}.*?\n)*? {8}export none;)|(?: {8}export none;\n(?: {4,}.*?\n)*? {8}import none;))\n"
        r"(?: {4,}.*?\n)*?"
        r" {4}\};"
    )
    bird_regex_v6 = r"protocol bgp DN42_" + str(asn) + r"_v6 from dn42_peers \{\n" r"(?:(?: +.*?\n)*?.*\n)+?" r"\}"
    bird_regex_v6_only = (
        r" {4}ipv4 \{\n"
        r"(?: {4,}.*?\n)*?"
        r"(?:(?: {8}import none;\n(?: {4,}.*?\n)*? {8}export none;)|(?: {8}export none;\n(?: {4,}.*?\n)*? {8}import none;))\n"
        r"(?: {4,}.*?\n)*?"
        r" {4}\};"
    )
    bird_regex_decs = r'^ {4}description "(.*)";$'

    with open(f'/etc/wireguard/dn42-{asn}.conf', 'r') as f:
        wg_raw = f.read()
    with open(f'/etc/bird/dn42_peers/{asn}.conf', 'r') as f:
        bird_raw = f.read()
    try:
        wg_info = re.search(wg_regex, wg_raw, re.MULTILINE).groups()
    except BaseException:
        return web.Response(body='wg error', status=500)
    if wg_info[2]:
        v6 = wg_info[2]
        my_v6 = wg_info[1]
    else:
        v6 = wg_info[3]
        my_v6 = str(MY_DN42_ULA_ADDRESS)
    my_v4 = str(MY_DN42_IPv4_ADDRESS) if wg_info[4] else None
    if wg_info[6]:
        clearnet = wg_info[6]
    else:
        clearnet = None

    desc = "N.A."
    session = ""
    session_name = []
    if matches := re.findall(bird_regex_v6, bird_raw, re.MULTILINE):
        session_name.append(f"DN42_{asn}_v6")
        if re.findall(bird_regex_v6_only, matches[0], re.MULTILINE):
            session = "IPv6 Session with IPv6 channel only"
        else:
            session = "IPv6 Session with IPv6 & IPv4 Channels"
        try:
            desc = re.search(bird_regex_decs, matches[0], re.MULTILINE).group(1)
        except BaseException:
            pass
    if matches := re.findall(bird_regex_v4, bird_raw, re.MULTILINE):
        session_name.append(f"DN42_{asn}_v4")
        if re.findall(bird_regex_v4_only, matches[0], re.MULTILINE):
            if session == "":
                session += "IPv4 Session with IPv4 channel only"
            elif session == "IPv6 Session with IPv6 channel only":
                session = "IPv6 & IPv4 Session with their own channels"
            else:
                return web.Response(body='session error', status=500)
        else:
            session = "IPv4 Session with IPv6 & IPv4 Channels"
        try:
            desc = re.search(bird_regex_decs, matches[0], re.MULTILINE).group(1)
        except BaseException:
            pass
    if not session_name:
        return web.Response(body='no session', status=500)

    out = simple_run(f"wg show dn42-{asn} latest-handshakes")
    if out:
        if out == 'Unable to access interface: No such device':
            wg_last_handshake = 0
        else:
            out = out.split()
            if out[0] == wg_info[5]:
                wg_last_handshake = int(out[1])
            else:
                return web.Response(body='wg error', status=500)
    else:
        wg_last_handshake = 0
    out = simple_run(f"wg show dn42-{asn} transfer")
    if out:
        if out == 'Unable to access interface: No such device':
            wg_transfer = [0, 0]
        else:
            out = out.split()
            if out[0] == wg_info[5]:
                wg_transfer = [int(out[1]), int(out[2])]
            else:
                return web.Response(body='wg error', status=500)
    else:
        wg_transfer = [0, 0]
    bird_status = {}
    for the_session in session_name:
        out = simple_run(f"birdc show protocols {the_session}").splitlines()
        if len(out) != 3:
            return web.Response(body='bird error', status=500)
        out = out[2].strip().split(maxsplit=6)
        if out[0] != the_session:
            return web.Response(body='bird error', status=500)
        bird_status[the_session] = [out[5], "", {}]
        try:
            bird_status[the_session][1] = out[6]
        except IndexError:
            pass
        if out[5] == 'Established':
            out = simple_run(f"birdc show protocols all {the_session}")
            out = [i.strip().splitlines() for i in out.split('Channel ')]
            out = {
                i[0].strip(): {j.split(':', 1)[0].strip(): j.split(':', 1)[1].strip() for j in i[1:]}
                for i in out
                if i[0].strip().startswith('ipv')
            }
            for k, v in out.items():
                if v['State'] == 'UP' and v['Output filter'] == '(unnamed)':
                    bird_status[the_session][2][k[3]] = v['Routes']

    return web.json_response(
        {
            'port': wg_info[0],
            'v6': v6,
            'v4': wg_info[4],
            'clearnet': clearnet,
            'pubkey': wg_info[5],
            'desc': desc,
            'session': session,
            'session_name': session_name,
            'my_v6': my_v6,
            'my_v4': my_v4,
            'my_pubkey': MY_WG_PUBLIC_KEY,
            'wg_last_handshake': wg_last_handshake,
            'wg_transfer': wg_transfer,
            'bird_status': bird_status,
            'net_support': NET_SUPPORT,
        }
    )


@routes.post('/stats')
async def get_route_stats(request):
    secret = request.headers.get("X-DN42-Bot-Api-Secret-Token")
    if secret != SECRET:
        return web.Response(status=403)

    stats = {'4': {}, '6': {}}

    out = simple_run("birdc show protocols").splitlines()
    if len(out) < 3:
        return web.Response(body='bird error', status=500)
    sessions = []
    for line in out[2:]:
        s = line.split()
        if s[1] == 'BGP' and s[0].startswith('DN42_') and s[5] == 'Established':
            try:
                int(s[0].split('_')[1])
                sessions.append(s[0])
            except ValueError:
                if s[0].startswith('DN42_INNER_'):
                    sessions.append(s[0])
    for the_session in sessions:
        out = simple_run(f"birdc show protocols all {the_session}")
        out = [i.strip().splitlines() for i in out.split('Channel ')]
        out = {
            i[0].strip(): {j.split(':', 1)[0].strip(): j.split(':', 1)[1].strip() for j in i[1:]}
            for i in out
            if i[0].strip().startswith('ipv')
        }
        for k, v in out.items():
            if v['State'] == 'UP' and v['Output filter'] == '(unnamed)':
                if the_session.startswith('DN42_INNER_'):
                    as_name = the_session[5:]
                else:
                    as_name = the_session[5:-3]
                preferred = int(v['Routes'].split(',')[2].split()[0])
                stats[k[3]][as_name] = preferred
    return web.json_response(stats)


@routes.post('/peer')
@set_sentry
async def setup_peer(request):
    secret = request.headers.get("X-DN42-Bot-Api-Secret-Token")
    if secret == SECRET:
        try:
            peer_info = await request.json()
        except BaseException:
            return web.Response(status=400)
    else:
        return web.Response(status=403)

    current_peer_num = get_current_peer_num()
    if current_peer_num is None:
        return web.Response(body='wireguard and bird config not match', status=500)
    if not (
        os.path.exists(f"/etc/wireguard/dn42-{peer_info['ASN']}.conf")
        and os.path.exists(f"/etc/bird/dn42_peers/{peer_info['ASN']}.conf")
    ) and ((MAX_PEERS != 0 and current_peer_num >= MAX_PEERS) or not OPEN):
        return web.Response(status=503)

    ula = None
    ll = None
    ipv4 = None
    try:
        if IP(peer_info['IPv6']) in IP("fc00::/7"):
            ula = str(IP(peer_info['IPv6']))
    except BaseException:
        pass
    try:
        if IP(peer_info['IPv6']) in IP("fe80::/64"):
            ll = str(IP(peer_info['IPv6']))
    except BaseException:
        pass
    try:
        if IP(peer_info['IPv4']) in IP("172.20.0.0/14"):
            ipv4 = str(IP(peer_info['IPv4']))
    except BaseException:
        pass
    try:
        my_lla = str(IP(peer_info['Request-LinkLocal']))
    except BaseException:
        my_lla = str(MY_DN42_LINK_LOCAL_ADDRESS)
    wg = (
        "# {comment}\n"
        "[Interface]\n"
        "ListenPort = {port}\n"
        "Table = off\n"
        "MTU = 1420\n"
        "PostUp = wg set %i private-key /etc/wireguard/dn42-privatekey\n"
        "PostUp = ip addr add {my_lla}/64{ll} dev %i\n"
        "PostUp = ip addr add {my_ula}/128{ula} dev %i\n"
        "PostUp = ip addr add {my_ipv4}/32{ipv4} dev %i\n"
        "PostUp = sysctl -w net.ipv6.conf.%i.autoconf=0\n"
        "\n"
        "[Peer]\n"
        "PublicKey = {pubkey}\n"
        "Endpoint = {clearnet}\n"
        "AllowedIPs = 172.20.0.0/14, 10.0.0.0/8, 172.31.0.0/16, fd00::/8, fe80::/64\n"
    )
    final_wg_text = wg.format(
        comment=f"{peer_info['ASN']} - {peer_info['Contact']}",
        port=peer_info['Port'],
        ll=(f" peer {ll}/64" if ll else ""),
        ula=(f" peer {ula}/128" if ula else ""),
        ipv4=(f" peer {ipv4}/32" if ipv4 else ""),
        my_lla=my_lla,
        my_ula=str(MY_DN42_ULA_ADDRESS),
        my_ipv4=str(MY_DN42_IPv4_ADDRESS),
        pubkey=peer_info['PublicKey'],
        clearnet=peer_info['Clearnet'],
    )
    if peer_info['Clearnet'] is None:
        final_wg_text = final_wg_text.replace('Endpoint = None\n', '')
    with open(f"/etc/wireguard/dn42-{peer_info['ASN']}.conf", "w") as f:
        f.write(final_wg_text)

    def gen_bird_protocol(version, only):
        text = (
            f"protocol bgp DN42_{peer_info['ASN']}_v{version} from dn42_peers "
            "{\n"
            f"    neighbor {peer_info[f'IPv{version}']} % 'dn42-{peer_info['ASN']}' external;\n"
            f'    description "{peer_info["Contact"]}";\n'
        )
        if only is True:
            if version == 6:
                text += "    ipv4 {\n"
            elif version == 4:
                text += "    ipv6 {\n"
            text += "        import none;\n" "        export none;\n" "    };\n"
        text += "}\n"
        return text

    if peer_info["Channel"] == "IPv6 only":
        bird = gen_bird_protocol(6, True)
    elif peer_info["Channel"] == "IPv4 only":
        bird = gen_bird_protocol(4, True)
    elif peer_info['Channel'] == "IPv6 & IPv4":
        if peer_info['MP-BGP'] == "IPv6":
            bird = gen_bird_protocol(6, False)
        elif peer_info['MP-BGP'] == "IPv4":
            bird = gen_bird_protocol(4, False)
        elif peer_info['MP-BGP'] == "Not supported":
            bird = gen_bird_protocol(6, True) + "\n" + gen_bird_protocol(4, True)
    with open(f"/etc/bird/dn42_peers/{peer_info['ASN']}.conf", "w") as f:
        f.write(bird)

    simple_run("systemctl daemon-reload")
    simple_run(f"systemctl enable wg-quick@dn42-{peer_info['ASN']}")
    simple_run(f"systemctl restart wg-quick@dn42-{peer_info['ASN']}")
    simple_run("birdc c")
    return web.Response(status=200)


@routes.post('/remove')
@set_sentry
async def remove_peer(request):
    secret = request.headers.get("X-DN42-Bot-Api-Secret-Token")
    if secret == SECRET:
        try:
            asn = int(await request.text())
        except BaseException:
            return web.Response(status=400)
    else:
        return web.Response(status=403)

    simple_run(f"systemctl stop wg-quick@dn42-{asn}")
    simple_run(f"systemctl disable wg-quick@dn42-{asn}")
    try:
        os.remove(f"/etc/wireguard/dn42-{asn}.conf")
    except BaseException:
        pass
    try:
        os.remove(f"/etc/bird/dn42_peers/{asn}.conf")
    except BaseException:
        pass
    simple_run("birdc c")
    return web.Response(status=200)


@routes.post('/restart')
@set_sentry
async def restart_peer(request):
    secret = request.headers.get("X-DN42-Bot-Api-Secret-Token")
    if secret == SECRET:
        try:
            asn = int(await request.text())
        except BaseException:
            return web.Response(status=400)
    else:
        return web.Response(status=403)

    out_wg = simple_run(f"systemctl restart wg-quick@dn42-{asn}")
    out_v4 = simple_run(f"birdc restart DN42_{asn}_v4")
    out_v6 = simple_run(f"birdc restart DN42_{asn}_v6")
    if 'syntax error' in out_v4 and 'syntax error' in out_v6:
        if out_wg:
            return web.Response(status=404)
        else:
            return web.Response(body='bird error', status=500)
    else:
        if out_wg:
            return web.Response(body='wg error', status=500)
        else:
            return web.Response(status=200)


@routes.post('/ping')
@set_sentry
async def ping_test(request):
    secret = request.headers.get("X-DN42-Bot-Api-Secret-Token")
    if secret == SECRET:
        target = await request.text()
    else:
        return web.Response(status=403)
    try:
        output = simple_run(f"ping -c 5 -w 6 {target}", timeout=8)
    except subprocess.TimeoutExpired:
        return web.Response(status=408)
    return web.Response(body=output)


@routes.post('/trace')
@set_sentry
async def trace_test(request):
    secret = request.headers.get("X-DN42-Bot-Api-Secret-Token")
    if secret == SECRET:
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
    output = [i for i in output.splitlines()[::-1] if not re.match(r'^\s*$', i)]
    total = 0
    while re.match(r"^\s*\d+(?:\s+\*)+$", output[0]):
        output.pop(0)
        total += 1
    output = '\n'.join(output[::-1])
    if total > 0:
        output += f"\n\n{total} hops not responding."
    return web.Response(body=output)


@routes.post('/tcping')
@set_sentry
async def tcping_test(request):
    secret = request.headers.get("X-DN42-Bot-Api-Secret-Token")
    if secret == SECRET:
        target = await request.text()
    else:
        return web.Response(status=403)
    try:
        output = simple_run(f"tcping -w 1 -x 5 {target}", timeout=8)
    except subprocess.TimeoutExpired:
        return web.Response(status=408)
    return web.Response(body=output)


@routes.post('/route')
@set_sentry
async def get_route(request):
    secret = request.headers.get("X-DN42-Bot-Api-Secret-Token")
    if secret == SECRET:
        target = await request.text()
    else:
        return web.Response(status=403)
    try:
        output = simple_run(f"birdc show route for {target} all primary")
    except subprocess.TimeoutExpired:
        return web.Response(status=408)
    return web.Response(body=output)


@routes.post('/path')
@set_sentry
async def get_path(request):
    secret = request.headers.get("X-DN42-Bot-Api-Secret-Token")
    if secret == SECRET:
        target = await request.text()
    else:
        return web.Response(status=403)
    try:
        output = simple_run(f"birdc show route for {target} all primary")
    except subprocess.TimeoutExpired:
        return web.Response(status=408)
    for line in output.splitlines():
        if 'BGP.as_path' in line:
            return web.Response(body=line.split(':')[1].strip())
    return web.Response(status=404)


app = web.Application()
app.add_routes(routes)
web.run_app(app, port=PORT)
