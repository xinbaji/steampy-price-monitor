# SteamPY 价格监控脚本

监控 steampy.com 某游戏 CDKey 买家价格，每 N 分钟轮询一次；
存在单价 ≤ 阈值 的买家时，自动发 QQ 邮箱提醒（只提醒一次后退出）。

## 文件说明

| 文件 | 说明 |
|---|---|
| `get_session.py` | **一键登录**：Playwright 打开 Edge，登录一次后自动抓取凭证存 session.json |
| `monitor.py` | 主程序（轮询 + 触发邮件） |
| `steampy_core.py` | 核心逻辑：URL 解析 / API 请求 / 买家过滤（可单元测试） |
| `email_sender.py` | QQ 邮箱 SMTP/SSL 发信 |
| `config.json` | 目标价格与邮箱配置（**不含登录凭证**） |
| `session.json` | 登录凭证（自动生成，勿手动改） |
| `test_core.py` / `e2e_mock.py` | 单元测试 / mock 端到端 |

## 使用步骤

1. **运行环境**（一次性）：
   ```bash
   "C:/Users/cyh/.workbuddy/binaries/python/envs/steampy/Scripts/python.exe" get_session.py
   ```
   会弹出 Edge 窗口，登录 steampy.com 后凭证自动保存，**无需复制任何东西**。

2. **填 config.json**：
   - `steampy.game_url`：要监控的游戏 cdkDetail 链接（含 gameId）
   - `steampy.max_price`：目标价格（如 179.0，单价 ≤ 它即提醒）
   - `steampy.poll_interval_seconds`：轮询间隔，默认 60 秒
   - `email.sender`：QQ 邮箱（发件人）
   - `email.auth_code`：QQ 邮箱「设置 → 账号 → 开启 SMTP 服务」的授权码
   - `email.receiver`：接收提醒的邮箱

3. **运行**：
   ```bash
   # 用隔离 venv 的 python 运行
   "C:/Users/cyh/.workbuddy/binaries/python/envs/steampy/Scripts/python.exe" monitor.py
   # 或普通 python（脚本本身只用标准库）
   python monitor.py
   python monitor.py --once     # 只检查一次（测试用）
   ```

## 技术要点

- 买家列表接口：`GET https://steampy.com/xboot/steamKeySale/listSale`
  （cn 区；ru/us/tl 自动按链接 name 参数切换）
- **认证机制**：登录 token 存浏览器 localStorage 的 `accessToken`，
  通过请求头 `accessToken` 发送，参数走 query string
  （不是 Cookie 鉴权、不是 POST body）—— 这就是必须用 Playwright
  抓凭证的原因
- 参数 `sort=keyPrice&order=asc` 按单价升序，返回 `result.content[]`
- 凭证失效（401）时重跑 `get_session.py` 重新登录即可
- 脚本默认直连，绕过系统代理（死代理 127.0.0.1:7897 会拖垮请求）

## 测试

```bash
python -m py_compile steampy_core.py email_sender.py monitor.py get_session.py
python test_core.py
python e2e_mock.py
```
