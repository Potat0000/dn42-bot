import json
from time import time

from tools.tools import get_from_agent, get_whoisinfo_by_asn


def gen_get_route_stats():
    update_time = 0
    data = {}

    def inner(*, update=False):
        nonlocal data, update_time
        if not update:
            return data, update_time
        temp = {}
        raw = get_from_agent("stats", "")
        for node, raw_data in raw.items():
            if raw_data.status != 200:
                temp[node] = raw_data.text
                continue
            try:
                json_data = json.loads(raw_data.text)
            except json.JSONDecodeError:
                temp[node] = raw_data.text
            else:
                temp[node] = {}
                for ip_ver in ['4', '6']:
                    s = [(k, get_whoisinfo_by_asn(k, 'as-name'), v) for k, v in json_data[ip_ver].items()]
                    s.sort(key=lambda x: (-x[2], x[0]))
                    temp[node][ip_ver] = s
        data, update_time = temp, int(time())

    return inner


get_route_stats = gen_get_route_stats()
