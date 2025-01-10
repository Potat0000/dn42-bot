from ipaddress import IPv4Network, IPv6Network

import base
import requests


def update_china_ip():
    try:
        ChinaIPv4_RAW = requests.get(
            'https://raw.githubusercontent.com/misakaio/chnroutes2/master/chnroutes.txt', timeout=5
        ).text
        base.ChinaIPv4 = [
            IPv4Network(i.strip()) for i in ChinaIPv4_RAW.splitlines() if i != '' and not i.startswith('#')
        ]
    except BaseException:
        pass
    try:
        ChinaIPv6_RAW = requests.get('https://ispip.clang.cn/all_cn_ipv6.txt', timeout=5).text
        base.ChinaIPv6 = [IPv6Network(i.strip()) for i in ChinaIPv6_RAW.splitlines() if i != '']
    except BaseException:
        pass
