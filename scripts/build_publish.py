#!/usr/bin/env python3
"""build_publish.py - 读取 clash-speedtest 筛选后的节点，重建带国家分组的最终订阅配置。"""
import argparse
import re

import yaml

REGIONS = [
    ("HK", "\U0001F1ED\U0001F1F0 \u9999\u6E2F", r"(?i)\u9999\u6E2F|HK|Hong ?Kong|\U0001F1ED\U0001F1F0"),
    ("TW", "\U0001F1F9\U0001F1FC \u53F0\u6E7E", r"(?i)\u53F0\u6E7E|TW|Taiwan|\U0001F1F9\U0001F1FC"),
    ("SG", "\U0001F1F8\U0001F1EC \u65B0\u52A0\u5761", r"(?i)\u65B0\u52A0\u5761|\u72EE\u57CE|SG|Singapore|\U0001F1F8\U0001F1EC"),
    ("JP", "\U0001F1EF\U0001F1F5 \u65E5\u672C", r"(?i)\u65E5\u672C|JP|Japan|\U0001F1EF\U0001F1F5"),
    ("KR", "\U0001F1F0\U0001F1F7 \u97E9\u56FD", r"(?i)\u97E9\u56FD|KR|Korea|\U0001F1F0\U0001F1F7"),
    ("US", "\U0001F1FA\U0001F1F8 \u7F8E\u56FD", r"(?i)\u7F8E\u56FD|US|United States|\U0001F1FA\U0001F1F8"),
    ("GB", "\U0001F1EC\U0001F1E7 \u82F1\u56FD", r"(?i)\u82F1\u56FD|UK|GB|\U0001F1EC\U0001F1E7"),
    ("DE", "\U0001F1E9\U0001F1EA \u5FB7\u56FD", r"(?i)\u5FB7\u56FD|DE|Germany|\U0001F1E9\U0001F1EA"),
    ("FR", "\U0001F1EB\U0001F1F7 \u6CD5\u56FD", r"(?i)\u6CD5\u56FD|FR|France|\U0001F1EB\U0001F1F7"),
    ("CA", "\U0001F1E8\U0001F1E6 \u52A0\u62FF\u5927", r"(?i)\u52A0\u62FF\u5927|CA|Canada|\U0001F1E8\U0001F1E6"),
    ("AU", "\U0001F1E6\U0001F1FA \u6FB3\u6D32", r"(?i)\u6FB3\u6D32|\u6FB3\u6D32|AU|Australia|\U0001F1E6\U0001F1FA"),
    ("TR", "\U0001F1F9\U0001F1F7 \u571F\u8033\u5176", r"(?i)\u571F\u8033\u5176|TR|Turkey|\U0001F1F9\U0001F1F7"),
    ("RU", "\U0001F1F7\U0001F1FA \u4FC4\u7F57\u65AF", r"(?i)\u4FC4\u7F57\u65AF|RU|Russia|\U0001F1F7\U0001F1FA"),
    ("IN", "\U0001F1EE\U0001F1F3 \u5370\u5EA6", r"(?i)\u5370\u5EA6|IN|India|\U0001F1EE\U0001F1F3"),
    ("BR", "\U0001F1E7\U0001F1F7 \u5DF4\u897F", r"(?i)\u5DF4\u897F|BR|Brazil|\U0001F1E7\U0001F1F7"),
    ("AR", "\U0001F1E6\U0001F1F7 \u963F\u6839\u5EF7", r"(?i)\u963F\u6839\u5EF7|AR|Argentina|\U0001F1E6\U0001F1F7"),
]


def build(proxies):
    names = [p["name"] for p in proxies]
    region_members, used = {}, set()
    for code, gname, pat in REGIONS:
        rx = re.compile(pat)
        members = [n for n in names if rx.search(n)]
        if members:
            region_members[gname] = members
            used.update(members)
    others = [n for n in names if n not in used]

    groups = []
    for code, gname, pat in REGIONS:
        if gname in region_members:
            groups.append({"name": gname, "type": "url-test", "proxies": region_members[gname],
                           "url": "http://www.gstatic.com/generate_204", "interval": 300, "tolerance": 80})
    if others:
        groups.append({"name": "\U0001F30D \u5176\u4ED6\u5730\u533A", "type": "url-test", "proxies": others,
                       "url": "http://www.gstatic.com/generate_204", "interval": 300, "tolerance": 80})
    if len(names) > 1:
        groups.append({"name": "\u2696\uFE0F \u5168\u90E8\u5747\u8861", "type": "load-balance", "proxies": names,
                       "strategy": "round-robin", "url": "http://www.gstatic.com/generate_204", "interval": 300})
        groups.append({"name": "\u267B\uFE0F \u81EA\u52A8\u9009\u62E9", "type": "url-test", "proxies": names,
                       "url": "http://www.gstatic.com/generate_204", "interval": 300, "tolerance": 80})
        groups.append({"name": "\u2708\uFE0F \u6545\u969C\u8F6C\u79FB", "type": "fallback", "proxies": names,
                       "url": "http://www.gstatic.com/generate_204", "interval": 300})

    entry = {"name": "\U0001F680 \u8282\u70B9\u9009\u62E9", "type": "select",
             "proxies": [g["name"] for g in groups] + ["DIRECT"]}

    cfg = {
        "mixed-port": 7890,
        "allow-lan": True,
        "mode": "rule",
        "log-level": "info",
        "unified-delay": True,
        "tcp-concurrent": True,
        "dns": {
            "enable": True,
            "enhanced-mode": "fake-ip",
            "fake-ip-range": "198.18.0.1/16",
            "nameserver": ["https://doh.pub/dns-query", "https://dns.alidns.com/dns-query"],
            "fallback": ["https://dns.cloudflare.com/dns-query", "https://dns.google/dns-query"],
            "fake-ip-filter": ["*.lan", "*.local", "+.msftconnecttest.com", "+.msftncsi.com"],
        },
        "proxies": proxies,
        "proxy-groups": [entry] + groups,
        "rules": [
            "DOMAIN-SUFFIX,local,DIRECT",
            "IP-CIDR,127.0.0.0/8,DIRECT,no-resolve",
            "IP-CIDR,10.0.0.0/8,DIRECT,no-resolve",
            "IP-CIDR,172.16.0.0/12,DIRECT,no-resolve",
            "IP-CIDR,192.168.0.0/16,DIRECT,no-resolve",
            "IP-CIDR,100.64.0.0/10,DIRECT,no-resolve",
            "GEOIP,CN,DIRECT",
            "MATCH,\U0001F680 \u8282\u70B9\u9009\u62E9",
        ],
    }
    return cfg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="tested.yaml")
    ap.add_argument("--out", default="output/clash.yaml")
    args = ap.parse_args()

    with open(args.inp, encoding="utf-8") as f:
        d = yaml.safe_load(f) or {}
    proxies = [p for p in (d.get("proxies") or []) if p.get("server")]
    if not proxies:
        print("no proxies after speed test, keep previous output")
        raise SystemExit(2)

    cfg = build(proxies)
    import os
    os.makedirs("output", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False, width=300)

    regions = {}
    for g in cfg["proxy-groups"]:
        if g["type"] == "url-test" and g["name"] != "\U0001F30D \u5176\u4ED6\u5730\u533A":
            regions[g["name"]] = len(g["proxies"])
    print("published:", args.out, "| total:", len(proxies), "| regions:", regions)


if __name__ == "__main__":
    main()
