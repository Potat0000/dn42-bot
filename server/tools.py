import asyncio
import json
import math
import random
import re
import shlex
import socket
import string
import subprocess
from collections import namedtuple
from time import time

import config
from aiohttp import ClientSession
from IPy import IP


def gen_random_code(length):
    return ''.join(
        random.SystemRandom().choice(string.ascii_uppercase + string.ascii_lowercase + string.digits)
        for _ in range(length)
    )


# https://stackoverflow.com/a/14822210
def convert_size(size_bytes):
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, size_name[i])


# https://stackoverflow.com/a/13756038
def td_format(td_object):
    seconds = int(td_object.total_seconds())
    if seconds <= 0:
        return 'now'
    periods = [
        # ('year', 60 * 60 * 24 * 365),
        # ('month', 60 * 60 * 24 * 30),
        ('day', 60 * 60 * 24),
        ('hour', 60 * 60),
        ('minute', 60),
        ('second', 1),
    ]
    strings = []
    for period_name, period_seconds in periods:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            has_s = 's' if period_value > 1 else ''
            strings.append("%s %s%s" % (period_value, period_name, has_s))
    return ", ".join(strings) + " ago"


def get_mnt_by_asn(asn):
    try:
        whois = subprocess.check_output(shlex.split(f'whois -h 127.0.0.1 AS{asn}'), timeout=3).decode("utf-8")
        for i in whois.split('\n'):
            if i.startswith('as-name:'):
                raw_name = i.split(':')[1].strip()
                if raw_name.endswith('-AS'):
                    raw_name = raw_name[:-3]
                if raw_name.endswith('-DN42'):
                    raw_name = raw_name[:-5]
                if raw_name.startswith('DN42-'):
                    raw_name = raw_name[5:]
                if raw_name.startswith('AS-'):
                    raw_name = raw_name[3:]
                return raw_name
    except BaseException:
        pass
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
            whois = subprocess.check_output(shlex.split(f'whois -h 127.0.0.1 -T route,route6 {ip}'), timeout=3).decode(
                "utf-8"
            )
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
    try:  # Test for IPv4
        socket.inet_pton(socket.AF_INET, address)
        if any(IP(address) in i for i in IPv4_Bogon):
            return None
        else:
            return str(IP(address))
    except socket.error:
        try:  # Test for IPv6
            socket.inet_pton(socket.AF_INET6, address)
            if any(IP(address) in i for i in IPv6_Bogon):
                return None
            else:
                return str(IP(address))
        except socket.error:
            if not re.search('[a-zA-Z]', address):
                return None
            try:  # Test for domain
                if test_clearnet(socket.gethostbyname(address)) is not None:
                    return address
            except socket.error:
                return None


def get_email(asn):
    try:
        whois1 = (
            subprocess.check_output(shlex.split(f"whois -h 127.0.0.1 AS{asn}"), timeout=3)
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
            subprocess.check_output(shlex.split(f"whois -h 127.0.0.1 {admin_c}"), timeout=3)
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


def get_all(type, target):
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

    return data


def get_info(asn):
    data = {}
    for k, v in get_all("info", str(asn)).items():
        if v.status == 200:
            try:
                data[k] = json.loads(v.text)
            except BaseException:
                data[k] = 'Error'
        elif v.status == 500:
            data[k] = v.text
    return data


def gen_get_stats():
    update_time = 0
    data = {}

    def inner(*, update=False):
        nonlocal data, update_time
        temp = {}
        if update:
            raw = get_all("stats", "")
            for node, raw_data in raw.items():
                if raw_data.status != 200:
                    temp[node] = raw_data.text
                    continue
                try:
                    json_data = json.loads(raw_data.text)
                except json.JSONDecodeError:
                    temp[node] = raw_data.text
                else:
                    temp[node] = {}
                    for ip_ver in ['4', '6']:
                        s = [(k, get_mnt_by_asn(k), v) for k, v in json_data[ip_ver].items()]
                        s.sort(key=lambda x: (-x[2], x[0]))
                        temp[node][ip_ver] = s
            data, update_time = temp, int(time())
        else:
            return data, update_time

    return inner
