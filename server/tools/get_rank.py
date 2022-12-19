import pickle
from time import time

import bgpkit
import networkx as nx
from tools.tools import get_mnt_by_asn


# https://github.com/isjerryxiao/rushed_dn42_map/blob/c7bc49eb8c59ba9309e2e7eed425105154802a0a/map.py#L92-L111
def jerry_centrality(fullasmap, closeness_centrality, betweenness_centrality):
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


def gen_get_rank():
    update_time = 0
    data = {}

    def inner(*, update=None):
        nonlocal data, update_time
        if update:
            if isinstance(update, tuple):
                data, update_time = update
                return
            G = nx.Graph()
            for ipver in ['4', '6']:
                parser = bgpkit.Parser(url=f"https://mrt.collector.dn42/master{ipver}_latest.mrt.bz2")
                for elem in parser:
                    as_path = [int(i) for i in elem['as_path'].split(' ')]
                    for i in range(len(as_path) - 1):
                        G.add_edge(as_path[i], as_path[i + 1])

            temp = {
                'closeness': nx.closeness_centrality(G),
                'betweenness': nx.betweenness_centrality(G),
                'peer': {p: len(G.adj[p]) for p in G.nodes},
            }
            temp['jerry'] = jerry_centrality(G.nodes, temp['closeness'], temp['betweenness'])
            for rank_type, rank_data in temp.items():
                s = [(k, v) for k, v in rank_data.items()]
                s.sort(key=lambda x: (-x[1], x[0]))
                rank_now = 0
                last_value = 0
                out = []
                for index, (asn, value) in enumerate(s, 1):
                    if value != last_value:
                        rank_now = index
                    last_value = value
                    out.append((rank_now, asn, get_mnt_by_asn(asn, fallback_prefix=''), value))
                temp[rank_type] = out
            data, update_time = temp, int(time())
            with open('./rank.pkl', 'wb') as f:
                pickle.dump((data, update_time), f)
        else:
            return data, update_time

    return inner


get_rank = gen_get_rank()
