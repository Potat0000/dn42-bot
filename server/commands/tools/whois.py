import shlex
import string
import subprocess

import base
import config
import tools
from base import bot
from commands.statistics.stats import get_stats
from IPy import IP


def get_extra_route(asn):
    route_result = ''
    route4, route6 = [], []
    for route in base.AS_ROUTE[asn]:
        if (ip := IP(route)).version() == 4:
            route4.append((ip.int(), route))
        else:
            route6.append((ip.int(), route))
    for _, route in sorted(route4, key=lambda x: x[0]):
        route_result += f'route4:             {route}\n'
    for _, route in sorted(route6, key=lambda x: x[0]):
        route_result += f'route6:             {route}\n'
    if route_result:
        return f"% Routes for 'AS{asn}':\n{route_result.strip()}"


@bot.message_handler(commands=['whois'])
def whois(message):
    if len(message.text.split()) < 2:
        bot.reply_to(
            message,
            'Usage: /whois [something]\n用法：/whois [something]',
            reply_markup=tools.gen_peer_me_markup(message),
        )
        return
    whois_str = message.text.split()[1]
    allowed_punctuation = '_-./:'
    if any(c not in (string.ascii_letters + string.digits + allowed_punctuation) for c in whois_str):
        bot.reply_to(
            message,
            (
                'Invalid input.\n'
                '输入无效\n'
                '\n'
                'Only non-empty strings which contain only upper and lower case letters, numbers, spaces and the following special symbols are accepted.\n'
                '只接受仅由大小写英文字母、数字、空格及以下特殊符号组成的非空字符串。\n'
                f'`{allowed_punctuation}`\n'
            ),
            parse_mode='Markdown',
            reply_markup=tools.gen_peer_me_markup(message),
        )
        return
    bot.send_chat_action(chat_id=message.chat.id, action='typing')
    whois_command = f'whois -h {config.WHOIS_ADDRESS} {whois_str}'
    while True:
        try:
            whois_result = (
                subprocess.run(
                    shlex.split(whois_command),
                    stdout=subprocess.PIPE,
                    timeout=3,
                )
                .stdout.decode('utf-8')
                .strip()
            )
        except subprocess.TimeoutExpired:
            whois_result = 'Request timeout.\n请求超时。'
            break
        except BaseException:
            whois_result = 'Something went wrong.\n发生了一些错误。'
            break
        if len(whois_result.splitlines()) > 1 and '% 404' not in whois_result:
            break
        try:
            asn = int(whois_str)
            if asn < 10000:
                whois_str = f'AS424242{asn:04d}'
            elif 20000 <= asn < 30000:
                whois_str = f'AS42424{asn}'
            else:
                whois_str = f'AS{asn}'
            whois_command = f'whois -h {config.WHOIS_ADDRESS} {whois_str}'
        except ValueError:
            whois_command = f'whois -I {message.text.split()[1]}'
        whois_result = ''
    try:
        asn = int(whois_str[2:])
        if route_result := get_extra_route(asn):
            whois_result += f'\n\n{route_result}'
        if stats_result := get_stats(asn)[1]:
            whois_result += (
                '\n\n'
                f"% Statistics for 'AS{asn}':\n"
                f'centrality:         {stats_result["centrality"]}\n'
                f'closeness:          {stats_result["closeness"]}\n'
                f'betweenness:        {stats_result["betweenness"]}\n'
                f'peer count:         {stats_result["peer"]}'
            )
    except BaseException:
        pass
    if len(whois_result) > 4000:
        whois_result = tools.split_long_msg(whois_result)
        last_msg = message
        for index, m in enumerate(whois_result):
            if index < len(whois_result) - 1:
                last_msg = bot.reply_to(
                    last_msg,
                    f'```WhoisResult\n{m}```To be continued...',
                    parse_mode='Markdown',
                    reply_markup=tools.gen_peer_me_markup(message),
                )
            else:
                bot.reply_to(
                    last_msg,
                    f'```WhoisResult\n{m}```',
                    parse_mode='Markdown',
                    reply_markup=tools.gen_peer_me_markup(message),
                )
    else:
        bot.reply_to(
            message,
            f'```WhoisResult\n{whois_result}```',
            parse_mode='Markdown',
            reply_markup=tools.gen_peer_me_markup(message),
        )
