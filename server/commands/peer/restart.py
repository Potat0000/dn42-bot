# -*- coding: utf-8 -*-
from functools import partial

import config
import requests
import tools
from base import bot, db, db_privilege
from telebot.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove


@bot.message_handler(commands=['restart'], is_private_chat=True)
def restart_peer(message):
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

    peered = [config.SERVER[i] for i in peer_info.keys()]

    if len(peered) == 1:
        could_chosen = peered[0]
        bot.send_message(
            message.chat.id,
            (
                f"Only one available node, automatically select `{could_chosen}`\n"
                f"只有一个可选节点，自动选择 `{could_chosen}`\n"
                "\n"
                "If not wanted, use /cancel to interrupt the operation.\n"
                "如非所需，使用 /cancel 终止操作。"
            ),
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove(),
        )
        restart_peer_choose(peered, could_chosen, message)
    else:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        for i in peered:
            markup.add(KeyboardButton(i))
        msg = bot.send_message(
            message.chat.id,
            "Which node do you want to restart the tunnel and Bird session with?\n你想要重启与哪个节点的隧道及 Bird 会话？",
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, partial(restart_peer_choose, peered, None))


def restart_peer_choose(peered, chosen, message):
    if not chosen:
        chosen = message.text.strip()
    if chosen == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if chosen not in peered:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        for i in peered:
            markup.add(KeyboardButton(i))
        msg = bot.send_message(
            message.chat.id,
            ("Invalid input, please try again. Use /cancel to interrupt the operation.\n" "输入不正确，请重试。使用 /cancel 终止操作。"),
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, partial(restart_peer_choose, peered, None))
        return

    chosen = next(k for k, v in config.SERVER.items() if v == chosen)

    msg = bot.send_message(
        message.chat.id,
        (
            "The tunnel and Bird sessions with the following nodes will be restarted soon.\n"
            "即将重启与以下节点的隧道及 Bird 会话。\n"
            "\n"
            f"`{config.SERVER[chosen]}`\n"
            "\n"
            "Please enter an *uppercase* `yes` to confirm. All other inputs indicate the cancellation of the operation.\n"
            "确认无误请输入*大写* `yes`，所有其他输入表示取消操作。"
        ),
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardRemove(),
    )
    bot.register_next_step_handler(msg, partial(restart_peer_confirm, chosen))


def restart_peer_confirm(region, message):
    if message.text.strip() != "YES":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    try:
        r = requests.post(
            f"http://{region}.{config.ENDPOINT}:{config.API_PORT}/restart",
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
    bot.send_message(
        message.chat.id,
        ("The tunnel and Bird sessions have been restarted.\n" "隧道及 Bird 会话已重启。\n"),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
