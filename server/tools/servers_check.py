import base
import config
from telebot.types import ReplyKeyboardRemove
from tools.tools import get_from_agent

MIN_AGENT_VERSION = 17


def servers_check():
    offline_node = []
    old_node = []
    for k, v in get_from_agent('version', None, config.SERVER.keys(), backoff_factor=1).items():
        if v.status != 200:
            offline_node.append(k)
        elif int(v.text) < MIN_AGENT_VERSION:
            old_node.append(k)
    old_servers = base.servers.copy()
    base.servers = {k: v for k, v in config.SERVER.items() if k not in offline_node and k not in old_node}
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
