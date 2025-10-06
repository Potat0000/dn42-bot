import json
from functools import partial

import base
import config
import tools
from base import bot
from commands.blacklist.get_blocked import get_blocked
from telebot.types import ReplyKeyboardRemove


@bot.message_handler(commands=["block", "ban", "unblock", "unban"], is_private_chat=True)
def block_action(message):
    if message.chat.id not in base.db_privilege:
        bot.send_message(
            message.chat.id,
            "You are not allowed to use this command.\n你无权使用此命令。",
            reply_markup=ReplyKeyboardRemove(),
        )
    command = message.text.split()[0].split("@")[0][1:]
    if len(message.text.split()) < 2:
        bot.send_message(
            message.chat.id,
            f"Usage: /{command} <ASN> {{node1}} {{node2}} ...\n用法：/{command} <ASN> {{node1}} {{node2}} ...",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if not base.servers:
        bot.send_message(
            message.chat.id,
            f"No available nodes. Please contact {config.CONTACT}\n当前无可用节点，请联系 {config.CONTACT}",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    nodes = [i.lower() for i in message.text.split()[2:]]
    if command.startswith("un") and message.text.split()[1] == "all":
        unbluck_all_action(message, nodes)
        return
    asn = tools.extract_asn(message.text.split()[1], privilege=True)
    if not asn:
        bot.send_message(
            message.chat.id,
            f"Usage: /{command} <ASN> {{node1}} {{node2}} ...\n用法：/{command} <ASN> {{node1}} {{node2}} ...",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    asn_name = tools.get_whoisinfo_by_asn(asn)
    try:
        available_server = [j.lower() for j in base.servers.keys()]
        specific_server = [i for i in available_server if i in nodes]
        if not specific_server:
            specific_server = [i for i in available_server if any(i.startswith(k) for k in nodes)]
        if not specific_server:
            raise RuntimeError()
    except BaseException:
        specific_server = list(base.servers.keys())
    if not command.startswith("un"):
        text = f"Blocking AS{asn} ({asn_name})\n\n"
        result = tools.get_from_agent("block", json.dumps({"ASN": asn, "Name": asn_name}), specific_server)
    else:
        text = f"Unblocking AS{asn} ({asn_name})\n\n"
        result = tools.get_from_agent("unblock", str(asn), specific_server)
    for node in specific_server:
        text += f"- {base.servers[node]}\n  "
        if result[node].status == 200:
            if not command.startswith("un"):
                text += "✅ Blocked successfully\n"
            else:
                text += "✅ Unblocked successfully\n"
        elif result[node].status == 409:
            text += "⚠️ Already in blacklist\n"
        elif result[node].status == 404:
            text += "⚠️ Not in blacklist\n"
        elif result[node].status == 500:
            text += f"❌ {result[node].text.capitalize()}\n"
        else:
            text += f"❌ Error: {result[node].status}\n"
    bot.send_message(
        message.chat.id,
        f"```BlockActionResult\n{text}```",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )


def unbluck_all_action(message, nodes):
    get_blocked(message, nodes)
    code = tools.gen_random_code(32)
    msg = bot.send_message(
        message.chat.id,
        (
            "This action will unblock all blocked ASNs on the selected nodes (see the previous message for current blocked list). Enter the following random code to confirm the deletion.\n"
            "此操作将解除所选节点上所有被封禁的ASN（当前封禁列表参见上一条消息）。输入以下随机码以确认删除。\n"
            "\n"
            f"`{code}`\n"
            "\n"
            "All other inputs indicate the cancellation of the operation.\n"
            "所有其他输入表示取消操作。"
        ),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    bot.register_next_step_handler(msg, partial(confirm_unblock_all, nodes, code))


def confirm_unblock_all(nodes, code, message):
    if message.text.strip() != code:
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    try:
        available_server = [j.lower() for j in base.servers.keys()]
        if nodes:
            specific_server = [i for i in available_server if i in nodes]
        else:
            specific_server = available_server
        if not specific_server:
            specific_server = [i for i in available_server if any(i.startswith(k) for k in nodes)]
        if not specific_server:
            raise RuntimeError()
    except BaseException:
        bot.send_message(
            message.chat.id,
            "No valid nodes selected. Operation cancelled.\n未选择有效节点，操作已取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    result = tools.get_from_agent("unblock_all", None, specific_server)
    text = "Unblocking all blocked ASNs\n\n"
    for node in specific_server:
        text += f"- {base.servers[node]}\n  "
        if result[node].status == 200:
            text += "✅ Unblocked successfully\n"
        elif result[node].status == 500:
            text += f"❌ {result[node].text.capitalize()}\n"
        else:
            text += f"❌ Error: {result[node].status}\n"
    bot.send_message(
        message.chat.id,
        f"```UnblockAllResult\n{text}```",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
