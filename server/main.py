#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import pickle
import socket
import string
from datetime import datetime, timezone
from functools import partial
from time import sleep

import requests
import telebot
from aiohttp import web
from IPy import IP
from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

import config
import tools

bot = telebot.TeleBot(config.BOT_TOKEN)

try:
    with open("./user_db.pkl", "rb") as f:
        db, db_privilege = pickle.load(f)
except BaseException:
    db = {}
    db_privilege = set()


class IsPrivateChat(telebot.custom_filters.SimpleCustomFilter):
    key = 'is_private_chat'

    @staticmethod
    def check(message):
        is_private = message.chat.type == "private"
        if not is_private:
            bot.reply_to(message, "This command can only be used in private chat.\n此命令只能在私聊中使用。")
        return is_private


class IsForMe(telebot.custom_filters.SimpleCustomFilter):
    key = 'is_for_me'

    @staticmethod
    def check(message):
        command = message.text.strip().split(" ")[0].split("@")
        if len(command) > 1:
            return command[-1].lower() == config.BOT_USERNAME.lower()
        else:
            return True


bot.add_custom_filter(IsPrivateChat())
bot.add_custom_filter(IsForMe())


@bot.message_handler(commands=['start'], is_for_me=True, is_private_chat=True)
def startup(message):
    try:
        if message.text.strip().split(" ")[1] == "peer":
            bot.send_message(
                message.chat.id,
                "Use /peer to create a Peer with me!\n使用 /peer 与我建立 Peer！",
                reply_markup=ReplyKeyboardRemove(),
            )
        elif message.text.strip().split(" ")[1].startswith("whoami_"):
            whoami(message, message.text.strip().split(" ")[1][7:])
    except BaseException:
        send_welcome(message)


@bot.message_handler(commands=['help'], is_for_me=True, is_private_chat=True)
def send_welcome(message):
    bot.send_message(
        message.chat.id,
        (
            f"{config.WELCOME_TEXT}"
            "\n"
            "Command List 指令列表:\n"
            "    Tools:\n"
            "        - /ping [ip/domain]\n"
            "        - /trace [ip/domain]\n"
            "    User Manage:\n"
            "        - /login - Login to verify your ASN 登录以验证你的 ASN\n"
            "        - /logout - Logout current logged ASN 退出当前登录的 ASN\n"
            "        - /whoami - Get current login user 获取当前登录用户\n"
            "    Peer:\n"
            "        - /peer - Set up a peer 设置一个 Peer\n"
            "        - /remove - Remove a peer 移除一个 Peer\n"
            "        - /info - Show your peer info and status 查看你的 Peer 信息及状态\n"
            "\n"
            "You can always use /cancel to interrupt current operation.\n"
            "你始终可以使用 /cancel 终止当前正在进行的操作。\n"
            "\n"
            f"When something unexpected happens or the bot can't meet your needs, please contact {config.CONTACT}\n"
            f"当出现了什么意料之外的，或者机器人无法满足你的需求，请联系 {config.CONTACT}"
        ),
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )


@bot.message_handler(commands=['cancel'], is_for_me=True, is_private_chat=True)
def cancel(message):
    bot.reply_to(message, "No ongoing operations\n没有正在进行的操作", reply_markup=ReplyKeyboardRemove())


def gen_peer_me_markup(message):
    if message.chat.id in db_privilege:
        return None
    if message.chat.type == "private" and message.chat.id in db:
        if tools.get_info(db[message.chat.id]):
            return None
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("Peer with me | 与我 Peer", url=f"https://t.me/{config.BOT_USERNAME}?start=peer"))
    return markup


def get_asn_mnt_text(asn):
    if (s := tools.get_mnt_by_asn(asn)) != f"AS{asn}":
        return f"{s} AS{asn}"
    else:
        return f"AS{asn}"


@bot.message_handler(commands=['ping', 'trace', 'traceroute', 'tracert'], is_for_me=True)
def ping_trace(message):
    command = message.text.strip().split(" ")[0][1:]
    if len(message.text.strip().split(" ")) != 2:
        bot.reply_to(
            message,
            f"Usage: /{command} [ip/domain]\n用法：/{command} [ip/domain]",
            reply_markup=gen_peer_me_markup(message),
        )
        return
    parsed_info = tools.test_ip_domain(message.text.strip().split(" ")[1])
    if not parsed_info:
        bot.reply_to(message, "IP/Domain is wrong\nIP/域名不正确", reply_markup=gen_peer_me_markup(message))
        return
    # if not parsed_info.dn42:
    #     bot.reply_to(
    #         message,
    #         "IP/Domain not in DN42\nIP/域名不属于 DN42",
    #         reply_markup=gen_peer_me_markup(message),
    #     )
    #     return
    if not parsed_info.ip:
        bot.reply_to(message, "Domain can't be resolved 域名无法被解析", reply_markup=gen_peer_me_markup(message))
        return
    msg = bot.reply_to(
        message,
        "```\n{command_text} {ip}{domain} ...\n```".format(
            command_text="Ping" if command == "ping" else "Traceroute",
            ip=parsed_info.ip,
            domain=f" ({parsed_info.domain})" if parsed_info.domain else "",
        ),
        parse_mode="Markdown",
        reply_markup=gen_peer_me_markup(message),
    )
    bot.send_chat_action(chat_id=message.chat.id, action='typing')
    raw = tools.get_test('ping' if command == "ping" else "trace", parsed_info.raw)
    output = "\n\n".join(
        "{server}\n```\n{text}```".format(
            server=config.SERVER[k],
            text=v.text if v.status == 200 else 'Something went wrong.\n发生了一些错误。',
        )
        for k, v in raw.items()
    )
    bot.edit_message_text(
        output,
        parse_mode="Markdown",
        chat_id=message.chat.id,
        message_id=msg.message_id,
        reply_markup=gen_peer_me_markup(message),
    )


def check_login_and_peer(message):
    if message.chat.id not in db:
        bot.send_message(
            message.chat.id,
            "You are not logged in yet, please use /login first.\n你还没有登录，请先使用 /login",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    asn = db[message.chat.id]
    if peer_info := tools.get_info(asn):
        return peer_info
    else:
        bot.send_message(
            message.chat.id,
            ("You are not peer with me yet, you can use /peer to start.\n" "你还没有与我 Peer，可以使用 /peer 开始。"),
            reply_markup=ReplyKeyboardRemove(),
        )
        return


@bot.message_handler(commands=['login'], is_for_me=True, is_private_chat=True)
def start_login(message):
    if message.chat.id in db:
        bot.send_message(
            message.chat.id,
            (
                f"You are already logged in as `{get_asn_mnt_text(db[message.chat.id])}`, please use /logout to log out.\n"
                f"你已经以 `{get_asn_mnt_text(db[message.chat.id])}` 的身份登录了，请使用 /logout 退出。"
            ),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        if len(message.text.strip().split(" ")) != 2:
            msg = bot.send_message(
                message.chat.id,
                "Enter your ASN, without prefix AS\n请输入你的 ASN，不要加 AS 前缀",
                reply_markup=ReplyKeyboardRemove(),
            )
            bot.register_next_step_handler(msg, login_input_asn)
        else:
            login_input_asn(message, message.text.strip().split(" ")[1])


def login_input_asn(message, exist_asn=None):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    try:
        asn = int(exist_asn if exist_asn else message.text.strip())
    except ValueError:
        bot.send_message(
            message.chat.id,
            ("ASN error!\n" "ASN 错误！\n" "You can use /login to retry.\n" "你可以使用 /login 重试。"),
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        emails = tools.get_email(asn)

        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        if emails:
            markup.add(*(KeyboardButton(email) for email in emails))
        markup.add(KeyboardButton("None of the above 以上都不是"))
        msg = bot.send_message(
            message.chat.id,
            ("Select the email address to receive the verification code.\n" "选择接收验证码的邮箱。"),
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, partial(login_choose_email, asn, emails))


def login_choose_email(asn, emails, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if config.PRIVILEGE_CODE and message.text.strip() == config.PRIVILEGE_CODE:
        db[message.chat.id] = asn
        db_privilege.add(message.chat.id)
        with open('./user_db.pkl', 'wb') as f:
            pickle.dump((db, db_privilege), f)
        bot.send_message(
            message.chat.id,
            ("*[Privilege]*\n" f"Welcome! `{get_asn_mnt_text(asn)}`\n" f"欢迎你！`{get_asn_mnt_text(asn)}`"),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if message.text.strip() not in emails:
        msg = bot.send_message(
            message.chat.id,
            (
                "Sorry. For now, you can only use the email address you registered in the DN42 Registry to authenticate.\n"
                "抱歉。暂时只能使用您在 DN42 Registry 中登记的邮箱完成验证。\n"
                f"Please contact {config.CONTACT} for manual handling.\n"
                f"请联系 {config.CONTACT} 人工处理。"
            ),
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    bot.send_message(
        message.chat.id,
        (
            "Sending verification code...\n"
            "正在发送验证码...\n"
            "\n"
            "Hold on, this may take up to 2 minutes to send successfully.\n"
            "稍安勿躁，最多可能需要 2 分钟才能成功发送。"
        ),
        reply_markup=ReplyKeyboardRemove(),
    )
    bot.send_chat_action(chat_id=message.chat.id, action='typing')
    code = tools.gen_random_code(32)
    try:
        config.send_email(asn, tools.get_mnt_by_asn(asn), code, message.text.strip())
    except RuntimeError:
        bot.send_message(
            message.chat.id,
            (
                "Sorry, we are unable to send the verification code to your email address at this time. Please try again later.\n"
                "抱歉，暂时无法发送验证码至您的邮箱。请稍后再试。"
            ),
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        bot.send_message(
            message.chat.id,
            "Verification code has been sent to your email\n验证码已发送至您的邮箱。",
            reply_markup=ReplyKeyboardRemove(),
        )
        msg = bot.send_message(
            message.chat.id,
            "Enter your verification code\n请输入验证码",
            reply_markup=ReplyKeyboardRemove(),
        )
        bot.register_next_step_handler(msg, partial(login_verify_code, asn, code))


def login_verify_code(asn, code, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if message.text.strip() == code:
        db[message.chat.id] = asn
        with open('./user_db.pkl', 'wb') as f:
            pickle.dump((db, db_privilege), f)
        bot.send_message(
            message.chat.id,
            (f"Welcome! `{get_asn_mnt_text(asn)}`\n" f"欢迎你！`{get_asn_mnt_text(asn)}`"),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        bot.send_message(
            message.chat.id,
            ("Verification code error!\n" "验证码错误！\n" "You can use /login to retry.\n" "你可以使用 /login 重试。"),
            reply_markup=ReplyKeyboardRemove(),
        )


@bot.message_handler(commands=['logout'], is_for_me=True, is_private_chat=True)
def start_logout(message):
    if message.chat.id not in db:
        bot.send_message(
            message.chat.id,
            "You are not logged in yet, please use /login first.\n你还没有登录，请先使用 /login",
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        text = (
            f"You have logged out as `{get_asn_mnt_text(db[message.chat.id])}`.\n"
            f"你已经退出 `{get_asn_mnt_text(db[message.chat.id])}` 身份。"
        )
        db.pop(message.chat.id)
        if message.chat.id in db_privilege:
            db_privilege.remove(message.chat.id)
            text = "*[Privilege]*\n" + text
        with open('./user_db.pkl', 'wb') as f:
            pickle.dump((db, db_privilege), f)
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())


@bot.message_handler(commands=['whoami'], is_for_me=True, is_private_chat=True)
def whoami(message, new_asn=None):
    if message.chat.id not in db:
        bot.send_message(
            message.chat.id,
            "You are not logged in yet, please use /login first.\n你还没有登录，请先使用 /login",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if message.chat.id in db_privilege:
        text = "*[Privilege]*\n"
        if not new_asn and len(message.text.strip().split(" ")) == 2:
            new_asn = message.text.strip().split(" ")[1]
        if new_asn:
            try:
                db[message.chat.id] = int(new_asn)
                with open('./user_db.pkl', 'wb') as f:
                    pickle.dump((db, db_privilege), f)
            except BaseException:
                pass
    else:
        text = ""
    text += "Current login user:\n当前登录用户：\n" f"`{get_asn_mnt_text(db[message.chat.id])}`"
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())


@bot.message_handler(commands=['info', 'status'], is_for_me=True, is_private_chat=True)
def get_info(message):
    all_peers = check_login_and_peer(message)
    if all_peers is None:
        return

    def basic_info(asn, endpoint, pubkey, v6, v4):
        text = (
            "    ASN:\n"
            f"        AS{asn}\n"
            "    Endpoint:\n"
            f"        {endpoint}\n"
            "    WireGuard Public Key:\n"
            f"        {pubkey}\n"
            "    DN42 Address:\n"
        )
        ipv6_space = ""
        try:
            if IP(v6) in IP("fc00::/7"):
                text += f"        IPv6 ULA: {v6}/128\n"
                ipv6_space = " " * 4
        except BaseException:
            pass
        try:
            if IP(v6) in IP("fe80::/64"):
                text += f"        IPv6 Link-Local: {v6}/64\n"
                ipv6_space = " " * 11
        except BaseException:
            pass
        try:
            if IP(v4) in IP("172.20.0.0/14"):
                text += f"        IPv4: {ipv6_space}{v4}/32\n"
        except BaseException:
            pass
        return text

    for region, peer_info in all_peers.items():
        if not isinstance(peer_info, dict):
            bot.send_message(
                message.chat.id,
                (
                    f"{config.SERVER[region]}:\n"
                    f"Error occurred. Please contact {config.CONTACT} with following message.\n"
                    f"遇到错误。请联系 {config.CONTACT} 并附带下述结果。\n"
                    f"<code>{peer_info}</code>"
                ),
                parse_mode="HTML",
                reply_markup=ReplyKeyboardRemove(),
            )
            continue

        detail_text = "Information on your side:\n"
        detail_text += basic_info(
            db[message.chat.id],
            peer_info['clearnet'],
            peer_info['pubkey'],
            peer_info['v6'],
            peer_info['v4'],
        )
        detail_text += "Information on my side:\n"
        detail_text += basic_info(
            config.DN42_ASN,
            f"{region}.{config.ENDPOINT}:{peer_info['port']}",
            peer_info['my_pubkey'],
            peer_info['my_v6'],
            peer_info['my_v4'],
        )

        if peer_info['wg_last_handshake'] == 0:
            detail_text += (
                "WireGuard Status:\n"
                "    Latest handshake:\n"
                "        Never\n"
                "    Transfer:\n"
                "        0B received, 0B sent\n"
            )
        else:
            latest_handshake = datetime.fromtimestamp(peer_info['wg_last_handshake'], tz=timezone.utc)
            latest_handshake_td = tools.td_format(datetime.now(tz=timezone.utc) - latest_handshake)
            latest_handshake = latest_handshake.isoformat().replace('+00:00', 'Z')
            transfer = [tools.convert_size(i) for i in peer_info['wg_transfer']]
            detail_text += (
                "WireGuard Status:\n"
                "    Latest handshake:\n"
                f"        {latest_handshake}\n"
                f"        {latest_handshake_td}\n"
                "    Transfer:\n"
                f"        {transfer[0]} received, {transfer[1]} sent\n"
            )

        detail_text += "Bird Status:\n" f"    {peer_info['session']}\n"
        if len(peer_info['bird_status']) == 1:
            bird_status = list(peer_info['bird_status'].values())[0]
            detail_text += f"    {bird_status[0]}\n"
            if bird_status[1]:
                detail_text += f"    {bird_status[1]}\n"
            if len(bird_status[2]) == 2:
                detail_text += f"    IPv4\n        {bird_status[2]['4']}\n"
                detail_text += f"    IPv6\n        {bird_status[2]['6']}\n"
            elif bird_status[2]:
                detail_text += f"    {list(bird_status[2].values())[0]}\n"
        else:
            for session in ('4', '6'):
                bird_status = [v for k, v in peer_info['bird_status'].items() if k.endswith(session)][0]
                detail_text += f"    IPv{session}:\n"
                detail_text += f"        {bird_status[0]}\n"
                if bird_status[1]:
                    detail_text += f"        {bird_status[1]}\n"
                if session in bird_status[2]:
                    detail_text += f"        {bird_status[2][session]}\n"

        detail_text += "Contact:\n" f"    {tools.get_mnt_by_asn(db[message.chat.id])}\n" f"    {peer_info['desc']}\n"

        if config.LG_DOMAIN:
            if len(peer_info['session_name']) == 2:
                session_name = '_'.join(peer_info['session_name'][0].split('_')[:-1])
                url_prefix = f"{config.LG_DOMAIN}/detail/{region}/{session_name}"
                button_list = [
                    [
                        InlineKeyboardButton(text='Looking Glass (IPv4)', url=f'{url_prefix}_v4'),
                        InlineKeyboardButton(text='Looking Glass (IPv6)', url=f'{url_prefix}_v6'),
                    ],
                ]
            else:
                button_list = [
                    [
                        InlineKeyboardButton(
                            text='Looking Glass',
                            url=f'{config.LG_DOMAIN}/detail/{region}/{peer_info["session_name"][0]}',
                        )
                    ]
                ]
            markup = InlineKeyboardMarkup(button_list)
        else:
            markup = ReplyKeyboardRemove()

        bot.send_message(
            message.chat.id,
            (
                f"{config.SERVER[region]}:\n"
                f"```\n{detail_text}```\n"
                "Click the button below to view Looking Glass.\n"
                "点击下方按钮查看 Looking Glass。"
            ),
            parse_mode="Markdown",
            reply_markup=markup,
        )


@bot.message_handler(commands=['peer'], is_for_me=True, is_private_chat=True)
def start_peer(message):
    if message.chat.id not in db:
        bot.send_message(
            message.chat.id,
            "Login with /login first!\n请先使用 /login 登录！",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    peer_info = tools.get_info(db[message.chat.id])
    could_peer = [config.SERVER[i] for i in set(config.SERVER.keys()) - set(peer_info.keys())]
    if could_peer == []:
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

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row_width = 1
    for i in could_peer:
        markup.add(KeyboardButton(i))
    msg = bot.send_message(
        message.chat.id,
        "Which of my nodes do you want to peer with?\n你想要与我的哪个节点 Peer？",
        reply_markup=markup,
    )
    bot.register_next_step_handler(msg, partial(peer_node_choose, could_peer))


def peer_node_choose(could_peer, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
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
        bot.register_next_step_handler(msg, partial(peer_node_choose, could_peer))
        return

    peer_info = {
        "Region": [k for k, v in config.SERVER.items() if v == message.text.strip()][0],
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

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row_width = 3
    markup.add(KeyboardButton("IPv6 & IPv4"), KeyboardButton("IPv6 only"), KeyboardButton("IPv4 only"))
    msg = bot.send_message(
        message.chat.id,
        "What routes do you want to transmit with me?\n你想和我传递哪些路由？",
        reply_markup=markup,
    )
    bot.register_next_step_handler(msg, partial(peer_session_type, peer_info))


def ask_ipv6(message, peer_info):
    msg = bot.send_message(
        message.chat.id,
        (
            "Input your DN42 IPv6 address, without `/L` suffix.\n"
            "请输入你的 DN42 IPv6 地址，不包含 `/L` 后缀。\n"
            "\n"
            "Both Link-Local and ULA address are support. Link-Local is preferred for Bird users while ULA is preferred for other BGP clients.\n"
            "Link-Local 和 ULA 地址均支持。Bird 用户首选 Link-Local，其他 BGP 客户端首选 ULA。"
        ),
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardRemove(),
    )
    bot.register_next_step_handler(msg, partial(peer_ipv6_input, peer_info))


def ask_ipv4(message, peer_info):
    msg = bot.send_message(
        message.chat.id,
        ("Input your DN42 IPv4 address, without `/L` suffix.\n" "请输入你的 DN42 IPv4 地址，不包含 `/L` 后缀。"),
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardRemove(),
    )
    bot.register_next_step_handler(msg, partial(peer_ipv4_input, peer_info))


def peer_session_type(peer_info, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    if (
        message.text.strip().lower() == "ipv6 & ipv4"
        or message.text.strip().lower() == "ipv6 and ipv4"
        or message.text.strip().lower() == "both"
    ):
        peer_info["Channel"] = "IPv6 & IPv4"

        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 2
        markup.add(KeyboardButton("Yes"), KeyboardButton("No"))
        msg = bot.send_message(
            message.chat.id,
            "Do you support Multiprotocol BGP?\n你支持多协议 BGP 吗？",
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, partial(peer_mpbgp_support, peer_info))
    elif message.text.strip().lower() == "ipv6 only" or message.text.strip().lower() == "ipv6":
        peer_info["Channel"] = "IPv6 only"
        ask_ipv6(message, peer_info)
    elif message.text.strip().lower() == "ipv4 only" or message.text.strip().lower() == "ipv4":
        peer_info["Channel"] = "IPv4 only"
        ask_ipv4(message, peer_info)
    else:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 3
        markup.add(KeyboardButton("IPv6 & IPv4"), KeyboardButton("IPv6 only"), KeyboardButton("IPv4 only"))
        msg = bot.send_message(
            message.chat.id,
            ("Invalid input, please try again. Use /cancel to interrupt the operation.\n" "输入不正确，请重试。使用 /cancel 终止操作。"),
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, peer_session_type)


def peer_mpbgp_support(peer_info, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if message.text.strip().lower() == "yes":

        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 2
        markup.add(KeyboardButton("IPv6"), KeyboardButton("IPv4"))
        msg = bot.send_message(
            message.chat.id,
            ("What address do you want to use to establish an MP-BGP session with me?\n" "你想使用什么地址与我建立多协议 BGP 会话？"),
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, partial(peer_mpbgp_type, peer_info))
    elif message.text.strip().lower() == "no":
        ask_ipv6(message, peer_info)
    else:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 2
        markup.add(KeyboardButton("Yes"), KeyboardButton("No"))
        msg = bot.send_message(
            message.chat.id,
            ("Invalid input, please try again. Use /cancel to interrupt the operation.\n" "输入不正确，请重试。使用 /cancel 终止操作。"),
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, partial(peer_mpbgp_support, peer_info))


def peer_mpbgp_type(peer_info, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if message.text.strip().lower() == "ipv6":
        peer_info["MP-BGP"] = "IPv6"

        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 2
        markup.add(KeyboardButton("Yes"), KeyboardButton("No"))
        msg = bot.send_message(
            message.chat.id,
            "Do you support Extended Next Hop?\n你支持扩展的下一跳吗？",
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, partial(peer_enh_support, peer_info))
    elif message.text.strip().lower() == "ipv4":
        peer_info["MP-BGP"] = "IPv4"
        ask_ipv6(message, peer_info)
    else:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 2
        markup.add(KeyboardButton("IPv6"), KeyboardButton("IPv4"))
        msg = bot.send_message(
            message.chat.id,
            ("Invalid input, please try again. Use /cancel to interrupt the operation.\n" "输入不正确，请重试。使用 /cancel 终止操作。"),
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, partial(peer_mpbgp_type, peer_info))


def peer_enh_support(peer_info, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if message.text.strip().lower() == "yes":
        peer_info["ENH"] = True
        peer_info["IPv4"] = "Not required due to Extended Next Hop"
    elif message.text.strip().lower() == "no":
        peer_info["ENH"] = False
    else:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 2
        markup.add(KeyboardButton("Yes"), KeyboardButton("No"))
        msg = bot.send_message(
            message.chat.id,
            ("Invalid input, please try again. Use /cancel to interrupt the operation.\n" "输入不正确，请重试。使用 /cancel 终止操作。"),
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, partial(peer_enh_support, peer_info))
        return
    ask_ipv6(message, peer_info)


def peer_ipv6_input(peer_info, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    try:  # Test for IPv6
        socket.inet_pton(socket.AF_INET6, message.text.strip())
        if IP(message.text.strip()) not in IP("fc00::/7") and IP(message.text.strip()) not in IP("fe80::/64"):
            raise ValueError
    except (socket.error, ValueError):
        msg = bot.send_message(
            message.chat.id,
            (
                "Invalid DN42 IPv6 address, please try again. Use /cancel to interrupt the operation.\n"
                "输入不是有效的 DN42 IPv6 地址，请重试。使用 /cancel 终止操作。"
            ),
            reply_markup=ReplyKeyboardRemove(),
        )
        bot.register_next_step_handler(msg, partial(peer_ipv6_input, peer_info))
        return
    peer_info["IPv6"] = message.text.strip()
    if IP(message.text.strip()) in IP("fe80::/64"):
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        markup.add(KeyboardButton("Auto"))
        msg = bot.send_message(
            message.chat.id,
            (
                "Link-Local address detected. You can enter the address required on my side as needed, without `/L` suffix.\n"
                "检测到 Link-Local 地址。你可以按需输入所需的我这边的地址，不包含 `/L` 后缀。\n\n"
                "If you don't know what this is, or don't need to specify it, select `Auto`.\n"
                "如果你不知道这是什么，或者不需要指定，请选择 `Auto`。"
            ),
            parse_mode="Markdown",
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, partial(peer_request_linklocal_input, peer_info))
    else:
        if peer_info["Channel"] == "IPv6 & IPv4" and peer_info["ENH"] is not True:
            ask_ipv4(message, peer_info)
        else:
            msg = bot.send_message(
                message.chat.id,
                (
                    "Input your clearnet address for WireGuard tunnel, without port.\n"
                    "请输入你用于 WireGurad 隧道的公网地址，不包含端口。\n\n"
                    "If you don't have a static clearnet address or is behind NAT, please enter `none`\n"
                    "如果你没有静态公网地址，或你的服务器在 NAT 网络中，请输入 `none`"
                ),
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardRemove(),
            )
            bot.register_next_step_handler(msg, partial(peer_clearnet_input, peer_info))


def peer_request_linklocal_input(peer_info, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if message.text.strip().lower() != "auto":
        try:  # Test for IPv6
            socket.inet_pton(socket.AF_INET6, message.text.strip())
            if IP(message.text.strip()) not in IP("fe80::/64"):
                raise ValueError
        except (socket.error, ValueError):
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row_width = 1
            markup.add(KeyboardButton("Auto"))
            msg = bot.send_message(
                message.chat.id,
                (
                    "Invalid DN42 IPv6 Link-Local address, please try again. Use /cancel to interrupt the operation.\n"
                    "输入不是有效的 DN42 IPv6 Link-Local 地址，请重试。使用 /cancel 终止操作。"
                ),
                reply_markup=markup,
            )
            bot.register_next_step_handler(msg, partial(peer_request_linklocal_input, peer_info))
            return
        peer_info["Request-LinkLocal"] = message.text.strip()
    else:
        peer_info["Request-LinkLocal"] = "Not specified"
    if peer_info["Channel"] == "IPv6 & IPv4" and peer_info["ENH"] is not True:
        ask_ipv4(message, peer_info)
    else:
        msg = bot.send_message(
            message.chat.id,
            (
                "Input your clearnet address for WireGuard tunnel, without port.\n"
                "请输入你用于 WireGurad 隧道的公网地址，不包含端口。\n\n"
                "If you don't have a static clearnet address or is behind NAT, please enter `none`\n"
                "如果你没有静态公网地址，或你的服务器在 NAT 网络中，请输入 `none`"
            ),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
        bot.register_next_step_handler(msg, partial(peer_clearnet_input, peer_info))


def peer_ipv4_input(peer_info, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    try:  # Test for IPv4
        socket.inet_pton(socket.AF_INET, message.text.strip())
        if IP(message.text.strip()) not in IP("172.20.0.0/14"):
            raise ValueError
    except (socket.error, ValueError):
        msg = bot.send_message(
            message.chat.id,
            (
                "Invalid DN42 IPv4 address, please try again. Use /cancel to interrupt the operation.\n"
                "输入不是有效的 DN42 IPv4 地址，请重试。使用 /cancel 终止操作。"
            ),
            reply_markup=ReplyKeyboardRemove(),
        )
        bot.register_next_step_handler(msg, partial(peer_ipv4_input, peer_info))
        return
    peer_info["IPv4"] = message.text.strip()
    msg = bot.send_message(
        message.chat.id,
        (
            "Input your clearnet address for WireGuard tunnel, without port.\n"
            "请输入你用于 WireGurad 隧道的公网地址，不包含端口。\n\n"
            "If you don't have a static clearnet address or is behind NAT, please enter `none`\n"
            "如果你没有静态公网地址，或你的服务器在 NAT 网络中，请输入 `none`"
        ),
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    bot.register_next_step_handler(msg, partial(peer_clearnet_input, peer_info))


def peer_clearnet_input(peer_info, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    if message.text.strip().lower() != "none":
        if tools.test_clearnet(message.text.strip()):
            peer_info["Clearnet"] = tools.test_clearnet(message.text.strip())
        else:
            if message.chat.id not in db_privilege:
                msg = bot.send_message(
                    message.chat.id,
                    (
                        "Invalid or unreachable clearnet address, please try again.\n"
                        "输入不是有效的公网地址或该地址不可达，请重试。\n"
                        f"The check procedure may sometimes be wrong, if it is confirmed to be valid, just resubmit. If the error keeps occurring please contact {config.CONTACT}\n"
                        f"判定程序可能出错。如果确认有效，重新提交即可。重复出错请联系 {config.CONTACT}\n"
                        "Use /cancel to interrupt the operation.\n"
                        "使用 /cancel 终止操作。"
                    ),
                    reply_markup=ReplyKeyboardRemove(),
                    parse_mode="HTML",
                )
                bot.register_next_step_handler(msg, partial(peer_clearnet_input, peer_info))
                return
            else:
                bot.send_message(
                    message.chat.id,
                    (
                        "*[Privilege]*\n"
                        "Invalid or unreachable clearnet address.\n"
                        "输入不是有效的公网地址或该地址不可达。\n"
                        "Use the privilege to continue the process. Use /cancel to exit if there is a mistake.\n"
                        "使用特权，流程继续。如确认有误使用 /cancel 退出。"
                    ),
                    parse_mode='Markdown',
                    reply_markup=ReplyKeyboardRemove(),
                )
                peer_info["Clearnet"] = message.text.strip()
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        markup.add(KeyboardButton(str(config.DN42_ASN % 100000)))
        msg = bot.send_message(
            message.chat.id,
            "Input your port for WireGuard tunnel.\n请输入你用于 WireGurad 隧道的端口。",
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, partial(peer_port_input, peer_info))
    else:
        if message.chat.id in db_privilege:
            text = "*[Privilege]*\n" "Enter the port number you provided to your peer-er\n" "请输入你给对方提供的端口号"
            if peer_info["Port"]:
                markup = ReplyKeyboardMarkup(resize_keyboard=True)
                markup.row_width = 1
                markup.add(KeyboardButton(str(peer_info['Port'])))
            else:
                markup = ReplyKeyboardRemove()
            msg = bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)
            bot.register_next_step_handler(msg, partial(peer_myside_port_input_admin, peer_info))
        else:
            msg = bot.send_message(
                message.chat.id,
                "Input your WireGuard public key\n请输入你的 WireGuard 公钥",
                reply_markup=ReplyKeyboardRemove(),
            )
            bot.register_next_step_handler(msg, partial(peer_pubkey_input, peer_info))


def peer_port_input(peer_info, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    try:
        port = int(message.text.strip())
        if not (0 < port <= 65535):
            raise ValueError
    except ValueError:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row_width = 1
        markup.add(KeyboardButton(str(config.DN42_ASN % 100000)))
        msg = bot.send_message(
            message.chat.id,
            (
                "Invalid port, please try again. Use /cancel to interrupt the operation.\n"
                "输入不是有效的端口，请重试。使用 /cancel 终止操作。"
            ),
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, partial(peer_port_input, peer_info))
        return
    peer_info["Clearnet"] += f":{message.text.strip()}"
    if message.chat.id in db_privilege:
        text = "*[Privilege]*\n" "Enter the port number you provided to your peer-er\n" "请输入你给对方提供的端口号"
        if peer_info["Port"]:
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row_width = 1
            markup.add(KeyboardButton(str(peer_info['Port'])))
        else:
            markup = ReplyKeyboardRemove()
        msg = bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)
        bot.register_next_step_handler(msg, partial(peer_myside_port_input_admin, peer_info))
    else:
        msg = bot.send_message(
            message.chat.id,
            "Input your WireGuard public key\n请输入你的 WireGuard 公钥",
            reply_markup=ReplyKeyboardRemove(),
        )
        bot.register_next_step_handler(msg, partial(peer_pubkey_input, peer_info))


def peer_myside_port_input_admin(peer_info, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    try:
        port = int(message.text.strip())
        if not (0 < port <= 65535):
            raise ValueError
    except ValueError:
        if peer_info["Port"]:
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row_width = 1
            markup.add(KeyboardButton(str(peer_info['Port'])))
        else:
            markup = ReplyKeyboardRemove()
        msg = bot.send_message(
            message.chat.id,
            (
                "Invalid port, please try again. Use /cancel to interrupt the operation.\n"
                "输入不是有效的端口，请重试。使用 /cancel 终止操作。"
            ),
            reply_markup=markup,
        )
        bot.register_next_step_handler(msg, partial(peer_myside_port_input_admin, peer_info))
        return
    peer_info["Port"] = message.text.strip()
    msg = bot.send_message(
        message.chat.id,
        "Input your WireGuard public key\n请输入你的 WireGuard 公钥",
        reply_markup=ReplyKeyboardRemove(),
    )
    bot.register_next_step_handler(msg, partial(peer_pubkey_input, peer_info))


def peer_pubkey_input(peer_info, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if len(message.text.strip()) != 44 or message.text.strip()[-1] != '=':
        msg = bot.send_message(
            message.chat.id,
            (
                "Invalid public key, please try again. Use /cancel to interrupt the operation.\n"
                "输入不是有效的公钥，请重试。使用 /cancel 终止操作。"
            ),
            reply_markup=ReplyKeyboardRemove(),
        )
        bot.register_next_step_handler(msg, partial(peer_pubkey_input, peer_info))
        return
    peer_info["PublicKey"] = message.text.strip()
    msg = bot.send_message(
        message.chat.id,
        ("Input your contact information (Telegram or Email)\n" "请输入你的联系方式（Telegram 或 Email）"),
        reply_markup=ReplyKeyboardRemove(),
    )
    bot.register_next_step_handler(msg, partial(peer_contact_input, peer_info))


def peer_contact_input(peer_info, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    allowed_punctuation = "!#$%&()*+,-./:;<=>?@[]^_{|}~"
    if message.text.strip() == "" or any(
        c not in (string.ascii_letters + string.digits + allowed_punctuation + ' ') for c in message.text.strip()
    ):
        msg = bot.send_message(
            message.chat.id,
            (
                "Only non-empty strings which contain only upper and lower case letters, numbers, spaces and the following special symbols are accepted.\n"
                "只接受仅由大小写英文字母、数字、空格及以下特殊符号组成的非空字符串。\n"
                "\n"
                f"`{allowed_punctuation}`\n"
                "\n"
                "Please try again. Use /cancel to interrupt the operation.\n"
                "请重试。使用 /cancel 终止操作。"
            ),
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="Markdown",
        )
        bot.register_next_step_handler(msg, partial(peer_contact_input, peer_info))
        return
    peer_info["Contact"] = message.text.strip()
    all_text = (
        "Region:\n"
        f"    {config.SERVER[peer_info['Region']]}\n"
        "Basic:\n"
        f"    ASN:         AS{peer_info['ASN']}\n"
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
    bot.register_next_step_handler(msg, partial(peer_confirm, peer_info))


def peer_confirm(peer_info, message):
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
                    f"`{get_asn_mnt_text(peer_info['ASN'])}`\n"
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


@bot.message_handler(commands=['remove'], is_for_me=True, is_private_chat=True)
def remove_peer(message):
    peer_info = check_login_and_peer(message)
    if peer_info is None:
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
                        f"`{get_asn_mnt_text(db[message.chat.id])}`\n"
                        f"`{config.SERVER[region]}`"
                    ),
                    parse_mode="Markdown",
                    reply_markup=ReplyKeyboardRemove(),
                )
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


bot.enable_save_next_step_handlers(delay=2, filename="./step.save")
bot.load_next_step_handlers(filename="./step.save")

# ##################################################
# Webhook server
# ##################################################

WEBHOOK_SECRET = tools.gen_random_code(32)

bot.remove_webhook()
sleep(0.5)
bot.set_webhook(url=config.WEBHOOK_URL, secret_token=WEBHOOK_SECRET)


async def handle(request):
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret == WEBHOOK_SECRET:
        request_body_dict = await request.json()
        update = telebot.types.Update.de_json(request_body_dict)
        bot.process_new_updates([update])
        return web.Response()
    else:
        return web.Response(status=403)


app = web.Application()
app.router.add_post('/', handle)
web.run_app(app, host=config.WEBHOOK_LISTEN_HOST, port=config.WEBHOOK_LISTEN_PORT)
