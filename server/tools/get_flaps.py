import shlex
import subprocess
import time
from urllib.parse import urlsplit
from ipaddress import ip_network

import config
import requests


def gen_get_flaps():
    update_time = 0
    flaps = []

    def get_flaps(*, update=False, asn=None):
        nonlocal update_time, flaps
        if asn:
            prefixes = sorted(
                [
                    (str(ip_network(i["Prefix"])), int(ip_network(i["Prefix"]).network_address))
                    for i in flaps
                    if i["ASN"] == asn
                ],
                key=lambda x: x[1],
            )
            return [p[0] for p in prefixes]
        if not update:
            return update_time, flaps
        try:
            raw_url = urlsplit(config.FLAPALERTED_URL)
            url = f"{raw_url.scheme}://{raw_url.netloc}/flaps/active/compact"
            raw_flaps = requests.get(url, timeout=30).json()
            update_time = int(time.time())
        except BaseException:
            return
        old_result_map = {}
        for old_value in flaps:
            old_result_map[old_value["Prefix"]] = old_value["ASN"]
        result = []
        for flap in raw_flaps:
            if flap["Prefix"] in old_result_map:
                asn = old_result_map[flap["Prefix"]]
            else:
                try:
                    whois_result = (
                        subprocess.run(
                            shlex.split(f"whois -h {config.WHOIS_ADDRESS} {flap['Prefix']}"),
                            stdout=subprocess.PIPE,
                            timeout=3,
                        )
                        .stdout.decode("utf-8")
                        .strip()
                    )
                except BaseException:
                    whois_result = ""
                try:
                    asn = next(i for i in whois_result.split("\n") if i.startswith("origin:"))
                    asn = int(asn[7:].strip()[2:])
                except BaseException:
                    asn = -1
            result.append({"ASN": asn, **flap})
        flaps = result

    return get_flaps


get_flaps = gen_get_flaps()
