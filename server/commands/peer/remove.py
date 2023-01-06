# -*- coding: utf-8 -*-
from functools import partial

import config
import requests
import tools
from base import bot, db, db_privilege
from telebot.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove


@bot.message_handler(commands=['remove'], is_private_chat=True)
def remove_peer(message):
    if message.chat.id not in db:
        bot.send_message(
            message.chat.id,
            "You are not logged in yet, please use /login first.\n你还没有登录，请先使用 /login",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    peer_info = tools.get_info(db[message.chat.id])
    if not peer_info:
        bot.send_message(
            message.chat.id,
            ("You are not peer with me yet, you can use /peer to start.\n" "你还没有与我 Peer，可以使用 /peer 开始。"),
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    removable = [config.SERVER[i] for i in peer_info.keys()]

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row_width = 1
    for i in removable:
        markup.add(KeyboardButton(i))
    msg = bot.send_message(
        message.chat.id,
        "Which node do you want to delete the information with?\n你想要删除与哪个节点的信息？",
        reply_markup=markup,
    )
    bot.register_next_step_handler(msg, partial(remove_peer_choose, removable))


def remove_peer_choose(removable, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if message.text.strip() not in removable:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        for i in removable:
            markup.add(KeyboardButton(i))
        msg = bot.send_message(
            message.chat.id,
            ("Invalid input, please try again. Use /cancel to interrupt the operation.\n" "输入不正确，请重试。使用 /cancel 终止操作。"),
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, partial(remove_peer_choose, removable))
        return

    chosen = [k for k, v in config.SERVER.items() if v == message.text.strip()][0]
    code = tools.gen_random_code(32)
    if db[message.chat.id] // 10000 == 424242:
        bot.send_message(
            message.chat.id,
            (
                f"Peer information with `{config.SERVER[chosen]}` will be deleted (including BGP Sessions and WireGuard tunnels), and you can always re-create it using /peer.\n"
                f"将要删除与 `{config.SERVER[chosen]}` 的 Peer 信息（包括 BGP Session 和 WireGuard 隧道），你可以随时使用 /peer 重新建立。"
            ),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        bot.send_message(
            message.chat.id,
            (
                f"Peer information with <code>{config.SERVER[chosen]}</code> will be deleted (including BGP Sessions and WireGuard tunnels).\n"
                f"将要删除与 <code>{config.SERVER[chosen]}</code> 的 Peer 信息（包括 BGP Session 和 WireGuard 隧道）。\n\n"
                "<b>Attention 注意</b>\n\n"
                "Your ASN is not in standard DN42 format (<code>AS424242xxxx</code>), so it cannot be auto-peered\n"
                "你的 ASN 不是标准 DN42 格式 (<code>AS424242xxxx</code>)，因此无法进行 AutoPeer\n"
                f"After deleting peer information, you need to contact {config.CONTACT} for manual operation if you need to re-peer.\n"
                f"删除 Peer 信息后，如需重新 Peer，需要联系 {config.CONTACT} 进行人工操作。"
            ),
            parse_mode='HTML',
            reply_markup=ReplyKeyboardRemove(),
        )
    msg = bot.send_message(
        message.chat.id,
        (
            "Enter the following random code to confirm the deletion.\n"
            "输入以下随机码以确认删除。\n"
            "\n"
            f"`{code}`\n"
            "\n"
            "All other inputs indicate the cancellation of the operation.\n"
            "所有其他输入表示取消操作。"
        ),
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardRemove(),
    )
    bot.register_next_step_handler(msg, partial(remove_peer_confirm, code, chosen))


def remove_peer_confirm(code, region, message):
    if message.text.strip() == code:
        try:
            r = requests.post(
                f"http://{region}.{config.ENDPOINT}:{config.API_PORT}/remove",
                data=str(db[message.chat.id]),
                headers={"X-DN42-Bot-Api-Secret-Token": config.API_TOKEN},
                timeout=10,
            )
            if r.status_code != 200:
                raise RuntimeError
        except BaseException:
            bot.send_message(
                message.chat.id,
                (
                    f"Error encountered, please try again. If the problem remains, please contact {config.CONTACT}\n"
                    f"遇到错误，请重试。如果问题依旧，请联系 {config.CONTACT}"
                ),
                parse_mode="HTML",
                reply_markup=ReplyKeyboardRemove(),
            )
            return
        if db[message.chat.id] // 10000 == 424242:
            bot.send_message(
                message.chat.id,
                (
                    "Peer information has been deleted.\n"
                    "Peer 信息已删除。\n"
                    "\n"
                    "You can always re-create it using /peer.\n"
                    "你可以随时使用 /peer 重新建立。"
                ),
                reply_markup=ReplyKeyboardRemove(),
            )
        else:
            bot.send_message(
                message.chat.id,
                (
                    "Peer information has been deleted.\n"
                    "Peer 信息已删除。\n"
                    "\n"
                    f"Contact {config.CONTACT} if you need to re-peer.\n"
                    f"如需重新 Peer 请联系 {config.CONTACT}"
                ),
                parse_mode="HTML",
                reply_markup=ReplyKeyboardRemove(),
            )
        for i in db_privilege - {message.chat.id}:
            bot.send_message(
                i,
                (
                    "*[Privilege]*\n"
                    "Peer Removed!   有 Peer 被删除！\n"
                    f"`{tools.get_asn_mnt_text(db[message.chat.id])}`\n"
                    f"`{config.SERVER[region]}`"
                ),
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardRemove(),
            )
    else:
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
