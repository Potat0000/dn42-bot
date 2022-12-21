# -*- coding: utf-8 -*-
import json
from functools import partial

import commands.peer.info_collect as info_collect
import config
import requests
import tools
from base import bot, db, db_privilege
from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)


@bot.message_handler(commands=['peer'], is_private_chat=True)
def start_peer(message):
    peer_info = {
        "Region": None,
        "ASN": db[message.chat.id],
        "Channel": None,
        "MP-BGP": "Not supported",
        "ENH": None,
        "IPv6": "Not enabled",
        "IPv4": "Not enabled",
        "Request-LinkLocal": "Not required due to not use LLA as IPv6",
        "Clearnet": None,
        "PublicKey": None,
        "Port": None,
        "Contact": None,
    }
    if db[message.chat.id] // 10000 == 424242:
        peer_info["Port"] = str(peer_info['ASN'])[-5:]
    step_manage('init', peer_info, message)


def step_manage(next_step, peer_info, message):
    def _call(func):
        if message:
            rtn = func(message, peer_info)
        else:
            rtn = func(peer_info)
        if rtn:
            rtn_next_step, rtn_peer_info, rtn_msg = rtn
            if rtn_next_step.startswith('post_'):
                bot.register_next_step_handler(rtn_msg, partial(step_manage, rtn_next_step, rtn_peer_info))
            elif rtn_next_step.startswith('pre_'):
                step_manage(rtn_next_step, rtn_peer_info, rtn_msg)

    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if next_step in globals() and callable(globals()[next_step]):
        _call(globals()[next_step])
    else:
        _call(getattr(info_collect, next_step))


def init(message, peer_info):
    if message.chat.id not in db:
        bot.send_message(
            message.chat.id,
            "You are not logged in yet, please use /login first.\n你还没有登录，请先使用 /login",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    could_peer = set(config.SERVER.keys()) - set(tools.get_info(db[message.chat.id]).keys())
    if (db[message.chat.id] // 10000 != 424242) and (message.chat.id not in db_privilege):
        bot.send_message(
            message.chat.id,
            (
                f"Your ASN is not in standard DN42 format (<code>AS424242xxxx</code>), so it cannot be auto-peered, please contact {config.CONTACT} for manual peer.\n"
                f"你的 ASN 不是标准 DN42 格式 (<code>AS424242xxxx</code>)，因此无法进行 AutoPeer，请联系 {config.CONTACT} 进行人工 Peer。"
            ),
            parse_mode='HTML',
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if not could_peer:
        bot.send_message(
            message.chat.id,
            (
                "You already peer with all my nodes.\n"
                "你已经和我的所有节点 Peer 了。\n"
                "\n"
                "Use /info for more information.\n"
                "使用 /info 查看更多信息。"
            ),
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    bot.send_message(
        message.chat.id,
        (
            "You will peer with me through the following identity:\n"
            "你将通过以下身份与我 Peer：\n"
            f"<code>AS{db[message.chat.id]}</code>\n"
            "\n"
            "If it is wrong, please use /cancel to interrupt the operation.\n"
            "如果有误请输入 /cancel 终止操作。\n"
            "\n"
            f"Any problems with the AutoPeer process, please contact {config.CONTACT}\n"
            f"AutoPeer 过程中产生任何问题，请联系 {config.CONTACT}"
        ),
        parse_mode='HTML',
        reply_markup=ReplyKeyboardRemove(),
    )
    return 'pre_region', peer_info, message


def pre_region(message, peer_info):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row_width = 1
    could_peer = set(config.SERVER.keys()) - set(tools.get_info(db[message.chat.id]).keys())
    for i in could_peer:
        markup.add(KeyboardButton(config.SERVER[i]))
    msg = bot.send_message(
        message.chat.id,
        "Which of my nodes do you want to peer with?\n你想要与我的哪个节点 Peer？",
        reply_markup=markup,
    )
    return 'post_region', peer_info, msg


def post_region(message, peer_info):
    could_peer = [config.SERVER[i] for i in set(config.SERVER.keys()) - set(tools.get_info(db[message.chat.id]).keys())]
    if message.text.strip() not in could_peer:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        for i in could_peer:
            markup.add(KeyboardButton(i))
        msg = bot.send_message(
            message.chat.id,
            ("Invalid input, please try again. Use /cancel to interrupt the operation.\n" "输入不正确，请重试。使用 /cancel 终止操作。"),
            reply_markup=markup,
        )
        return 'post_region', peer_info, msg
    peer_info['Region'] = next(k for k, v in config.SERVER.items() if v == message.text.strip())
    return 'pre_session_type', peer_info, message


def pre_confirm(message, peer_info):
    all_text = (
        "Region:\n"
        f"    {config.SERVER[peer_info['Region']]}\n"
        "Basic:\n"
        f"    ASN:         {peer_info['ASN']}\n"
        f"    Channel:     {peer_info['Channel']}\n"
        f"    MP-BGP:      {peer_info['MP-BGP']}\n"
        f"    IPv6:        {peer_info['IPv6']}\n"
        f"    IPv4:        {peer_info['IPv4']}\n"
        f"    Request-LLA: {peer_info['Request-LinkLocal']}\n"
        "Tunnel:\n"
        f"    Endpoint:    {peer_info['Clearnet']}\n"
        f"    PublicKey:   {peer_info['PublicKey']}\n"
        "Contact:\n"
        f"    {peer_info['Contact']}\n"
    )
    msg = bot.send_message(
        message.chat.id,
        (
            "Please check all your information\n"
            "请确认你的信息\n"
            "\n"
            f"```\n{all_text}```\n"
            "Please enter `yes` to confirm. 确认无误请输入 `yes`。\n"
            "All other inputs indicate the cancellation of the operation.\n"
            "所有其他输入表示取消操作。"
        ),
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardRemove(),
    )
    return 'post_confirm', peer_info, msg


def post_confirm(message, peer_info):
    if message.text.strip().lower() == "yes":
        try:
            r = requests.post(
                f"http://{peer_info['Region']}.{config.ENDPOINT}:{config.API_PORT}/peer",
                data=json.dumps(peer_info),
                headers={"X-DN42-Bot-Api-Secret-Token": config.API_TOKEN},
                timeout=10,
            )
            if r.status_code != 200:
                raise RuntimeError
            bot.send_message(
                message.chat.id,
                ("Peer has been created. Peer 已建立。\n" "\n" "Use /info for related information.\n" "使用 /info 查看相关信息。"),
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardRemove(),
            )

            def gen_privilege_markup():
                markup = InlineKeyboardMarkup()
                markup.row_width = 1
                markup.add(
                    InlineKeyboardButton(
                        "Switch to it | 切换至该身份",
                        url=f"https://t.me/{config.BOT_USERNAME}?start=whoami_{peer_info['ASN']}",
                    )
                )
                return markup

            for i in db_privilege - {message.chat.id}:
                text = (
                    "*[Privilege]*\n"
                    "New Peer!   新 Peer！\n"
                    f"`{tools.get_asn_mnt_text(peer_info['ASN'])}`\n"
                    f"`{config.SERVER[peer_info['Region']]}`"
                )
                markup = ReplyKeyboardRemove()
                if peer_info['ASN'] == db[i]:
                    text += "\n\nAlready as this user 已在该身份"
                else:
                    markup = gen_privilege_markup()
                bot.send_message(i, text, parse_mode="Markdown", reply_markup=markup)
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
    else:
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
