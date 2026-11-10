#!/usr/bin/env python3
"""fetch_merge.py — 抓取多源公开节点 -> 解析为 Clash 代理字典 -> 去重 -> 输出待测池 pool.yaml
数据源失效时自动跳过，不阻塞整条流水线。"""
import argparse
import base64
import json
import re
import sys
import urllib.request
import ssl
from urllib.parse import urlparse, parse_qs, unquote

import yaml

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# 数据源：clash yaml 源 + 分享链接源，可自行增删
YAML_SOURCES = [
    "https://raw.githubusercontent.com/anaer/Sub/main/clash.yaml",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/sub_merge_yaml.yml",
]
LINK_SOURCES = [
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list_raw.txt",
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/sub_merge.txt",  # base64
]

UA = "mihomo/1.19.0"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    data = urllib.request.urlopen(req, context=ctx, timeout=30).read()
    return data.decode("utf-8", errors="replace")


def load_yaml_proxies(url: str) -> list:
    text = fetch(url)
    d = yaml.safe_load(text) or {}
    proxies = d.get("proxies") or []
    return [p for p in proxies if isinstance(p, dict) and p.get("server") and p.get("type")]


# ---------- 分享链接解析 ----------

def b64d(s: str) -> bytes:
    return base64.b64decode(s + "=" * (-len(s) % 4))


def parse_vmess(link: str) -> dict | None:
    try:
        raw = link.split("://", 1)[1].split("#", 1)[0]
        j = json.loads(b64d(raw).decode("utf-8", "replace"))
        p = {
            "name": j.get("ps") or f"vmess-{j.get('add')}",
            "type": "vmess",
            "server": str(j.get("add")),
            "port": int(j.get("port")),
            "uuid": j.get("id"),
            "alterId": int(j.get("aid") or 0),
            "cipher": j.get("scy") or "auto",
            "udp": True,
        }
        net = j.get("net") or "tcp"
        if net == "ws":
            p["ws-opts"] = {"path": j.get("path") or "/", "headers": {"Host": j.get("host")} if j.get("host") else {}}
        elif net == "grpc":
            p["grpc-opts"] = {"grpc-service-name": j.get("path") or ""}
        if str(j.get("tls")).lower() in ("tls", "true", "1"):
            p["tls"] = True
            if j.get("sni"):
                p["servername"] = j["sni"]
        return p
    except Exception:
        return None


def _uri_proxy(link: str, ptype: str) -> dict | None:
    try:
        body = link.split("://", 1)[1]
        frag = ""
        if "#" in body:
            body, frag = body.split("#", 1)
        name = unquote(frag) or f"{ptype}-node"
        userinfo, hostport = body.rsplit("@", 1) if "@" in body else (body, "")
        q = {}
        if "?" in hostport:
            hostport, qs = hostport.split("?", 1)
            q = parse_qs(qs)
        host, port = hostport.rsplit(":", 1)
        port = int(port)
        p = {"name": name, "type": ptype, "server": host, "port": port, "udp": True}
        if ptype == "ss":
            # 两种格式：base64(method:pass)@host:port 或整段 base64
            try:
                cred = b64d(userinfo + "=" * (-len(userinfo) % 4)).decode("utf-8", "replace")
                method, password = cred.split(":", 1)
            except Exception:
                method, password = unquote(userinfo).split(":", 1)
            p["cipher"], p["password"] = method, password
        elif ptype == "vmess":  # 不走这分支，vmess 单独处理
            return None
        elif ptype in ("trojan", "vless"):
            p["password" if ptype == "trojan" else "uuid"] = unquote(userinfo)
            sni = (q.get("sni") or q.get("peer") or [None])[0]
            if sni:
                p["sni"] = sni
            security = (q.get("security") or [None])[0]
            if security in ("tls", "reality") and ptype == "vless":
                p["tls"] = True
                if security == "reality":
                    p["reality-opts"] = {"public-key": (q.get("pbk") or [""])[0]}
                fp = (q.get("fp") or [None])[0]
                if fp:
                    p["client-fingerprint"] = fp
            nettype = (q.get("type") or ["tcp"])[0]
            if nettype == "ws":
                p["ws-opts"] = {"path": (q.get("path") or ["/"])[0]}
            elif nettype == "grpc":
                p["grpc-opts"] = {"grpc-service-name": (q.get("serviceName") or [""])[0]}
        elif ptype == "hysteria2":
            p["password"] = unquote(userinfo)
            sni = (q.get("sni") or [None])[0]
            if sni:
                p["sni"] = sni
            if (q.get("insecure") or ["0"])[0] in ("1", "true"):
                p["skip-cert-verify"] = True
            obfs = (q.get("obfs") or [None])[0]
            if obfs:
                p["obfs"] = obfs
                p["obfs-password"] = (q.get("obfs-password") or [""])[0]
        return p
    except Exception:
        return None


def parse_links(text: str) -> list:
    out = []
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    # 整个文件可能是 base64 订阅
    joined = "\n".join(lines)
    if not any("://" in l for l in lines[:5]) and len(lines) == 1:
        try:
            joined = b64d(joined).decode("utf-8", "replace")
            lines = [l.strip() for l in joined.splitlines() if l.strip()]
        except Exception:
            pass
    for l in lines:
        if l.startswith("vmess://"):
            p = parse_vmess(l)
        elif l.startswith("ss://"):
            p = _uri_proxy(l, "ss")
        elif l.startswith("vless://"):
            p = _uri_proxy(l, "vless")
        elif l.startswith("trojan://"):
            p = _uri_proxy(l, "trojan")
        elif l.startswith(("hysteria2://", "hy2://")):
            p = _uri_proxy(l, "hysteria2")
        else:
            p = None
        if p and p.get("server") and p.get("port"):
            out.append(p)
    return out


# ---------- 去重 ----------

def dedupe_key(p: dict):
    ident = p.get("uuid") or p.get("password") or p.get("cipher", "")
    return (p.get("type"), p.get("server"), p.get("port"), ident)


def dedupe(proxies: list) -> list:
    seen, out = set(), []
    for p in proxies:
        try:
            k = dedupe_key(p)
        except Exception:
            continue
        if k in seen:
            continue
        seen.add(k)
        out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="pool.yaml")
    ap.add_argument("--sample", type=int, default=250,
                    help="每轮随机抽测的节点数（0=全量）。免费节点寿命短，轮转抽样即可覆盖")
    args = ap.parse_args()

    proxies, src_stat = [], {}
    for u in YAML_SOURCES:
        try:
            got = load_yaml_proxies(u)
            proxies += got
            src_stat[u.rsplit("/", 1)[-1]] = len(got)
        except Exception as e:
            src_stat[u.rsplit("/", 1)[-1]] = f"FAIL {str(e)[:40]}"
    for u in LINK_SOURCES:
        try:
            got = parse_links(fetch(u))
            proxies += got
            src_stat[u.rsplit("/", 1)[-1]] = len(got)
        except Exception as e:
            src_stat[u.rsplit("/", 1)[-1]] = f"FAIL {str(e)[:40]}"

    proxies = dedupe(proxies)
    if args.sample and len(proxies) > args.sample:
        import random
        proxies = random.sample(proxies, args.sample)
    # 规范名字，避免重名
    counts = {}
    for p in proxies:
        n = re.sub(r"[\r\n|#]", " ", str(p.get("name") or "node")).strip() or "node"
        counts[n] = counts.get(n, 0) + 1
        if counts[n] > 1:
            n = f"{n} #{counts[n]}"
        p["name"] = n

    cfg = {
        "mixed-port": 7890,
        "mode": "rule",
        "log-level": "warning",
        "proxies": proxies,
        "proxy-groups": [{"name": "POOL", "type": "select", "proxies": [p["name"] for p in proxies]}],
        "rules": ["MATCH,POOL"],
    }
    with open(args.out, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False, width=200)
    print("sources:", src_stat)
    print("total after dedupe:", len(proxies))


if __name__ == "__main__":
    sys.exit(main())
