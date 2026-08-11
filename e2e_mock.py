# 端到端模拟：mock 网络+邮件，验证 run_once 命中→发信→退出完整链路
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from unittest.mock import patch
import monitor

cfg = {
    "steampy": {
        "game_url": "https://steampy.com/pro/cdKey/cdkDetail?name=cn&gameId=9001034537870446481409",
        "max_price": 179.0,
        "poll_interval_seconds": 60,
    },
    "email": {
        "smtp_host": "smtp.qq.com", "smtp_port": 465,
        "sender": "me@qq.com", "auth_code": "xxx", "receiver": "me@qq.com",
    },
}

session = {
    "access_token": "fake_token_abc",
    "cookie_header": "userInfo=fake; loginRead=1",
}

fake_rows = [
    {"steamName": "买家A", "stock": 3, "keyPrice": "175.0", "discount": 0.95},
    {"steamName": "买家B", "stock": 1, "keyPrice": "188.0", "discount": 0.99},
    {"steamName": "买家C", "stock": 0, "keyPrice": "120.0", "discount": 0.8},
]

with patch("monitor.fetch_buyers", return_value=fake_rows) as mf, \
     patch("monitor.send_email") as ms:
    hit = monitor.run_once(cfg, session)
    print("命中:", hit)
    # 验证 fetch_buyers 收到了 session 中的凭证
    args, kwargs = mf.call_args
    assert args[0] == "userInfo=fake; loginRead=1", "cookie_header 未传递"
    assert kwargs.get("access_token") == "fake_token_abc", "access_token 未传递"
    print("凭证传递正确: cookie + accessToken")
    ms.assert_called_once()
    call = ms.call_args
    print("邮件主题:", call.kwargs["subject"])
    print("邮件正文:")
    print(call.kwargs["body_text"])
    assert hit is True
    assert "175.0" in call.kwargs["body_text"]
    assert "买家C" not in call.kwargs["body_text"]  # 无库存应排除
    print("\n=== E2E 链路验证通过 ===")
