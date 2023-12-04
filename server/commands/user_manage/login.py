# -*- coding: utf-8 -*-
import pickle
import re
import shlex
import subprocess
from functools import partial

import config
import tools
from base import bot, db, db_privilege
from telebot.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove


def get_email(asn):
    try:
        whois1 = (
            subprocess.check_output(shlex.split(f"whois -h {config.WHOIS_ADDRESS} AS{asn}"), timeout=3)
            .decode("utf-8")
            .split("\n")[3:]
        )
        for line in whois1:
            if line.startswith("admin-c:"):
                admin_c = line.split(":")[1].strip()
                break
        else:
            return set()
        whois2 = (
            subprocess.check_output(shlex.split(f"whois -h {config.WHOIS_ADDRESS} {admin_c}"), timeout=3)
            .decode("utf-8")
            .split("\n")[3:]
        )
        emails = set()
        for line in whois2:
            if line.startswith("e-mail:"):
                email = line.split(":")[1].strip()
                if re.fullmatch(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', email):
                    emails.add(email)
        for line in whois2:
            if line.startswith("contact:"):
                email = line.split(":")[1].strip()
                if re.fullmatch(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', email):
                    emails.add(email)
        if emails:
            return emails
        else:
            return set()
    except BaseException:
        return set()


@bot.message_handler(commands=['login'], is_private_chat=True)
def start_login(message):
    if message.chat.id in db:
        bot.send_message(
            message.chat.id,
            (
                f"You are already logged in as `{tools.get_asn_mnt_text(db[message.chat.id])}`, please use /logout to log out.\n"
                f"你已经以 `{tools.get_asn_mnt_text(db[message.chat.id])}` 的身份登录了，请使用 /logout 退出。"
            ),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    try:
        asn = int(message.text.strip().split()[1])
        login_input_asn(asn, message)
    except (IndexError, ValueError):
        msg = bot.send_message(
            message.chat.id,
            "Enter your ASN, without prefix AS\n请输入你的 ASN，不要加 AS 前缀",
            reply_markup=ReplyKeyboardRemove(),
        )
        bot.register_next_step_handler(msg, partial(login_input_asn, None))


def login_input_asn(exist_asn, message):
    raw = exist_asn if exist_asn else message.text.strip()
    if raw == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    try:
        asn = int(raw)
    except ValueError:
        bot.send_message(
            message.chat.id,
            ("ASN error!\n" "ASN 错误！\n" "You can use /login to retry.\n" "你可以使用 /login 重试。"),
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        emails = get_email(asn)

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
        bot.register_next_step_handler(msg, partial(login_choose_email, asn, emails, msg.message_id))


def login_choose_email(asn, emails, last_msg_id, message):
    if message.text.strip() == "/cancel":
        bot.send_message(
            message.chat.id,
            "Current operation has been cancelled.\n当前操作已被取消。",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if (
        config.PRIVILEGE_CODE
        and (not (config.SINGLE_PRIVILEGE and db_privilege))
        and message.text.strip() == config.PRIVILEGE_CODE
    ):
        db[message.chat.id] = asn
        db_privilege.add(message.chat.id)
        with open('./user_db.pkl', 'wb') as f:
            pickle.dump((db, db_privilege), f)
        bot.delete_message(message.chat.id, message.message_id)
        bot.delete_message(message.chat.id, last_msg_id)
        bot.send_message(
            message.chat.id,
            ("*[Privilege]*\n" f"Welcome! `{tools.get_asn_mnt_text(asn)}`\n" f"欢迎你！`{tools.get_asn_mnt_text(asn)}`"),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    if message.text.strip() not in emails:
        bot.send_message(
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
    msg = bot.send_message(
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
        config.send_email(asn, tools.get_whoisinfo_by_asn(asn), code, message.text.strip())
    except RuntimeError:
        bot.delete_message(message.chat.id, msg.message_id)
        bot.send_message(
            message.chat.id,
            (
                "Sorry, we are unable to send the verification code to your email address at this time. Please try again later.\n"
                "抱歉，暂时无法发送验证码至您的邮箱。请稍后再试。\n"
                f"Please contact {config.CONTACT} if it keeps failing.\n"
                f"如果一直发送失败请联系 {config.CONTACT} 处理。"
            ),
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        bot.delete_message(message.chat.id, msg.message_id)
        msg = bot.send_message(
            message.chat.id,
            (
                "Verification code has been sent to your email.\n"
                "验证码已发送至您的邮箱。\n"
                f"Please contact {config.CONTACT} if you can not receive it.\n"
                f"如果无法收到请联系 {config.CONTACT}\n"
                "\n"
                "Enter your verification code:\n"
                "请输入验证码："
            ),
            parse_mode="HTML",
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
            (f"Welcome! `{tools.get_asn_mnt_text(asn)}`\n" f"欢迎你！`{tools.get_asn_mnt_text(asn)}`"),
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        bot.send_message(
            message.chat.id,
            ("Verification code error!\n" "验证码错误！\n" "You can use /login to retry.\n" "你可以使用 /login 重试。"),
            reply_markup=ReplyKeyboardRemove(),
        )
