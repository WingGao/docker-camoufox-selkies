# Camoufox Selkies

基于 LinuxServer Selkies 的 Docker 化 Camoufox/Firefox 环境。它同时提供可在浏览器中直接操作的 X11/Openbox 桌面和标准 Playwright BrowserServer WebSocket 接口，并可选择使用固定 Firefox profile。

## 架构

```text
Web browser -> HTTPS :3001 -> Selkies -> X11/Openbox -> Camoufox
External agent -> WebSocket :1234 -> Playwright BrowserServer -> Camoufox
```

Selkies 负责 patched Xvfb、Openbox、视频、音频、键鼠、Unicode 剪贴板和 Nginx。本项目不会自行启动 Xvfb，也不包含 x11vnc、noVNC、websockify 或 Wayland。Camoufox 使用官方 Python package，Playwright 版本由 Camoufox 依赖约束决定。

BrowserServer 使用 Playwright 的 shared BrowserServer 分支，因此 Selkies 中的长期 Firefox context 与远程 Agent 连接可见的是同一 context。Agent 应优先复用 `browser.contexts[0]`，不要关闭这个长期 context；这样页面、cookie 和登录状态才能在持久化模式下跨连接和容器重建保留。

## Build

Debian 和 PyPI 默认使用阿里云镜像，均可通过 build args 覆盖：

```bash
docker compose build
```

完全重建：

```bash
docker compose build --no-cache
```

可用参数：

| Build arg | 默认值 |
| --- | --- |
| `DEBIAN_MIRROR` | `https://mirrors.aliyun.com/debian` |
| `DEBIAN_SECURITY_MIRROR` | `https://mirrors.aliyun.com/debian-security` |
| `PIP_INDEX_URL` | `https://mirrors.aliyun.com/pypi/simple/` |

构建期间会通过 Camoufox 官方 package fetch API 下载浏览器 bundle，将其暴露为稳定路径 `/opt/camoufox/browser/camoufox-bin`，并严格 patch 实际安装的 Playwright driver。只下载浏览器，不在构建时访问 Mozilla 下载可选扩展。patch 无法唯一识别 Firefox profile 创建逻辑、静态校验失败或 Node 语法检查失败时，构建会直接失败。

## 默认运行

默认模式不持久化 Firefox profile：

```bash
docker compose up -d
docker compose logs -f camoufox
```

WebUI：

```text
https://localhost:3001
```

3001 使用容器生成的 HTTPS 证书，浏览器第一次访问时可能提示自签名证书。HTTP 3000 也被保留。默认 compose 将 3000、3001 和 1234 都绑定到 `127.0.0.1`，不会监听所有主机接口。

`./config:/config` 只持久化 Selkies 桌面配置，不代表 Firefox profile 被持久化。默认 Camoufox 进程应使用：

```text
-profile /tmp/playwright_firefoxdev_profile-...
```

## 持久化运行

持久化示例使用独立 Docker named volume：

```bash
docker compose -f docker-compose.persistent.yml up -d
docker compose -f docker-compose.persistent.yml logs -f camoufox
```

它设置：

```text
CAMOUFOX_PERSISTENT_CONTEXT=true
CAMOUFOX_USER_DATA_DIR=/data/camoufox-profile
```

并把 `camoufox-profile` volume 挂载到 `/data/camoufox-profile`。浏览器进程最终应使用：

```text
-profile /data/camoufox-profile
```

停止或重建容器不会删除 named volume：

```bash
docker compose -f docker-compose.persistent.yml down
docker compose -f docker-compose.persistent.yml up -d
```

不要使用 `down -v`，该选项会主动删除 profile volume。

如需 bind mount，可把 compose 中的 named volume 改为 `./profile:/data/camoufox-profile`，并先保证目录可由容器运行用户写入：

```bash
mkdir -p profile
sudo chown 1000:1000 profile
chmod 700 profile
```

一个 Firefox profile 同一时间只能由一个 Camoufox 实例使用。多实例必须使用不同目录，例如 `/profiles/1`、`/profiles/2`，禁止多个 Firefox 进程同时共享同一 profile。

## 配置

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `CAMOUFOX_PORT` | `1234` | BrowserServer 容器内端口，范围 1-65535 |
| `CAMOUFOX_PERSISTENT_CONTEXT` | `false` | 是否启用固定 profile |
| `CAMOUFOX_USER_DATA_DIR` | 空 | 固定 profile 的绝对路径 |
| `CAMOUFOX_DEBUG` | `false` | 输出版本、可执行文件、DISPLAY 和 patch 路径诊断 |
| `CAMOUFOX_STARTUP_TIMEOUT` | `120` | 等待 WebSocket endpoint 的秒数 |
| `PIXELFLUX_WAYLAND` | `false` | 必须保持 false，使用 X11/Openbox |
| `PUID` / `PGID` | `1000` | LinuxServer 运行用户映射 |

Compose 中可通过 `CAMOUFOX_PORT` 同时修改容器内监听端口，通过 `CAMOUFOX_HOST_PORT` 修改宿主机端口。例如：

```bash
CAMOUFOX_PORT=4321 CAMOUFOX_HOST_PORT=14321 docker compose up -d
```

该命令映射 `127.0.0.1:14321 -> container:4321`，healthcheck 也会检查 4321。

合法 profile 参数组合只有：

```text
false + 空 user_data_dir -> ephemeral
true  + 绝对 user_data_dir -> persistent
```

只设置其中一项、使用相对路径、目录无法创建或不可写都会使启动立即失败，不会回退到临时 profile。

也可直接调用 CLI：

```bash
XDG_CACHE_HOME=/opt /opt/camoufox-venv/bin/python /app/server_entrypoint.py --port 1234

XDG_CACHE_HOME=/opt /opt/camoufox-venv/bin/python /app/server_entrypoint.py \
  --port 1234 \
  --persistent-context \
  --user-data-dir /data/camoufox-profile
```

Python API 位于 `app/camoufox_server.py`：

```python
from app.camoufox_server import launch_camoufox_server

launch_camoufox_server(
    headless=False,
    port=1234,
    persistent_context=True,
    user_data_dir="/data/camoufox-profile",
)
```

## Remote Playwright

完整动态 endpoint 会同时以以下格式写入容器日志：

```text
[camoufox] websocket=ws://0.0.0.0:1234/<id>
```

同一地址也会写入容器内 `/config/.cache/camoufox-server/ws_endpoint`。

Firefox 或 BrowserServer 在 endpoint 就绪后意外退出时，稳定 Python launcher 会清除旧 endpoint 并自动启动新实例；新实例会输出新的动态 endpoint。参数或 profile 权限错误仍立即失败，不会重试或回退。

查看 endpoint：

```bash
docker compose logs camoufox | grep '\[camoufox\] websocket='
```

客户端连接时把日志中的 `0.0.0.0` 换成客户端可访问的 Docker 主机地址。远程客户端应使用与容器相同主次版本的 Playwright；当前版本可通过 `CAMOUFOX_DEBUG=true` 查看。

```python
from playwright.async_api import async_playwright

async with async_playwright() as p:
    browser = await p.firefox.connect("ws://127.0.0.1:1234/<id>")
    context = browser.contexts[0]
    page = await context.new_page()
    await page.goto("https://example.com")
    print(await page.title())
    await browser.close()
```

Playwright WebSocket 没有内置强认证。默认只绑定 loopback；如需跨主机连接，应通过受控网络、VPN 或有认证和 TLS 的反向代理提供，禁止直接暴露到公网。

## 验证

运行单元测试：

```bash
python3 -m unittest discover -v
```

查看实际 Firefox profile 参数，不要只检查目录是否存在：

```bash
docker compose exec camoufox \
  ps auxww | grep '[c]amoufox-bin'
```

默认模式应看到：

```text
-profile /tmp/playwright_firefoxdev_profile-...
```

持久化模式应看到：

```text
-profile /data/camoufox-profile
```

远程 smoke test：

```bash
python3 tests/smoke/connect.py 'ws://127.0.0.1:1234/<id>'
```

持久化状态测试先运行 `write`，重建容器但保留 profile volume，再对新 endpoint 运行 `verify`：

```bash
python3 tests/smoke/persistence.py write  'ws://127.0.0.1:1234/<id>'
docker compose -f docker-compose.persistent.yml down
docker compose -f docker-compose.persistent.yml up -d
python3 tests/smoke/persistence.py verify 'ws://127.0.0.1:1234/<new-id>'
```

## WebUI 验收

以下项目需要通过真实浏览器在 `https://localhost:3001` 手工验证，因为主机浏览器剪贴板授权、输入法和窗口焦点无法由容器单元测试可靠模拟：

1. Firefox 窗口可见，刷新、鼠标、滚轮和键盘正常。
2. 本机复制 `你好，Camoufox 中文测试 😀 123`，进入 Firefox 按 `Ctrl+V`，结果逐字一致且无乱码。
3. 远端复制 `Camoufox 反向复制测试 中文 🚀`，在本机粘贴，结果逐字一致。
4. 中文网页、Emoji 和 Firefox 原生菜单显示正常。
5. 安装带 browserAction popup 的 Firefox 扩展，点击图标后将鼠标移入 popup；popup 必须保持打开且内部元素可点击。

## 安全

Selkies 自带的 basic auth 主要适用于可信网络，不应被视为公网应用网关。若修改端口绑定为 `0.0.0.0`，至少设置 `CUSTOM_USER` 和 `PASSWORD`，并推荐在前面部署成熟的认证反向代理。容器桌面用户默认具有 LinuxServer baseimage 提供的能力，不应让不可信用户访问。

部分宿主机 seccomp 配置可能阻止 Firefox 所需 syscall。如浏览器启动日志明确提示 sandbox/syscall 问题，可在可信环境中尝试 compose 配置：

```yaml
security_opt:
  - seccomp=unconfined
```

该选项会降低隔离强度，不应默认启用。

## Troubleshooting

### Profile 没生效

运行：

```bash
docker compose exec camoufox ps auxww | grep '[c]amoufox-bin'
```

如果持久化模式仍看到 `/tmp/playwright_firefoxdev_profile-*`，说明 patch 没进入实际启动路径。开启 `CAMOUFOX_DEBUG=true`，检查日志中的 `debug.patch`，然后无缓存重建镜像。仅看到 `/data/camoufox-profile` 目录存在不能证明 Firefox 正在使用它。

### Profile 权限错误

```bash
docker compose exec camoufox ls -ld /data/camoufox-profile
docker compose exec camoufox id
```

运行用户必须可写。配置要求持久化但目录不可写时，launcher 会输出 `Camoufox profile directory is not writable` 并退出，不会静默使用临时 profile。

### Autostart 修改没有生效

Selkies 仅在第一次创建 `/config` 时把 `/defaults/autostart` 复制为 `/config/.config/openbox/autostart`，后续镜像更新不会覆盖已有文件。本项目保持该脚本仅调用稳定的 `/app/server_entrypoint.py`；应用逻辑更新无需修改 autostart。如旧配置来自其他镜像，应停止容器并删除对应的旧 `openbox/autostart` 后重新启动，操作前先备份 `/config`。

### 没有 WebSocket endpoint

检查：

```bash
docker compose logs camoufox
docker compose ps
```

确认日志存在 `[camoufox] starting`、正确的 `display=:1` 和 mode。超过 `CAMOUFOX_STARTUP_TIMEOUT` 仍未输出 endpoint 时，launcher 会终止子进程并报告错误。

### 中文剪贴板乱码

确认 compose 中 `LANG=C.UTF-8`、`LC_ALL=C.UTF-8`，并且未切换到 Wayland。使用 HTTPS 3001，允许浏览器的剪贴板权限，然后用“WebUI 验收”中的固定字符串双向测试。
