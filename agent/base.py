import json
from ipaddress import ip_address

from aiohttp import web

AGENT_VERSION = 26

try:
    with open("agent_config.json", "r") as f:
        raw_config = json.load(f)
    HOST = raw_config["HOST"]
    PORT = raw_config["PORT"]
    SECRET = raw_config["SECRET"]
    OPEN = raw_config["OPEN"]
    MAX_PEERS = raw_config["MAX_PEERS"] if raw_config["MAX_PEERS"] > 0 else 0
    MIN_PEER_REQUIREMENT = raw_config["MIN_PEER_REQUIREMENT"] if raw_config["MIN_PEER_REQUIREMENT"] > 0 else 0
    NET_SUPPORT = raw_config["NET_SUPPORT"]
    EXTRA_MSG = raw_config["EXTRA_MSG"]
    MY_DN42_LINK_LOCAL_ADDRESS = ip_address(raw_config["MY_DN42_LINK_LOCAL_ADDRESS"])
    MY_DN42_ULA_ADDRESS = ip_address(raw_config["MY_DN42_ULA_ADDRESS"])
    MY_DN42_IPv4_ADDRESS = ip_address(raw_config["MY_DN42_IPv4_ADDRESS"])
    MY_WG_PUBLIC_KEY = raw_config["MY_WG_PUBLIC_KEY"]
    BIRD_TABLE_4 = raw_config["BIRD_TABLE_4"]
    BIRD_TABLE_6 = raw_config["BIRD_TABLE_6"]
    VNSTAT_AUTO_ADD = raw_config["VNSTAT_AUTO_ADD"]
    VNSTAT_AUTO_REMOVE = raw_config["VNSTAT_AUTO_REMOVE"] if VNSTAT_AUTO_ADD else False
    SENTRY_DSN = raw_config["SENTRY_DSN"]
except BaseException:
    print("Failed to load config file. Exiting.")
    exit(1)

routes = web.RouteTableDef()
