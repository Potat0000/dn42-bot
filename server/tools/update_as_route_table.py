from collections import defaultdict

import base
import requests


def update_as_route_table():
    try:
        roas = requests.get('https://dn42.burble.com/roa/dn42_roa_46.json', timeout=30).json()
        AS_ROUTE = defaultdict(set)
        for roa in roas['roas']:
            AS_ROUTE[int(roa['asn'][2:])].add(roa['prefix'])
        base.AS_ROUTE = dict(AS_ROUTE)
    except BaseException:
        pass
