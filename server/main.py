#!/usr/bin/env python3

import pickle
import re
import time

import base
import commands  # noqa: F401
import config
import sentry_sdk
import telebot
import tools
import urllib3
from aiohttp import web
from apscheduler.schedulers.background import BackgroundScheduler
from base import bot, db, db_privilege
from pytz import utc
from telebot.handler_backends import BaseMiddleware, CancelUpdate
from telebot.types import BotCommandScopeAllPrivateChats, ReplyKeyboardRemove


class IsPrivateChat(telebot.custom_filters.SimpleCustomFilter):
    key = 'is_private_chat'

    @staticmethod
    def check(message):
        is_private = message.chat.type == 'private'
        if not is_private:
            bot.reply_to(
                message,
                'This command can only be used in private chat.\n此命令只能在私聊中使用。',
                reply_markup=ReplyKeyboardRemove(),
            )
        return is_private


class IsForMe(telebot.custom_filters.SimpleCustomFilter):
    key = 'is_for_me'

    @staticmethod
    def check(message):
        command = message.text.split()[0].split('@')
        if len(command) > 1:
            return command[-1].lower() == bot.get_me().username.lower()
        else:
            return True


class MyMiddleware(BaseMiddleware):
    def __init__(self):
        self.update_types = ['message']

    def pre_process(self, message, data):
        if not message.text:
            return CancelUpdate()
        command = message.text.split()[0].split('@')
        if len(command) > 1:
            if command[-1].lower() != bot.get_me().username.lower():
                return CancelUpdate()
        if config.SENTRY_DSN and command[0].startswith('/'):
            self.transaction = sentry_sdk.start_transaction(
                name=f'Server {command[0]}',
                op=message.text.strip(),
                sampled=True,
            )
            if message.from_user.username:
                self.transaction.set_tag('username', message.from_user.username)
                sentry_sdk.set_user(
                    {
                        'username': f'{message.from_user.full_name} @{message.from_user.username}',
                        'id': message.from_user.id,
                    }
                )
            else:
                sentry_sdk.set_user(
                    {
                        'username': f'{message.from_user.full_name}',
                        'id': message.from_user.id,
                    }
                )
                sentry_sdk.set_user({'id': message.from_user.id})
            self.transaction.set_tag('user_fullname', message.from_user.full_name)
            self.transaction.set_tag('chat_id', message.chat.id)
            self.transaction.set_tag('chat_type', message.chat.type)
            if message.chat.type == 'private':
                if message.chat.id in db_privilege:
                    self.transaction.set_tag('privilege', 'True')
                    self.transaction.set_tag('ASN', db[message.chat.id])
                elif message.chat.id in db:
                    self.transaction.set_tag('ASN', db[message.chat.id])
            else:
                if message.chat.title:
                    self.transaction.set_tag('title', message.chat.title)

    def post_process(self, message, data, exception):
        if exception:
            bot.send_message(
                message.chat.id,
                f'Error encountered! Please contact {config.CONTACT}\n遇到错误！请联系 {config.CONTACT}',
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardRemove(),
            )
        try:
            if self.transaction:
                if exception:
                    self.transaction.set_status('error')
                else:
                    self.transaction.set_status('ok')
                self.transaction.finish()
        except BaseException:
            pass


# Startup and initialization
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

config.CONTACT = re.sub(f'([{re.escape(r"_*`[")}])', r'\\\1', config.CONTACT)

if config.SENTRY_DSN:
    sentry_sdk.init(
        dsn=config.SENTRY_DSN,
        traces_sample_rate=0,
    )

tools.update_china_ip()
tools.update_as_route_table()
tools.servers_check(startup=True)
try:
    with open('./map.pkl', 'rb') as f:
        tools.get_map(update=pickle.load(f))
except BaseException:
    tools.get_map(update=True)


# Setup scheduler
scheduler = BackgroundScheduler(
    timezone=utc,
    job_defaults={'misfire_grace_time': None, 'coalesce': True, 'replace_existing': True},
)


def scheduler_add_job(func, *args, **kwargs):
    kwargs['trigger'] = 'cron'
    kwargs['id'] = 'dn42bot_' + func.__name__
    scheduler.add_job(func, *args, **kwargs)


scheduler_add_job(tools.servers_check, minute='*/3')
scheduler_add_job(tools.get_map, kwargs={'update': True}, minute='*/3')
scheduler_add_job(tools.update_china_ip, hour='1', minute='30')
scheduler_add_job(tools.update_as_route_table, minute='7/15')
scheduler.start()


# Setup bot
bot.add_custom_filter(IsPrivateChat())
bot.setup_middleware(MyMiddleware())

cmd_list = {
    'ping': ('Ping IP / Domain', True),
    'tcping': ('TCPing IP / Domain', True),
    'trace': ('Traceroute IP / Domain', True),
    'route': ('Route to IP / Domain', True),
    'path': ('AS-Path of IP / Domain', True),
    'whois': ('Whois', True),
    'dig': ('Dig domain', True),
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
    'block': ('Block an ASN 拉黑一个 ASN', False),
    'unblock': ('Unblock an ASN 取消拉黑一个 ASN', False),
    'blocked': ('Get blocked ASN list 获取已拉黑的 ASN 列表', False),
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

bot.enable_save_next_step_handlers(delay=2, filename='./step.save')
bot.load_next_step_handlers(filename='./step.save')


bot.remove_webhook()

if config.WEBHOOK_URL:
    time.sleep(0.5)
    WEBHOOK_SECRET = tools.gen_random_code(32)
    bot.set_webhook(url=config.WEBHOOK_URL, secret_token=WEBHOOK_SECRET)

    async def handle(request):
        secret = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
        if secret == WEBHOOK_SECRET:
            request_body_dict = await request.json()
            update = telebot.types.Update.de_json(request_body_dict)
            bot.process_new_updates([update])
            return web.Response()
        else:
            return web.Response(status=403)

    async def health(request):
        return web.Response(body=','.join(base.servers.keys()))

    app = web.Application()
    app.router.add_post('/', handle)
    app.router.add_post('/health', health)
    web.run_app(app, host=config.WEBHOOK_LISTEN_HOST, port=config.WEBHOOK_LISTEN_PORT)

else:
    bot.infinity_polling()
