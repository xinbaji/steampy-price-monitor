# -*- coding: utf-8 -*-
"""SteamPY 买家价格监控 - 核心逻辑模块

职责分离：
- 本模块只做纯逻辑：URL 解析、API 请求、买家过滤
- 不负责邮件发送与轮询调度（见 monitor.py）
- 不包含任何敏感信息（敏感信息在 config.json）
"""
import json
import os
import re
import ssl
import time
import urllib.parse
import urllib.request
import urllib.error

# 系统代理 127.0.0.1:7897 常是死代理，脚本默认直连
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
           "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_k, None)

BASE = "https://steampy.com/xboot"
REGION_MAP = {
    "cn": "/steamKeySale/listSale",
    "ru": "/ruKeySale/listSale",
    "us": "/usKeySale/listSale",
    "tl": "/tlKeySale/listSale",
}

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def build_headers(cookie: str, access_token: str = "") -> dict:
    """构造请求头（Cookie + accessToken 请求头）

    steampy 认证机制：token 存浏览器 localStorage 的 accessToken，
    通过自定义请求头 `accessToken` 发送，请求体为 form-urlencoded。
    Cookie 主要携带 userInfo 资料，仍需一并带上。
    """
    h = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/126.0.0.0 Safari/537.36"),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Origin": "https://steampy.com",
        "Referer": "https://steampy.com/pro/",
        "Cookie": cookie,
    }
    if access_token:
        h["accessToken"] = access_token
    return h


def parse_game_url(url: str) -> dict:
    """从 cdkDetail 链接解析 gameId 与区域 name

    示例：
      https://steampy.com/pro/cdKey/cdkDetail?name=cn&gameId=9001034537870446481409
    -> {"game_id": "9001034537870446481409", "region": "cn"}
    """
    q = url.split("?", 1)[1] if "?" in url else ""
    params = {}
    for part in q.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k] = v
    game_id = params.get("gameId", "")
    region = params.get("name", "cn")
    if region not in REGION_MAP:
        raise ValueError(f"未知区域 name={region!r}，支持 cn/ru/us/tl")
    if not game_id:
        raise ValueError("链接中缺少 gameId 参数")
    return {"game_id": game_id, "region": region}


def fetch_buyers(cookie: str, game_id: str, region: str = "cn",
                 page_number: int = 1, page_size: int = 20,
                 timeout: int = 20, access_token: str = "") -> list:
    """请求一页买家列表，返回 content 数组

    接口：GET {BASE}/{region}/listSale（前端 getRequest，参数走 query）
    返回 result.content[]：含 steamName/stock/keyPrice/discount 等字段
    401 -> 抛 AuthError（登录态失效）
    """
    path = REGION_MAP[region]
    query = "&".join(
        f"{k}={urllib.parse.quote(str(v))}" for k, v in {
            "pageNumber": page_number,
            "pageSize": page_size,
            "sort": "keyPrice",
            "order": "asc",
            "startDate": "",
            "endDate": "",
            "gameId": game_id,
        }.items()
    )
    req = urllib.request.Request(
        f"{BASE}{path}?{query}",
        headers=build_headers(cookie, access_token),
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
            raw = resp.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.reason}") from e
    except Exception as e:
        raise RuntimeError(f"网络请求失败: {e}") from e

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"响应不是合法 JSON: {raw[:200]}") from e

    if not data.get("success"):
        code = data.get("code")
        msg = data.get("message", "")
        if code == 401:
            raise AuthError(msg or "Cookie 失效，请重新登录 steampy 并更新 config.json")
        raise RuntimeError(f"接口返回失败 code={code} msg={msg}")

    result = data.get("result") or {}
    content = result.get("content") or []
    return content


def normalize_buyer(row: dict) -> dict:
    """把接口原始行规整为可用字段；单价统一为 float（元）"""
    try:
        price = float(row.get("keyPrice"))
    except (TypeError, ValueError):
        price = float("inf")
    return {
        "steam_name": (row.get("steamName") or "").strip(),
        "stock": int(row.get("stock") or 0),
        "key_price": price,
        "discount": row.get("discount"),
    }


def find_cheap_buyers(buyers: list, max_price: float,
                      min_stock: int = 1) -> list:
    """过滤出单价 <= max_price 且库存 >= min_stock 的买家，按单价升序"""
    out = []
    for row in buyers:
        b = normalize_buyer(row)
        if b["key_price"] <= max_price and b["stock"] >= min_stock:
            out.append(b)
    out.sort(key=lambda x: x["key_price"])
    return out


class AuthError(Exception):
    """登录态失效"""
