import os
import re
from ipaddress import IPv4Network, IPv6Network, ip_address

import base
from aiohttp import web
from commands.blacklist import get_blacklist
from tools import set_sentry, simple_run


def get_current_peer_num():
    wg_conf = [i[5:-5] for i in os.listdir("/etc/wireguard") if i.startswith("dn42-") and i.endswith(".conf")]
    bird_conf = [i[:-5] for i in os.listdir("/etc/bird/dn42_peers") if i.endswith(".conf")]
    wg_conf_len = len([i for i in wg_conf if i.isdigit()])
    bird_conf_len = len([i for i in bird_conf if i.isdigit()])
    if wg_conf_len != bird_conf_len:
        return None
    else:
        return wg_conf_len


@base.routes.post("/pre_peer")
@set_sentry
async def pre_peer(request):
    secret = request.headers.get("X-DN42-Bot-Api-Secret-Token")
    if secret == base.SECRET:
        try:
            asn = int(await request.text())
        except BaseException:
            return web.Response(status=400)
    else:
        return web.Response(status=403)
    current_peer_num = get_current_peer_num()
    if current_peer_num is None:
        return web.Response(body="wireguard and bird config not match", status=500)
    if (b := get_blacklist()) is not None:
        blocked_time = b.get(asn, (None,))[0]
    else:
        blocked_time = None
    return web.json_response(
        {
            "existed": current_peer_num,
            "max": base.MAX_PEERS,
            "requirement": base.MIN_PEER_REQUIREMENT,
            "open": base.OPEN,
            "net_support": base.NET_SUPPORT,
            "lla": str(base.MY_DN42_LINK_LOCAL_ADDRESS),
            "msg": base.EXTRA_MSG,
            "blocked_time": blocked_time,
        }
    )


@base.routes.post("/info")
@set_sentry
async def get_info(request):
    secret = request.headers.get("X-DN42-Bot-Api-Secret-Token")
    if secret == base.SECRET:
        try:
            asn = int(await request.text())
        except BaseException:
            return web.Response(status=400)
    else:
        return web.Response(status=403)

    wg_exist = os.path.isfile(f"/etc/wireguard/dn42-{asn}.conf")
    bird_exist = os.path.isfile(f"/etc/bird/dn42_peers/{asn}.conf")
    if not wg_exist and not bird_exist:
        return web.Response(status=404)
    elif wg_exist and not bird_exist:
        return web.Response(body="wg only", status=500)
    elif not wg_exist and bird_exist:
        return web.Response(body="bird only", status=500)

    wg_regex = (
        r"\[Interface\]\n"
        r"ListenPort = ([0-9]+)\n"
        r"Table = off\n"
        r"(?:MTU = [0-9]+\n)?"
        r"PostUp = wg set %i private-key /etc/wireguard/dn42-privatekey\n"
        r"PostUp = ip addr add (fe80::[0-9a-f:]+)/64(?: peer (fe80::[0-9a-f:]+)/64)? dev %i\n"
        r"PostUp = ip addr add " + str(base.MY_DN42_ULA_ADDRESS) + r"/128(?: peer (f[cd][0-9a-f:]+)/128)? dev %i\n"
        r"PostUp = ip addr add " + str(base.MY_DN42_IPv4_ADDRESS) + r"/32(?: peer ([0-9.]+)/32)? dev %i\n"
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

    with open(f"/etc/wireguard/dn42-{asn}.conf", "r") as f:
        wg_raw = f.read()
    with open(f"/etc/bird/dn42_peers/{asn}.conf", "r") as f:
        bird_raw = f.read()
    try:
        wg_info = re.search(wg_regex, wg_raw, re.MULTILINE).groups()
    except BaseException:
        return web.Response(body="wg error", status=500)
    if wg_info[2]:
        v6 = wg_info[2]
        my_v6 = wg_info[1]
    else:
        v6 = wg_info[3]
        my_v6 = str(base.MY_DN42_ULA_ADDRESS)
    my_v4 = str(base.MY_DN42_IPv4_ADDRESS) if wg_info[4] else None
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
                return web.Response(body="session error", status=500)
        else:
            session = "IPv4 Session with IPv6 & IPv4 Channels"
        try:
            desc = re.search(bird_regex_decs, matches[0], re.MULTILINE).group(1)
        except BaseException:
            pass
    if not session_name:
        return web.Response(body="no session", status=500)

    out = simple_run(f"wg show dn42-{asn} latest-handshakes")
    if out:
        if out == "Unable to access interface: No such device":
            wg_last_handshake = 0
        else:
            out = out.split()
            if out[0] == wg_info[5]:
                wg_last_handshake = int(out[1])
            else:
                return web.Response(body="wg error", status=500)
    else:
        wg_last_handshake = 0
    out = simple_run(f"wg show dn42-{asn} transfer")
    if out:
        if out == "Unable to access interface: No such device":
            wg_transfer = [0, 0]
        else:
            out = out.split()
            if out[0] == wg_info[5]:
                wg_transfer = [int(out[1]), int(out[2])]
            else:
                return web.Response(body="wg error", status=500)
    else:
        wg_transfer = [0, 0]
    bird_status = {}
    for the_session in session_name:
        out = simple_run(f"birdc show protocols {the_session}").splitlines()
        if len(out) != 3:
            return web.Response(body="bird error", status=500)
        out = out[2].strip().split(maxsplit=6)
        if out[0] != the_session:
            return web.Response(body="bird error", status=500)
        bird_status[the_session] = [out[5] if len(out) >= 6 else "N/A", "", {}]
        try:
            bird_status[the_session][1] = out[6]
        except IndexError:
            pass
        if len(out) >= 6 and out[5] == "Established":
            out = simple_run(f"birdc show protocols all {the_session}")
            out = [i.strip().splitlines() for i in out.split("Channel ")]
            out = {
                i[0].strip(): {j.split(":", 1)[0].strip(): j.split(":", 1)[1].strip() for j in i[1:]}
                for i in out
                if i[0].strip().startswith("ipv")
            }
            for k, v in out.items():
                if v["State"] == "UP" and v["Output filter"] == "(unnamed)":
                    bird_status[the_session][2][k[3]] = v["Routes"]
    if (b := get_blacklist()) is not None:
        blocked_time = b.get(asn, (None,))[0]
    else:
        blocked_time = None

    return web.json_response(
        {
            "port": wg_info[0],
            "v6": v6,
            "v4": wg_info[4],
            "clearnet": clearnet,
            "pubkey": wg_info[5],
            "desc": desc,
            "session": session,
            "session_name": session_name,
            "my_v6": my_v6,
            "my_v4": my_v4,
            "my_pubkey": base.MY_WG_PUBLIC_KEY,
            "wg_last_handshake": wg_last_handshake,
            "wg_transfer": wg_transfer,
            "bird_status": bird_status,
            "net_support": base.NET_SUPPORT,
            "lla": str(base.MY_DN42_LINK_LOCAL_ADDRESS),
            "blocked_time": blocked_time,
        }
    )


@base.routes.post("/peer")
@set_sentry
async def setup_peer(request):
    secret = request.headers.get("X-DN42-Bot-Api-Secret-Token")
    if secret == base.SECRET:
        try:
            peer_info = await request.json()
        except BaseException:
            return web.Response(status=400)
    else:
        return web.Response(status=403)

    current_peer_num = get_current_peer_num()
    if current_peer_num is None:
        return web.Response(body="wireguard and bird config not match", status=500)
    if not (
        os.path.exists(f"/etc/wireguard/dn42-{peer_info['ASN']}.conf")
        and os.path.exists(f"/etc/bird/dn42_peers/{peer_info['ASN']}.conf")
    ) and ((base.MAX_PEERS != 0 and current_peer_num >= base.MAX_PEERS) or not base.OPEN):
        return web.Response(status=503)

    ula = None
    ll = None
    ipv4 = None
    try:
        if ip_address(peer_info["IPv6"]) in IPv6Network("fc00::/7"):
            ula = str(ip_address(peer_info["IPv6"]))
    except BaseException:
        pass
    try:
        if ip_address(peer_info["IPv6"]) in IPv6Network("fe80::/64"):
            ll = str(ip_address(peer_info["IPv6"]))
    except BaseException:
        pass
    try:
        if any(
            ip_address(peer_info["IPv4"]) in n for n in [IPv4Network("172.20.0.0/14"), IPv4Network("10.127.0.0/16")]
        ):
            ipv4 = str(ip_address(peer_info["IPv4"]))
    except BaseException:
        pass
    try:
        my_lla = str(ip_address(peer_info["Request-LinkLocal"]))
    except BaseException:
        my_lla = str(base.MY_DN42_LINK_LOCAL_ADDRESS)
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
        port=peer_info["Port"],
        ll=(f" peer {ll}/64" if ll else ""),
        ula=(f" peer {ula}/128" if ula else ""),
        ipv4=(f" peer {ipv4}/32" if ipv4 else ""),
        my_lla=my_lla,
        my_ula=str(base.MY_DN42_ULA_ADDRESS),
        my_ipv4=str(base.MY_DN42_IPv4_ADDRESS),
        pubkey=peer_info["PublicKey"],
        clearnet=peer_info["Clearnet"],
    )
    if peer_info["Clearnet"] is None:
        final_wg_text = final_wg_text.replace("Endpoint = None\n", "")
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
    elif peer_info["Channel"] == "IPv6 & IPv4":
        if peer_info["MP-BGP"] == "IPv6":
            bird = gen_bird_protocol(6, False)
        elif peer_info["MP-BGP"] == "IPv4":
            bird = gen_bird_protocol(4, False)
        elif peer_info["MP-BGP"] == "Not supported":
            bird = gen_bird_protocol(6, True) + "\n" + gen_bird_protocol(4, True)
    with open(f"/etc/bird/dn42_peers/{peer_info['ASN']}.conf", "w") as f:
        f.write(bird)

    simple_run("systemctl daemon-reload")
    simple_run(f"systemctl enable wg-quick@dn42-{peer_info['ASN']}")
    simple_run(f"systemctl restart wg-quick@dn42-{peer_info['ASN']}")
    simple_run("birdc c")
    if base.VNSTAT_AUTO_ADD:
        simple_run(f'vnstat --add -i dn42-{peer_info["ASN"]}')

    return web.Response(status=200)


@base.routes.post("/remove")
@set_sentry
async def remove_peer(request):
    secret = request.headers.get("X-DN42-Bot-Api-Secret-Token")
    if secret == base.SECRET:
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
    if base.VNSTAT_AUTO_REMOVE:
        simple_run(f"vnstat --remove -i dn42-{asn} --force")

    return web.Response(status=200)


@base.routes.post("/restart")
@set_sentry
async def restart_peer(request):
    secret = request.headers.get("X-DN42-Bot-Api-Secret-Token")
    if secret == base.SECRET:
        try:
            asn = int(await request.text())
        except BaseException:
            return web.Response(status=400)
    else:
        return web.Response(status=403)

    out_wg = simple_run(f"systemctl restart wg-quick@dn42-{asn}")
    out_v4 = simple_run(f"birdc restart DN42_{asn}_v4")
    out_v6 = simple_run(f"birdc restart DN42_{asn}_v6")
    if "syntax error" in out_v4 and "syntax error" in out_v6:
        if out_wg:
            return web.Response(status=404)
        else:
            return web.Response(body="bird error", status=500)
    else:
        if out_wg:
            return web.Response(body="wg error", status=500)
        else:
            return web.Response(status=200)
