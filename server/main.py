#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time

import config
from base import bot
import telebot
import tools
from aiohttp import web

import modules

tools.get_stats(update=True)
stats_timer = tools.LoopTimer(900, tools.get_stats, "Update Stats Timer", update=True)
stats_timer.start()


WEBHOOK_SECRET = tools.gen_random_code(32)

bot.remove_webhook()
time.sleep(0.5)
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
