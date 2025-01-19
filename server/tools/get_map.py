import os
import pickle
from re import sub as re_sub
from tempfile import TemporaryDirectory
from time import time

import networkx as nx
from pybgpkit_parser import Parser
from requests.adapters import HTTPAdapter, Retry
from requests_futures.sessions import FuturesSession
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

    def get_map(*, update=None):
        nonlocal data, peer_map, update_time
        if not update:
            return update_time, data, peer_map
        if isinstance(update, tuple):
            data, update_time, peer_map = update
            return
        session = FuturesSession()
        session.mount(
            'https://',
            HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.1, allowed_methods=('GET'))),
        )
        futures = {'4': None, '6': None}
        for ipver in futures.keys():
            future = session.get(f'https://mrt.collector.dn42/master{ipver}_latest.mrt.bz2', verify=False, timeout=20)
            futures[ipver] = future
        G = nx.Graph()
        with TemporaryDirectory() as tmpdir:
            for ipver, future in futures.items():
                try:
                    mrt = future.result()
                    filename = os.path.join(tmpdir, f'{ipver}.mrt.bz2')
                    with open(filename, 'wb') as f:
                        f.write(mrt.content)
                    parser = Parser(url=filename)
                except BaseException:
                    return
                else:
                    for elem in parser:
                        as_path = [int(i) for i in re_sub(r'\{.*?\}', '', elem['as_path']).split()]
                        for i in range(len(as_path) - 1):
                            if as_path[i] != as_path[i + 1]:
                                G.add_edge(as_path[i], as_path[i + 1])
        if not G.nodes:
            return
        temp_data = {
            'closeness': nx.closeness_centrality(G),
            'betweenness': nx.betweenness_centrality(G),
            'peer': {p: len(G[p]) for p in G.nodes},
        }
        temp_data['centrality'] = calculate_centrality(G.nodes, temp_data['closeness'], temp_data['betweenness'])
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
                out.append((rank_now, asn, get_whoisinfo_by_asn(asn, 'as-name'), value))
            temp_data[rank_type] = out
        temp_map = {asn: set(G[asn]) for asn in G.nodes}
        data, update_time, peer_map = temp_data, int(time()), temp_map
        with open('./map.pkl', 'wb') as f:
            pickle.dump((data, update_time, peer_map), f)

    return get_map


get_map = gen_get_map()
