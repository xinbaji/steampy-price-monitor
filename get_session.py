# -*- coding: utf-8 -*-
"""一键获取 SteamPY 登录凭证（Playwright + Edge 持久化登录）

用法：
  python get_session.py

流程：
  1. 用已安装的 Edge 打开浏览器窗口（复用持久化 profile，首次为空）
  2. 你在窗口里登录 steampy.com（含 Steam 授权/验证码都手动完成）
  3. 脚本自动检测 localStorage 的 accessToken，登录成功后
     把 accessToken + Cookie 保存到 session.json
  4. 之后 monitor.py 直接读取 session.json，无需再复制任何东西

注意：
  - 本脚本依赖 playwright（已装在隔离 venv）
  - 登录态保存在 .profile/ 目录，accessToken 过期后重跑本脚本即可
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(BASE_DIR, ".profile")
SESSION_FILE = os.path.join(BASE_DIR, "session.json")
LOGIN_URL = "https://steampy.com/pro/"
TIMEOUT_SECONDS = 600  # 10 分钟等待用户登录


def main():
    print("正在启动 Edge 浏览器窗口...")
    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                PROFILE_DIR,
                channel="msedge",
                headless=False,
                viewport={"width": 1360, "height": 860},
            )
        except Exception as e:
            print(f"[错误] 启动 Edge 失败: {e}")
            print("请确认已安装 Microsoft Edge，且未被占用（可先关闭 Edge 再试）")
            sys.exit(1)

        page = context.pages[0] if context.pages else context.new_page()
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
        print("=" * 50)
        print("请在浏览器窗口中登录 steampy.com ...")
        print("（若已登录会自动跳过；验证码/Steam 授权请在窗口内完成）")
        print("=" * 50)

        deadline = time.time() + TIMEOUT_SECONDS
        token = ""
        while time.time() < deadline:
            try:
                token = page.evaluate(
                    "() => localStorage.getItem('accessToken') || ''")
            except Exception:
                token = ""
            if token:
                break
            time.sleep(2)

        if not token:
            print("[超时] 10 分钟内未检测到登录，请重试。")
            context.close()
            sys.exit(1)

        cookies = context.cookies()
        cookie_header = "; ".join(
            f"{c['name']}={c['value']}" for c in cookies)
        session = {
            "access_token": token,
            "cookie_header": cookie_header,
            "cookies": cookies,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(session, f, ensure_ascii=False, indent=2)

        print(f"[成功] 登录凭证已保存到 {SESSION_FILE}")
        print(f"  accessToken 长度: {len(token)}")
        print(f"  Cookie 条目: {len(cookies)}")
        print("现在可以直接运行 monitor.py 开始监控。")
        context.close()


if __name__ == "__main__":
    main()
