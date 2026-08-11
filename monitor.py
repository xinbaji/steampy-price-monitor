# -*- coding: utf-8 -*-
"""SteamPY 游戏价格监控主程序

用法：
  python get_session.py            # 第一次：Playwright 打开浏览器登录，自动抓取凭证
  python monitor.py                # 读取 config.json + session.json 开始轮询（默认）
  python monitor.py --once         # 只检查一次，不进入轮询（用于测试/定时任务）
  python monitor.py --config xxx.json

行为：
  每 poll_interval_seconds 秒轮询一次买家列表；
  存在单价 <= max_price 的买家 -> 发送邮件提醒，然后退出（只提醒一次）；
  登录凭证失效时打印提示并退出（重跑 get_session.py 重新登录）。
"""
import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime

from steampy_core import (AuthError, find_cheap_buyers, fetch_buyers,
                          parse_game_url)
from email_sender import send_email

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(BASE_DIR, "config.json")
DEFAULT_SESSION = os.path.join(BASE_DIR, "session.json")


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg


def load_session(path: str = DEFAULT_SESSION) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        s = json.load(f)
    return s


def validate_config(cfg: dict) -> None:
    sp = cfg.get("steampy", {})
    em = cfg.get("email", {})
    if not sp.get("game_url"):
        raise ValueError("config.json 中 steampy.game_url 为空！")
    if not em.get("sender") or not em.get("auth_code") or not em.get("receiver"):
        raise ValueError("config.json 中 email 配置不完整"
                         "（sender/auth_code/receiver 必填）")


def build_alert_body(game_id: str, region: str, max_price: float,
                     cheap: list) -> str:
    lines = [
        "SteamPY 价格监控提醒",
        "=" * 40,
        f"监控时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"游戏链接: https://steampy.com/pro/cdKey/cdkDetail"
        f"?name={region}&gameId={game_id}",
        f"目标价格: 单价 <= {max_price} 元",
        f"符合买家数: {len(cheap)}",
        "",
        "符合条件买家列表（按单价升序）:",
        "-" * 40,
    ]
    for b in cheap:
        lines.append(
            f"  单价 ￥{b['key_price']:.2f} | 库存 {b['stock']} | {b['steam_name']}"
        )
    lines += ["", "请尽快前往链接购买。"]
    return "\n".join(lines)


def run_once(cfg: dict, session: dict) -> bool:
    """执行一次检查；命中并发信返回 True，否则 False"""
    sp = cfg["steampy"]
    game = parse_game_url(sp["game_url"])
    cookie = session.get("cookie_header", "")
    access_token = session.get("access_token", "")
    game_id, region = game["game_id"], game["region"]
    max_price = float(sp["max_price"])

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 查询 {game_id} "
          f"({region}) 最低价买家 ...", flush=True)

    buyers = fetch_buyers(cookie, game_id, region, page_number=1,
                          page_size=50, access_token=access_token)
    cheap = find_cheap_buyers(buyers, max_price)

    if not cheap:
        top = None
        for b in map(lambda r: {
            "key_price": float(r["keyPrice"]) if str(r.get("keyPrice", "")).replace(".", "").isdigit() else float("inf"),
            "stock": int(r.get("stock") or 0),
            "steam_name": (r.get("steamName") or "").strip(),
        }, buyers):
            if top is None or b["key_price"] < top["key_price"]:
                top = b
        lowest = f"￥{top['key_price']:.2f}" if top and top['key_price'] != float("inf") else "N/A"
        print(f"  暂未命中。当前最低单价约 {lowest}（阈值 ￥{max_price:.2f}）",
              flush=True)
        return False

    body = build_alert_body(game_id, region, max_price, cheap)
    print(body, flush=True)
    send_email(
        smtp_host=cfg["email"]["smtp_host"],
        smtp_port=cfg["email"]["smtp_port"],
        sender=cfg["email"]["sender"],
        auth_code=cfg["email"]["auth_code"],
        receiver=cfg["email"]["receiver"],
        subject=f"[SteamPY] 价格达标提醒：最低 ￥{cheap[0]['key_price']:.2f}",
        body_text=body,
    )
    print(f"  邮件已发送至 {cfg['email']['receiver']}", flush=True)
    return True


def main():
    parser = argparse.ArgumentParser(description="SteamPY 价格监控")
    parser.add_argument("--config", default=DEFAULT_CONFIG,
                        help="配置文件路径（默认 ./config.json）")
    parser.add_argument("--session", default=DEFAULT_SESSION,
                        help="登录凭证文件路径（默认 ./session.json）")
    parser.add_argument("--once", action="store_true",
                        help="只检查一次后退出（不轮询）")
    args = parser.parse_args()

    try:
        cfg = load_config(args.config)
        validate_config(cfg)
        session = load_session(args.session)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"[配置错误] {e}", file=sys.stderr)
        print("提示：先运行 python get_session.py 获取登录凭证，"
              "再检查 config.json 的 email 配置。", file=sys.stderr)
        sys.exit(1)

    interval = int(cfg["steampy"].get("poll_interval_seconds", 60))

    if args.once:
        try:
            hit = run_once(cfg, session)
        except AuthError as e:
            print(f"[认证失败] {e}", file=sys.stderr)
            print("请重跑 python get_session.py 重新登录。", file=sys.stderr)
            sys.exit(2)
        except Exception as e:
            print(f"[查询失败] {e}", file=sys.stderr)
            sys.exit(3)
        sys.exit(0 if hit else 4)

    print(f"开始监控，每 {interval} 秒轮询一次，Ctrl+C 退出。", flush=True)
    while True:
        try:
            hit = run_once(cfg, session)
            if hit:
                print("已发送提醒，按「只提醒一次」策略退出监控。", flush=True)
                break
        except AuthError as e:
            print(f"[认证失败] {e}", file=sys.stderr)
            print("请重跑 python get_session.py 重新登录。", file=sys.stderr)
            break
        except Exception as e:
            print(f"[查询失败] {e}，稍后重试...", file=sys.stderr)
            traceback.print_exc()

        time.sleep(interval)


if __name__ == "__main__":
    main()
