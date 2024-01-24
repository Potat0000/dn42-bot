from collections import defaultdict

import base
import requests


def update_as_route_table():
    try:
        roas = requests.get('https://dn42.burble.com/roa/dn42_roa_46.json', timeout=5).json()
        AS_ROUTE = defaultdict(list)
        for roa in roas['roas']:
            AS_ROUTE[roa['asn']].append(roa['prefix'])
        base.AS_ROUTE = dict(AS_ROUTE)
    except BaseException:
        pass
