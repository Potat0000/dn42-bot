import pickle
from collections import namedtuple
from time import time

import requests
import rustworkx as rx
from tools.tools import get_whoisinfo_by_asn


# https://github.com/isjerryxiao/rushed_dn42_map/blob/c7bc49eb8c59ba9309e2e7eed425105154802a0a/map.py#L92-L111
def calculate_centrality(fullasmap, closeness_centrality, betweenness_centrality):
    node_centrality = list()
    """ should be within 10 - 30 """
    mmin = 10.0
    mmax = 30.0
    clmin = min(closeness_centrality.values())
    clmax = max(closeness_centrality.values())
    bemin = min([v**0.25 for v in betweenness_centrality.values()])
    bemax = max([v**0.25 for v in betweenness_centrality.values()])

    def clcalc(x):
        return (mmax - mmin) / (clmax - clmin) * (x - clmin) + mmin

    def becalc(x):
        return (mmax - mmin) / (bemax - bemin) * (x - bemin) + mmin

    for asn in fullasmap:
        cl = closeness_centrality[asn]
        be = betweenness_centrality[asn] ** 0.25
        cl = clcalc(cl)
        be = becalc(be)
        size = 0.5 * (be + cl)
        node_centrality.append((asn, size))
    node_centrality.sort(key=lambda x: (-x[1], x[0]))
    return {k: v for k, v in node_centrality}


def gen_get_map():
    update_time = 0
    data = {}
    peer_map = {}
    as_name = {}
    last_as_name_update_time = 0

    def get_map(*, update=None):
        nonlocal data, peer_map, update_time, as_name, last_as_name_update_time
        if not update:
            map_result = namedtuple("MapResult", ["update_time", "data", "peer_map"])
            return map_result(update_time, data, peer_map)
        if isinstance(update, tuple):
            update_time, data, peer_map = update
            return
        try:
            G = rx.PyGraph()
            result = requests.get("https://api.iedon.com/dn42/map?type=json", timeout=30).json()
            if result["metadata"]["data_timestamp"] <= update_time:
                return
            asn_to_index = {}
            index_to_asn = {}
            for node in result["nodes"]:
                idx = G.add_node(node["asn"])
                asn_to_index[node["asn"]] = idx
                index_to_asn[idx] = node["asn"]
            for i in result["links"]:
                if i["source"] != i["target"]:
                    G.add_edge(i["source"], i["target"], None)
            if len(G.nodes()) == 0:
                raise RuntimeError
        except BaseException:
            return
        temp_data = {
            "closeness": {index_to_asn[idx]: value for idx, value in rx.closeness_centrality(G).items()},
            "betweenness": {index_to_asn[idx]: value for idx, value in rx.betweenness_centrality(G).items()},
            "peer": {asn: len(G.neighbors(idx)) for asn, idx in asn_to_index.items()},
        }
        temp_data["centrality"] = calculate_centrality(
            list(asn_to_index.keys()),
            temp_data["closeness"],
            temp_data["betweenness"],
        )
        if time() - last_as_name_update_time > 3600:
            as_name.clear()
            last_as_name_update_time = time()
        for rank_type, rank_data in temp_data.items():
            s = [(k, v) for k, v in rank_data.items()]
            s.sort(key=lambda x: (-x[1], x[0]))
            rank_now = 0
            last_value = 0
            out = []
            for index, (asn, value) in enumerate(s, 1):
                if value != last_value:
                    rank_now = index
                last_value = value
                if asn not in as_name:
                    as_name[asn] = get_whoisinfo_by_asn(asn, "as-name")
                out.append((rank_now, asn, as_name[asn], value))
            temp_data[rank_type] = out
        temp_peer_map = {}
        for asn, idx in asn_to_index.items():
            temp_peer_map[asn] = set(index_to_asn[neighbor] for neighbor in G.neighbors(idx))
        data, update_time, peer_map = (
            temp_data,
            result["metadata"]["data_timestamp"],
            temp_peer_map,
        )
        with open("./map.pkl", "wb") as f:
            pickle.dump((update_time, data, peer_map), f)

    return get_map


get_map = gen_get_map()
