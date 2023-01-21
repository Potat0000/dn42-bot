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
import dns.resolver as dns
from aiohttp import ClientSession
from base import db, db_privilege
from dns.exception import DNSException
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


def test_clearnet(address):
    IPv4_Bogon = [
        IP('0.0.0.0/8'),
        IP('10.0.0.0/8'),
        IP('100.64.0.0/10'),
        IP('127.0.0.0/8'),
        IP('127.0.53.53'),
        IP('169.254.0.0/16'),
        IP('172.16.0.0/12'),
        IP('192.0.0.0/24'),
        IP('192.0.2.0/24'),
        IP('192.168.0.0/16'),
        IP('198.18.0.0/15'),
        IP('198.51.100.0/24'),
        IP('203.0.113.0/24'),
        IP('224.0.0.0/4'),
        IP('240.0.0.0/4'),
        IP('255.255.255.255/32'),
    ]
    IPv6_Bogon = [
        IP('::/128'),
        IP('::1/128'),
        IP('::ffff:0:0/96'),
        IP('::/96'),
        IP('100::/64'),
        IP('2001:10::/28'),
        IP('2001:db8::/32'),
        IP('fc00::/7'),
        IP('fe80::/10'),
        IP('fec0::/10'),
        IP('ff00::/8'),
        IP('2002::/24'),
        IP('2002:a00::/24'),
        IP('2002:7f00::/24'),
        IP('2002:a9fe::/32'),
        IP('2002:ac10::/28'),
        IP('2002:c000::/40'),
        IP('2002:c000:200::/40'),
        IP('2002:c0a8::/32'),
        IP('2002:c612::/31'),
        IP('2002:c633:6400::/40'),
        IP('2002:cb00:7100::/40'),
        IP('2002:e000::/20'),
        IP('2002:f000::/20'),
        IP('2002:ffff:ffff::/48'),
        IP('2001::/40'),
        IP('2001:0:a00::/40'),
        IP('2001:0:7f00::/40'),
        IP('2001:0:a9fe::/48'),
        IP('2001:0:ac10::/44'),
        IP('2001:0:c000::/56'),
        IP('2001:0:c000:200::/56'),
        IP('2001:0:c0a8::/48'),
        IP('2001:0:c612::/47'),
        IP('2001:0:c633:6400::/56'),
        IP('2001:0:cb00:7100::/56'),
        IP('2001:0:e000::/36'),
        IP('2001:0:f000::/36'),
        IP('2001:0:ffff:ffff::/64'),
    ]
    test_result = namedtuple('test_result', ['raw', 'ip', 'domain', 'ipver'])
    try:  # Test for IPv4
        socket.inet_pton(socket.AF_INET, address)
        if any(IP(address) in i for i in IPv4_Bogon):
            return None
        else:
            domain = None
            try:
                domain = socket.gethostbyaddr(str(IP(address)))[0]
            except BaseException:
                pass
            if str(IP(address)) == domain:
                domain = None
            return test_result(str(IP(address)), str(IP(address)), domain, 'ipv4')
    except socket.error:
        try:  # Test for IPv6
            socket.inet_pton(socket.AF_INET6, address)
            if any(IP(address) in i for i in IPv6_Bogon):
                return None
            else:
                domain = None
                try:
                    domain = socket.gethostbyaddr(str(IP(address)))[0]
                except BaseException:
                    pass
                if str(IP(address)) == domain:
                    domain = None
                return test_result(str(IP(address)), str(IP(address)), domain, 'ipv6')
        except socket.error:  # Test for domain
            if not re.search('[a-zA-Z]', address):
                return None
            support = None
            try:
                for i in dns.resolve(address, 'A'):
                    if test_clearnet(i.address):
                        ip = i.address
                        support = 'ipv4'
                        break
            except DNSException:
                pass
            try:
                for i in dns.resolve(address, 'AAAA'):
                    if test_clearnet(i.address):
                        ip = i.address
                        if support:
                            support = 'dual'
                        else:
                            support = 'ipv6'
                        break
            except DNSException:
                pass
            if support:
                return test_result(address, ip, address, support)
            else:
                return None


def test_ip_domain(testcase):
    testcase = testcase.strip()
    return_tuple = namedtuple('IP_Domain_Info', ['raw', 'ip', 'domain', 'asn', 'mnt', 'dn42'])
    asn = None
    mnt = None
    dn42 = False
    test_result = test_clearnet(testcase)
    if not test_result:
        return None
    raw = test_result.raw
    ip = test_result.ip
    domain = test_result.domain

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
