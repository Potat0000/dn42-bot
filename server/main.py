#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pickle
import time

import config
import sentry_sdk
import telebot
import tools
from aiohttp import web
from base import bot, db, db_privilege
from telebot.handler_backends import BaseMiddleware, CancelUpdate
from telebot.types import BotCommandScopeAllPrivateChats, ReplyKeyboardRemove

import commands

MIN_AGENT_VERSION = 9


class IsPrivateChat(telebot.custom_filters.SimpleCustomFilter):
    key = 'is_private_chat'

    @staticmethod
    def check(message):
        is_private = message.chat.type == "private"
        if not is_private:
            bot.reply_to(
                message,
                "This command can only be used in private chat.\n此命令只能在私聊中使用。",
                reply_markup=ReplyKeyboardRemove(),
            )
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


class MyMiddleware(BaseMiddleware):
    def __init__(self):
        self.update_types = ['message']

    def pre_process(self, message, data):
        if not message.text:
            return CancelUpdate()
        command = message.text.strip().split(" ")[0].split("@")
        if len(command) > 1:
            if command[-1].lower() != config.BOT_USERNAME.lower():
                return CancelUpdate()
        if config.SENTRY_DSN and command[0].startswith("/"):
            self.transaction = sentry_sdk.start_transaction(
                name=f"Server {command[0]}",
                op=message.text.strip(),
                sampled=True,
            )
            if message.from_user.username:
                self.transaction.set_tag("username", message.from_user.username)
                sentry_sdk.set_user(
                    {
                        "username": f"{message.from_user.full_name} @{message.from_user.username}",
                        "id": message.from_user.id,
                    }
                )
            else:
                sentry_sdk.set_user(
                    {
                        "username": f"{message.from_user.full_name}",
                        "id": message.from_user.id,
                    }
                )
                sentry_sdk.set_user({"id": message.from_user.id})
            self.transaction.set_tag("user_fullname", message.from_user.full_name)
            self.transaction.set_tag("chat_id", message.chat.id)
            self.transaction.set_tag("chat_type", message.chat.type)
            if message.chat.type == "private":
                if message.chat.id in db_privilege:
                    self.transaction.set_tag("privilege", "True")
                    self.transaction.set_tag("ASN", db[message.chat.id])
                elif message.chat.id in db:
                    self.transaction.set_tag("ASN", db[message.chat.id])
            else:
                if message.chat.title:
                    self.transaction.set_tag("title", message.chat.title)

    def post_process(self, message, data, exception):
        if exception:
            bot.send_message(
                message.chat.id,
                f"Error encountered! Please contact {config.CONTACT}\n遇到错误！请联系 {config.CONTACT}",
                parse_mode='HTML',
                reply_markup=ReplyKeyboardRemove(),
            )
        if self.transaction:
            if exception:
                self.transaction.set_status("error")
                sentry_sdk.capture_exception(exception)
            else:
                self.transaction.set_status("ok")
            self.transaction.finish()


offline_node = []
old_node = []
for k, v in tools.get_from_agent('version', None).items():
    if v.status != 200:
        offline_node.append(k)
    elif int(v.text) < MIN_AGENT_VERSION:
        old_node.append(k)
if offline_node or old_node:
    if offline_node:
        print("Offline node: " + ', '.join(offline_node))
    if old_node:
        print("Old node: " + ', '.join(old_node))
    exit(1)

if config.SENTRY_DSN:
    sentry_sdk.init(
        dsn=config.SENTRY_DSN,
        traces_sample_rate=0,
    )

route_stats_timer = tools.LoopTimer(900, tools.get_route_stats, "Update Route Stats Timer", update=True)
route_stats_timer.start()

try:
    with open("./rank.pkl", "rb") as f:
        tools.get_map(update=pickle.load(f))
except BaseException:
    pass
rank_timer = tools.LoopTimer(900, tools.get_map, "Update Rank Timer", update=True)
rank_timer.start()

bot.add_custom_filter(IsPrivateChat())
bot.setup_middleware(MyMiddleware())

cmd_list = {
    'ping': ('Ping IP / Domain', True),
    'trace': ('Traceroute IP / Domain', True),
    'route': ('Route to IP / Domain', True),
    'whois': ('Whois', True),
    'login': ('Login to verify your ASN 登录以验证你的 ASN', False),
    'logout': ('Logout current logged ASN 退出当前登录的 ASN', False),
    'whoami': ('Get current login user 获取当前登录用户', False),
    'peer': ('Set up a peer 设置一个 Peer', False),
    'modify': ('Modify peer information 修改 Peer 信息', False),
    'remove': ('Remove a peer 移除一个 Peer', False),
    'info': ('Show your peer info and status 查看你的 Peer 信息及状态', False),
    'restart': ('Restart tunnel and bird session 重启隧道及 Bird 会话', False),
    'rank': ('Show DN42 global ranking 显示 DN42 总体排名', True),
    'stats': ('Show DN42 user basic info & statistics 显示 DN42 用户基本信息及数据', True),
    'peer_list': ('Show the peer situation of a user 显示某 DN42 用户的 Peer 情况', True),
    'route_stats': ('Show preferred routes ranking 显示优选 Routes 排名', True),
    'cancel': ('Cancel ongoing operations 取消正在进行的操作', True),
    'help': ('Get help text 获取帮助文本', True),
}
bot.delete_my_commands()
bot.set_my_commands(
    [telebot.types.BotCommand(cmd, desc) for cmd, (desc, public_available) in cmd_list.items() if public_available]
)
bot.set_my_commands(
    [telebot.types.BotCommand(cmd, desc) for cmd, (desc, _) in cmd_list.items()],
    scope=BotCommandScopeAllPrivateChats(),
)

bot.enable_save_next_step_handlers(delay=2, filename="./step.save")
bot.load_next_step_handlers(filename="./step.save")


bot.remove_webhook()

if config.WEBHOOK_URL:
    time.sleep(0.5)
    WEBHOOK_SECRET = tools.gen_random_code(32)
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

else:
    bot.infinity_polling()
