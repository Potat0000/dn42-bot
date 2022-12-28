#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pickle
import time

import config
import sentry_sdk
import telebot
import tools
from aiohttp import web
from base import bot

import commands

MIN_AGENT_VERSION = 6

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
        traces_sample_rate=1.0,
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
