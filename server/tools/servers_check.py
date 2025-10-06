import base
import config
from telebot.types import ReplyKeyboardRemove
from tools.tools import get_from_agent


def servers_check(startup=False):
    offline_node = []
    old_node = []
    if startup:
        nodes = get_from_agent("version", None, config.SERVERS.keys(), retry=0)
    else:
        nodes = get_from_agent("version", None, config.SERVERS.keys(), backoff_factor=1)
    for k, v in nodes.items():
        if v.status != 200:
            offline_node.append(k)
        elif int(v.text) < base.MIN_AGENT_VERSION:
            old_node.append(k)
    old_servers = base.servers.copy()
    base.servers = {k: v for k, v in config.SERVERS.items() if k not in offline_node and k not in old_node}
    if set(old_servers.keys()) != set(base.servers.keys()):
        text = "*[Privilege]*\n```ServerStatus\n"
        if base.servers.keys():
            text += f"Online nodes: {', '.join(base.servers.keys())}\n"
        if offline_node:
            text += f"Offline nodes: {', '.join(offline_node)}\n"
        if old_node:
            text += f"Outdated nodes: {', '.join(old_node)}\n"
        text += "```"
        for i in base.db_privilege:
            base.bot.send_message(i, text, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    elif not base.servers and startup:
        for i in base.db_privilege:
            base.bot.send_message(
                i,
                "*[Privilege]*\n```ServerStatus\nNo available nodes.\n当前无可用节点。```",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardRemove(),
            )
