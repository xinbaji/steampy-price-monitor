# -*- coding: utf-8 -*-
"""单元测试：steampy_core 核心逻辑（无需网络，mock 数据）"""
import json
import sys
import os
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import steampy_core as core
from steampy_core import (AuthError, find_cheap_buyers, normalize_buyer,
                          parse_game_url)


class TestParseGameUrl(unittest.TestCase):
    def test_标准链接(self):
        r = parse_game_url(
            "https://steampy.com/pro/cdKey/cdkDetail"
            "?name=cn&gameId=9001034537870446481409")
        self.assertEqual(r["game_id"], "9001034537870446481409")
        self.assertEqual(r["region"], "cn")

    def test_其他区域(self):
        r = parse_game_url(
            "https://steampy.com/pro/cdKey/cdkDetail"
            "?name=ru&gameId=123")
        self.assertEqual(r["region"], "ru")

    def test_缺gameId报错(self):
        with self.assertRaises(ValueError):
            parse_game_url("https://steampy.com/pro/cdKey/cdkDetail?name=cn")

    def test_未知区域报错(self):
        with self.assertRaises(ValueError):
            parse_game_url(
                "https://steampy.com/pro/cdKey/cdkDetail?name=xx&gameId=1")


class TestNormalizeBuyer(unittest.TestCase):
    def test_正常行(self):
        b = normalize_buyer({"steamName": "abc", "stock": 5, "keyPrice": "168.5"})
        self.assertEqual(b["key_price"], 168.5)
        self.assertEqual(b["stock"], 5)
        self.assertEqual(b["steam_name"], "abc")

    def test_价格非法(self):
        b = normalize_buyer({"keyPrice": "abc", "stock": 1})
        self.assertEqual(b["key_price"], float("inf"))

    def test_缺库存(self):
        b = normalize_buyer({"keyPrice": "100", "stock": None})
        self.assertEqual(b["stock"], 0)


class TestFindCheapBuyers(unittest.TestCase):
    SAMPLE = [
        {"steamName": "a", "stock": 2, "keyPrice": "175.0"},
        {"steamName": "b", "stock": 0, "keyPrice": "120.0"},   # 无库存排除
        {"steamName": "c", "stock": 1, "keyPrice": "199.0"},   # 超阈值排除
        {"steamName": "d", "stock": 3, "keyPrice": "180.0"},   # 等于阈值命中
        {"steamName": "e", "stock": 1, "keyPrice": "160.5"},
    ]

    def test_过滤与排序(self):
        cheap = find_cheap_buyers(self.SAMPLE, max_price=180.0)
        prices = [b["key_price"] for b in cheap]
        self.assertEqual(prices, [160.5, 175.0, 180.0])
        self.assertTrue(all(b["stock"] >= 1 for b in cheap))

    def test_无命中(self):
        self.assertEqual(find_cheap_buyers(self.SAMPLE, max_price=100.0), [])


class TestFetchBuyers(unittest.TestCase):
    def test_正常响应(self):
        payload = json.dumps({
            "success": True,
            "result": {"content": [
                {"steamName": "x", "stock": 1, "keyPrice": "150.0"}
            ]},
        }).encode()
        with patch("urllib.request.urlopen") as m:
            m.return_value.__enter__.return_value.read.return_value = payload
            rows = core.fetch_buyers("cookie=1", "123", "cn")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["keyPrice"], "150.0")

    def test_401抛AuthError(self):
        payload = json.dumps({
            "success": False, "code": 401, "message": "您还未登录",
        }).encode()
        with patch("urllib.request.urlopen") as m:
            m.return_value.__enter__.return_value.read.return_value = payload
            with self.assertRaises(AuthError):
                core.fetch_buyers("cookie=bad", "123", "cn")


if __name__ == "__main__":
    unittest.main(verbosity=2)
