import asyncio
import json
import random
import re
import shlex
import socket
import string
import subprocess
from collections import namedtuple

import config
from aiohttp import ClientSession
from base import db, db_privilege
from IPy import IP
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup


def gen_random_code(length):
    return ''.join(
        random.SystemRandom().choice(string.ascii_uppercase + string.ascii_lowercase + string.digits)
        for _ in range(length)
    )


def get_whoisinfo_by_asn(asn, item='mnt-by'):
    try:
        whois = subprocess.check_output(shlex.split(f'whois -h {config.WHOIS_ADDRESS} AS{asn}'), timeout=3).decode(
            "utf-8"
        )
        for i in whois.split('\n'):
            if i.startswith(f'{item}:'):
                raw_name = i.split(':')[1].strip()
                for w in ['AS', 'DN42', 'MNT']:
                    if raw_name.endswith(f'-{w}'):
                        raw_name = raw_name[: -(len(w) + 1)]
                    if raw_name.startswith(f'{w}-'):
                        raw_name = raw_name[(len(w) + 1) :]
                return raw_name
    except BaseException:
        pass
    return str(asn)


def get_asn_mnt_text(asn):
    if (s := get_whoisinfo_by_asn(asn)) != str(asn):
        return f"{s} AS{asn}"
    else:
        return f"AS{asn}"


def test_ip_domain(testcase):
    testcase = testcase.strip()
    return_tuple = namedtuple('IP_Domain_Info', ['raw', 'ip', 'domain', 'asn', 'mnt', 'dn42'])
    raw = None
    ip = None
    domain = None
    asn = None
    mnt = None
    dn42 = False
    try:  # Test for IPv4
        socket.inet_pton(socket.AF_INET, testcase)
        ip = IP(testcase)
    except socket.error:
        try:  # Test for IPv6
            socket.inet_pton(socket.AF_INET6, testcase)
            ip = IP(testcase)
        except socket.error:
            # Test for Domain
            if match := re.match(r'^(?:(?!-)[A-Za-z0-9-]{1,63}(?<!-)\.)+[A-Za-z0-9]{2,6}$', testcase):
                domain = match.group()
    if ip:
        raw = str(ip)
        try:
            domain = socket.gethostbyaddr(str(ip))[0]
        except BaseException:
            pass
        if str(ip) == domain:
            domain = None
    elif domain:
        raw = domain
        try:
            ip = IP(socket.gethostbyname(domain))
        except BaseException:
            pass
    else:
        return None
    if domain and domain.endswith('.dn42'):
        dn42 = True
    elif ip and (ip in IP('172.20.0.0/14') or ip in IP('fc00::/7')):
        dn42 = True
    if dn42 and ip:
        try:
            whois = subprocess.check_output(
                shlex.split(f'whois -h {config.WHOIS_ADDRESS} -T route,route6 {ip}'), timeout=3
            ).decode("utf-8")
            asn = []
            for i in whois.split('\n'):
                if i.startswith('origin:'):
                    asn.append(i.split(':')[1].strip())
                elif i.startswith('mnt-by:'):
                    mnt = i.split(':')[1].strip()
            asn = ', '.join(asn)
        except BaseException:
            dn42 = False
            asn = None
    return return_tuple(raw, str(ip) if ip else None, domain, asn, mnt, dn42)


def gen_peer_me_markup(message):
    if message.chat.id in db_privilege:
        return None
    if message.chat.type == "private" and message.chat.id in db:
        if get_info(db[message.chat.id]):
            return None
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("Peer with me | 与我 Peer", url=f"https://t.me/{config.BOT_USERNAME}"))
    return markup


def get_from_agent(type, target):
    api_result = namedtuple('api_result', ['text', 'status'])

    async def async_test():
        async def run(region):
            try:
                async with ClientSession() as session:
                    async with session.post(
                        f"http://{region}.{config.ENDPOINT}:{config.API_PORT}/{type}",
                        data=target,
                        headers={"X-DN42-Bot-Api-Secret-Token": config.API_TOKEN},
                        timeout=10,
                    ) as r:
                        data = await r.text()
                        return (region, api_result(data, r.status))
            except BaseException:
                return (region, api_result("", 500))

        task_list = [asyncio.create_task(run(region)) for region in config.SERVER.keys()]
        done, _ = await asyncio.wait(task_list)
        return done

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    raw = loop.run_until_complete(async_test())
    data = {i.result()[0]: i.result()[1] for i in raw}
    data = {i: data[i] for i in config.SERVER}

    return data


def get_info(asn):
    data = {}
    for k, v in get_from_agent("info", str(asn)).items():
        if v.status == 200:
            try:
                data[k] = json.loads(v.text)
            except BaseException:
                data[k] = 'Error'
        elif v.status == 500:
            data[k] = v.text
    return data
