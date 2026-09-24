
# Camoufox Selkies WebUI Container — Implementation Spec

## 1. 项目目标

从零实现一个 Docker 化的 Camoufox 浏览器运行环境，提供：

* Camoufox / Firefox
* Playwright Remote Server / WebSocket 控制
* LinuxServer Selkies WebUI
* X11 + Xfwm4 + Xfce Panel 图形环境
* 浏览器内鼠标、键盘正常操作
* 中文 / Unicode 双向剪贴板
* Firefox 扩展 popup 正常交互
* 可选的 Firefox Profile 持久化
* Docker Compose 部署
* 可供外部 Agent 使用 Playwright WebSocket 连接

最终使用体验应类似：

```text
linuxserver/chromium
```

但实际运行的是：

```text
Camoufox / Firefox
```

整体架构：

```text
                         Browser
                            │
                            │ HTTPS :3001
                            ▼
                    ┌────────────────┐
                    │    Selkies     │
                    │ Web UI / Input │
                    │ Clipboard      │
                    │ Audio          │
                    └───────┬────────┘
                            │
                    X11 / Xfwm4 + Panel
                            │
                            ▼
                    ┌────────────────┐
                    │    Camoufox    │
                    │    Firefox     │
                    └───────┬────────┘
                            │
                     Playwright/Juggler
                            │
                            ▼
                  Playwright BrowserServer
                            │
                     WebSocket :1234
                            │
                            ▼
                      External Agent
```

---

# 2. 明确不使用的方案

这是一个全新项目。

不要继承、修改、复制之前可能存在的实现。

明确禁止将以下组件作为最终架构的一部分：

```text
apify/actor-python-playwright-camoufox
x11vnc
noVNC
websockify
手工启动的 Xvfb
之前编写的 profile patch
之前的 clipboard HTTP bridge
```

不要：

```dockerfile
FROM apify/actor-python-playwright-camoufox
```

必须从 LinuxServer Selkies baseimage 开始。

推荐：

```dockerfile
FROM ghcr.io/linuxserver/baseimage-selkies:debiantrixie
```

LinuxServer 官方将该 baseimage 定位为构建 browser-accessible Linux GUI application 的基础镜像，并提供 X11/Openbox fallback、Selkies、Nginx、音频、输入、GPU 检测等基础设施。项目在该基础上使用自定义 `startwm.sh` 启动 Xfwm4 和 Xfce Panel。([LinuxServer][1])

---

# 3. Display / WebUI 架构

第一版必须使用：

```text
Selkies
+
X11
+
Xfwm4

Xfce Panel
```

不要使用 Wayland。

Docker 环境中设置：

```text
PIXELFLUX_WAYLAND=false
```

Selkies 在该模式下会负责：

```text
patched Xvfb
Xfwm4
Xfce Panel
X11 input
屏幕采集
Web UI
Clipboard
Audio
Nginx
```

因此项目本身不允许再次启动 Xvfb。

LinuxServer 官方 X11 fallback 提供：

```text
patched Xvfb + Openbox + Selkies
```

本项目通过自定义 `/defaults/startwm.sh` 用 Xfwm4 替换 Openbox，并继续通过 `/defaults/autostart` 启动应用。([LinuxServer][1])

---

# 4. WebUI

WebUI 使用 Selkies 自带 Web Client。

主要入口：

```text
https://HOST:3001
```

可以同时保留：

```text
3000
```

但推荐实际使用 HTTPS `3001`。

必须验证：

```text
鼠标
键盘
Ctrl+C
Ctrl+V
中文
Emoji
Firefox 原生菜单
Firefox extension popup
```

全部正常。

特别验证：

```text
本机复制：

你好，Camoufox 中文测试 😀 123

进入 Selkies Firefox
Ctrl+V
```

结果必须精确为：

```text
你好，Camoufox 中文测试 😀 123
```

不允许出现：

```text
ä¸­æ–‡
```

或其他乱码。

---

# 5. Camoufox 安装

使用官方 Python package。

建议建立独立 virtualenv：

```text
/opt/camoufox-venv
```

安装 Camoufox：

```bash
python -m venv /opt/camoufox-venv

/opt/camoufox-venv/bin/pip install --upgrade pip

/opt/camoufox-venv/bin/pip install \
    "camoufox[geoip]"
```

然后下载 Camoufox Browser：

```bash
/opt/camoufox-venv/bin/python -m camoufox fetch
```

Camoufox 官方当前安装方式为 Python package + `camoufox fetch`。([Camoufox][2])

不要额外安装一个不同版本的 Playwright。

应该让：

```text
camoufox
```

依赖声明决定兼容的：

```text
playwright
```

版本。

---

# 6. Browser binary 与 runtime user

LinuxServer Selkies 的 GUI session 运行用户为：

```text
abc
```

而 Docker build 阶段通常是：

```text
root
```

因此必须处理 Camoufox browser cache 路径问题。

不能假定：

```text
/root/.cache/camoufox
```

在 runtime 可以正常自动发现。

实现必须保证：

```text
abc
```

可以读取并执行 Camoufox browser binary。

推荐方式：

1. build 阶段执行 `camoufox fetch`
2. 找到实际 Camoufox executable
3. 将 browser bundle 放到稳定的只读路径，例如：

```text
/opt/camoufox/browser/
```

4. 权限设置为：

```text
root:root
755 directories
755 executable
644 normal files
```

5. runtime 启动 Camoufox 时显式传：

```python
executable_path=...
```

不要依赖 root home cache。

实现过程中允许使用 Camoufox API 动态定位 browser binary，但最终 runtime executable path 必须稳定、明确、可测试。

---

# 7. 中文字体

镜像必须包含中文字体。

至少：

```text
fonts-noto-cjk
fonts-noto-color-emoji
```

并设置合理 UTF-8 locale。

例如：

```text
LANG=C.UTF-8
LC_ALL=C.UTF-8
```

必须验证网页和浏览器 UI 可以正确显示中文。

---

# 8. Camoufox Server

项目必须提供自己的 Python server wrapper。

不要直接把：

```python
camoufox.server.launch_server
```

作为应用入口。

创建：

```text
app/camoufox_server.py
```

暴露：

```python
launch_server(...)
```

或：

```python
launch_camoufox_server(...)
```

它的基本 API 必须兼容 Camoufox `launch_server()` 的常用参数。

例如：

```python
launch_camoufox_server(
    headless=False,
    port=1234,
    ...
)
```

除此之外增加两个参数：

```python
persistent_context: bool = False
user_data_dir: str | None = None
```

---

# 9. Profile 持久化语义

这是本项目最重要的行为约束。

## 9.1 默认模式

如果：

```python
launch_camoufox_server(
    headless=False,
    port=1234,
)
```

或者：

```python
launch_camoufox_server(
    headless=False,
    port=1234,
    persistent_context=False,
    user_data_dir=None,
)
```

必须使用 Playwright 原生 BrowserServer 临时 profile。

表现应类似：

```text
-profile /tmp/playwright_firefoxdev_profile-XXXXXXXX
```

容器 / BrowserServer 退出后不要求保留任何 Firefox profile 数据。

这是默认行为。

---

# 9.2 持久化模式

只有以下两个参数同时满足：

```python
persistent_context=True
```

并且：

```python
user_data_dir="/some/absolute/path"
```

才启用持久化 Firefox profile。

例如：

```python
launch_camoufox_server(
    headless=False,
    port=1234,
    persistent_context=True,
    user_data_dir="/data/camoufox-profile",
)
```

此时 Firefox 必须最终以：

```text
-profile /data/camoufox-profile
```

启动。

必须真实保存：

```text
cookies.sqlite
prefs.js
places.sqlite
extensions.json
addons.json
storage/
extension settings
Firefox preferences
login state
```

等 profile 内容。

---

# 9.3 参数组合校验

以下组合必须允许：

```text
persistent_context=False
user_data_dir=None

→ ephemeral
```

以及：

```text
persistent_context=True
user_data_dir=/absolute/path

→ persistent
```

以下组合必须拒绝：

```text
persistent_context=True
user_data_dir=None
```

报错：

```text
persistent_context=True requires user_data_dir
```

以下组合也必须拒绝：

```text
persistent_context=False
user_data_dir=/some/path
```

报错类似：

```text
user_data_dir requires persistent_context=True
```

相对路径：

```text
./profile
```

必须拒绝。

要求：

```text
user_data_dir
```

必须为 absolute path。

---

# 10. 注意：不要真正改成 launchPersistentContext

这里非常重要。

Camoufox 官方当前：

```python
Camoufox(
    persistent_context=True,
    user_data_dir=...
)
```

走的是 Playwright：

```text
launchPersistentContext()
```

并返回：

```text
BrowserContext
```

官方支持这种模式。([Camoufox][2])

但是：

```python
camoufox.server.launch_server()
```

走的是：

```text
BrowserType.launchServer()
→ Browser
→ BrowserServer
```

Playwright Server model 并不能直接 serve 一个 `launchPersistentContext()` 返回的 BrowserContext。

Camoufox 上游在 2026 年 8 月已经明确处理这一点：`launch_server()` 不再静默接受 `persistent_context/user_data_dir`，因为 Playwright BrowserServer 原生并不消费这些参数。([GitHub][3])

因此：

**本项目的 `persistent_context=True` 是一个兼容扩展。**

其实际语义是：

> BrowserServer 仍然保持 BrowserServer，但强制底层 Firefox 使用固定 profile directory。

不要改变远程客户端使用方式。

客户端仍然应该能够：

```python
browser = playwright.firefox.connect(ws_endpoint)
```

---

# 11. Persistent BrowserServer 实现方式

必须采用：

```text
Python wrapper
+
Playwright driver 小型 build-time patch
```

实现。

不要 fork 整个 Playwright 项目。

不要 fork 整个 Camoufox 项目。

---

# 12. Python wrapper 实现

当前 Camoufox server 实际上非常薄：

```text
launch_options()
↓
启动 bundled Node
↓
camoufox/launchServer.js
↓
Playwright driver/package
```

当前上游 `server.py` 使用 `subprocess.Popen()` 启动 Node driver。([GitHub][4])

本项目自己的 wrapper 应：

```python
def launch_camoufox_server(
    *,
    persistent_context=False,
    user_data_dir=None,
    **kwargs,
):
```

首先校验参数。

伪代码：

```python
persistent = persistent_context is True

if persistent and not user_data_dir:
    raise ValueError(...)

if user_data_dir and not persistent:
    raise ValueError(...)

if persistent:
    path = Path(user_data_dir)

    if not path.is_absolute():
        raise ValueError(...)

    path.mkdir(parents=True, exist_ok=True)
```

然后：

```python
kwargs
```

中必须删除：

```text
persistent_context
user_data_dir
```

不要把它们直接传给当前 upstream：

```python
launch_options(...)
```

或者 upstream：

```python
launch_server(...)
```

因为 upstream Server API 当前不支持它们。

---

# 13. Child-specific environment

持久化 profile 信息必须通过 **Node child process environment** 传递。

定义：

```text
CAMOUFOX_SERVER_USER_DATA_DIR
```

例如 persistent 模式：

```text
CAMOUFOX_SERVER_USER_DATA_DIR=/data/camoufox-profile
```

ephemeral 模式：

```text
CAMOUFOX_SERVER_USER_DATA_DIR
```

必须不存在。

重要：

不要：

```python
os.environ["CAMOUFOX_SERVER_USER_DATA_DIR"] = ...
```

然后永久修改整个 Python process global environment。

必须构造：

```python
child_env = os.environ.copy()
```

persistent：

```python
child_env["CAMOUFOX_SERVER_USER_DATA_DIR"] = user_data_dir
```

ephemeral：

```python
child_env.pop("CAMOUFOX_SERVER_USER_DATA_DIR", None)
```

然后：

```python
subprocess.Popen(
    ...,
    env=child_env,
)
```

这样避免不同 server launch 之间 environment 泄漏。

---

# 14. Playwright Patch

创建独立脚本：

```text
scripts/patch_playwright_profile.py
```

在 Docker build 阶段执行。

目标：

修改 installed Playwright driver，使 Firefox BrowserServer 在：

```text
CAMOUFOX_SERVER_USER_DATA_DIR
```

存在时，使用该目录作为：

```text
userDataDir
```

否则完全保持 Playwright 原行为。

---

# 15. Patch 行为

Playwright 原逻辑概念上类似：

```javascript
if (userDataDir) {
    await mkdir(userDataDir)
} else {
    userDataDir = await mkdtemp(
        "playwright_firefoxdev_profile-"
    )

    tempDirectories.push(userDataDir)
}
```

Patch 后逻辑概念上应为：

```javascript
if (
    !userDataDir &&
    this._name === "firefox" &&
    process.env.CAMOUFOX_SERVER_USER_DATA_DIR
) {
    userDataDir =
        process.env.CAMOUFOX_SERVER_USER_DATA_DIR
}

if (userDataDir) {
    await mkdir(userDataDir)
} else {
    userDataDir = await mkdtemp(...)
    tempDirectories.push(userDataDir)
}
```

关键点：

persistent profile：

```text
不能加入 tempDirectories
```

否则 Playwright 关闭时可能删除 profile。

---

# 16. Patch 必须具备版本保护

不要 hardcode：

```text
browserType.js
```

因为 Playwright wheel 可能将代码 bundle 到：

```text
coreBundle.js
```

或其他文件。

Patch script 应：

1. 从：

```python
import playwright
```

定位：

```text
playwright/driver/package
```

2. recursive search：

```text
*.js
```

3. 搜索 Firefox 临时 profile 特征：

```text
dev_profile-
```

和：

```text
userDataDir
```

4. 定位真实实现文件。

5. 只有找到唯一且可确认的代码位置时才 patch。

如果不能安全确认：

```text
Docker build 必须失败
```

禁止：

```text
静默跳过
```

---

# 17. Patch 必须 idempotent

加入 marker：

```text
CAMOUFOX_PERSISTENT_SERVER_PROFILE_PATCH
```

如果 marker 已存在：

```text
skip
```

不要重复 patch。

---

# 18. Patch backup

build 阶段可以创建：

```text
*.pre-camoufox-patch
```

但最终 production image 中可以删除 backup，减少体积。

开发环境可保留。

---

# 19. Patch verification

Patch 完成后必须执行静态验证：

确认：

```text
CAMOUFOX_PERSISTENT_SERVER_PROFILE_PATCH
```

存在。

确认：

```text
CAMOUFOX_SERVER_USER_DATA_DIR
```

存在。

确认临时 profile 原逻辑仍存在。

如果可能，执行：

```text
node --check TARGET_JS
```

或等价 syntax check。

---

# 20. Server entrypoint

创建：

```text
app/server_entrypoint.py
```

支持 CLI：

```text
--port
--persistent-context
--user-data-dir
```

例如：

```bash
python server_entrypoint.py \
    --port 1234
```

默认：

```text
ephemeral
```

持久化：

```bash
python server_entrypoint.py \
    --port 1234 \
    --persistent-context \
    --user-data-dir /data/camoufox-profile
```

内部调用：

```python
launch_camoufox_server(
    headless=False,
    port=args.port,
    persistent_context=args.persistent_context,
    user_data_dir=args.user_data_dir,
)
```

---

# 21. Docker environment adapter

同时允许通过 Docker env 配置。

建议变量：

```text
CAMOUFOX_PORT=1234

CAMOUFOX_PERSISTENT_CONTEXT=false

CAMOUFOX_USER_DATA_DIR=
```

如果：

```text
CAMOUFOX_PERSISTENT_CONTEXT=true
CAMOUFOX_USER_DATA_DIR=/data/camoufox-profile
```

则：

```python
persistent_context=True
user_data_dir="/data/camoufox-profile"
```

如果：

```text
CAMOUFOX_PERSISTENT_CONTEXT=false
CAMOUFOX_USER_DATA_DIR=
```

则两个持久化参数都不传。

如果只设置一个：

```text
启动失败
```

并输出清晰错误。

---

# 22. Selkies autostart

项目结构必须包含：

```text
root/defaults/autostart
```

其作用只负责执行稳定 launcher，例如：

```bash
#!/bin/bash

exec /opt/camoufox-venv/bin/python \
    /app/server_entrypoint.py
```

不要把大量业务逻辑写进：

```text
/defaults/autostart
```

原因：

Selkies 首次启动会把 autostart copy 到 `/config/.config/openbox/autostart`，之后不会自动覆盖。([LinuxServer][1])

因此 autostart 应保持极简且长期稳定。

实际逻辑始终放：

```text
/app/
```

这样 image rebuild 后即使复用 `/config`，仍然运行最新代码。

---

# 23. X11 环境

启动 Camoufox 时：

```text
headless=False
```

不要：

```text
headless="virtual"
```

因为 Selkies 已提供 X server。

确保 runtime：

```text
DISPLAY
```

来自 Selkies session。

明确设置：

```text
GDK_BACKEND=x11
MOZ_ENABLE_WAYLAND=0
```

如果存在：

```text
WAYLAND_DISPLAY
```

在 Camoufox launcher 环境中移除。

---

# 24. Recommended repository structure

实现后的 repository 建议：

```text
camoufox-selkies/
├── Dockerfile
├── docker-compose.yml
├── README.md
│
├── requirements.txt
│
├── app/
│   ├── __init__.py
│   ├── camoufox_server.py
│   └── server_entrypoint.py
│
├── scripts/
│   ├── patch_playwright_profile.py
│   └── install_camoufox_browser.py
│
├── root/
│   └── defaults/
│       └── autostart
│
└── tests/
    ├── test_server_options.py
    ├── test_patch.py
    └── smoke/
```

允许根据实际情况稍作调整，但职责必须保持清晰。

---

# 25. Dockerfile

Dockerfile 至少完成：

```text
FROM baseimage-selkies
↓
安装 Python/runtime dependencies
↓
安装 CJK fonts
↓
创建 Python venv
↓
pip install Camoufox
↓
camoufox fetch
↓
将 browser bundle 放到 runtime-safe 路径
↓
patch Playwright
↓
COPY app
↓
COPY root
↓
EXPOSE 3000/3001/1234
```

必须：

```dockerfile
VOLUME /config
```

因为 `/config` 是 Selkies 官方持久化 surface。([LinuxServer][5])

---

# 26. Docker Compose — ephemeral 示例

默认 compose 应体现“不持久化 Browser Profile”。

例如：

```yaml
services:
  camoufox:
    build: .
    container_name: camoufox

    environment:
      PUID: 1000
      PGID: 1000
      TZ: Asia/Shanghai

      PIXELFLUX_WAYLAND: "false"

      CAMOUFOX_PORT: "1234"
      CAMOUFOX_PERSISTENT_CONTEXT: "false"

    volumes:
      - ./config:/config

    ports:
      - "3000:3000"
      - "3001:3001"
      - "127.0.0.1:1234:1234"

    shm_size: "2gb"

    restart: unless-stopped
```

注意：

```text
/config
```

是 Selkies desktop/config 持久化。

这不代表：

```text
Firefox profile
```

自动持久化。

默认 Firefox BrowserServer 仍使用：

```text
/tmp/playwright_firefoxdev_profile-*
```

---

# 27. Docker Compose — persistent 示例

提供第二个 example：

```yaml
services:
  camoufox:
    build: .
    container_name: camoufox

    environment:
      PUID: 1000
      PGID: 1000
      TZ: Asia/Shanghai

      PIXELFLUX_WAYLAND: "false"

      CAMOUFOX_PORT: "1234"

      CAMOUFOX_PERSISTENT_CONTEXT: "true"
      CAMOUFOX_USER_DATA_DIR: "/data/camoufox-profile"

    volumes:
      - ./config:/config
      - ./profile:/data/camoufox-profile

    ports:
      - "3000:3000"
      - "3001:3001"
      - "127.0.0.1:1234:1234"

    shm_size: "2gb"

    restart: unless-stopped
```

---

# 28. Profile permission

由于 browser process 由：

```text
abc
```

用户运行，必须确保：

```text
/data/camoufox-profile
```

可写。

首次启动时 launcher 应：

```text
mkdir -p
```

并检测 writable。

如果没有权限：

```text
立即失败
```

错误例如：

```text
Camoufox profile directory is not writable:
/data/camoufox-profile
```

不要退化成临时 profile。

这是非常重要的约束：

```text
配置要求 persistent
+
profile 无法使用
=
FAIL
```

绝对不能 silent fallback。

---

# 29. 同一个 Profile 只能被一个实例使用

必须在 README 中注明：

```text
一个 Firefox profile 同一时间只能对应一个 Camoufox instance。
```

多实例必须：

```text
instance1 → /profiles/1
instance2 → /profiles/2
instance3 → /profiles/3
```

禁止多个 Firefox process 同时共享：

```text
/data/camoufox-profile
```

---

# 30. Remote Playwright

必须保证外部仍然可以用标准 Playwright：

```python
from playwright.async_api import async_playwright

async with async_playwright() as p:
    browser = await p.firefox.connect(
        "ws://HOST:1234/..."
    )
```

具体 endpoint 使用 Camoufox server 输出的 endpoint。

如果 upstream endpoint 包含动态 path：

```text
ws://0.0.0.0:1234/<uuid>
```

项目必须把完整 endpoint：

```text
输出到 stdout
```

方便 Docker logs 获取。

可以额外写入：

```text
/run/camoufox/ws_endpoint
```

但不是强制。

---

# 31. Server bind

Camoufox Server 在容器内部必须能够：

```text
0.0.0.0:1234
```

提供连接。

Docker Compose 默认建议只映射到：

```text
127.0.0.1:1234
```

因为 Playwright WebSocket server 不应该默认暴露到公网。

---

# 32. Logging

启动日志至少输出：

```text
[camoufox] starting
[camoufox] display=:...
[camoufox] mode=ephemeral
```

或者：

```text
[camoufox] mode=persistent
[camoufox] profile=/data/camoufox-profile
```

以及：

```text
[camoufox] websocket=ws://...
```

Persistent 模式下禁止打印敏感 profile 内容。

---

# 33. Debug diagnostics

提供：

```text
CAMOUFOX_DEBUG=true
```

时输出额外诊断：

```text
Camoufox version
Playwright version
Camoufox browser version
browser executable path
DISPLAY
GDK_BACKEND
persistent mode
profile path
Playwright patched JS path
```

---

# 34. Unit tests

至少覆盖：

### Test A

```python
persistent_context=False
user_data_dir=None
```

结果：

```text
ephemeral
```

---

### Test B

```python
persistent_context=True
user_data_dir="/data/profile"
```

结果：

```text
persistent
```

---

### Test C

```python
persistent_context=True
user_data_dir=None
```

必须：

```text
ValueError
```

---

### Test D

```python
persistent_context=False
user_data_dir="/data/profile"
```

必须：

```text
ValueError
```

---

### Test E

```python
user_data_dir="relative/profile"
```

必须：

```text
ValueError
```

---

### Test F

确认 persistent child Node environment 包含：

```text
CAMOUFOX_SERVER_USER_DATA_DIR
```

ephemeral child environment 不包含。

---

# 35. Integration test — ephemeral profile

启动：

```text
persistent_context=False
```

容器内：

```bash
ps auxww | grep camoufox-bin
```

必须看到类似：

```text
-profile /tmp/playwright_firefoxdev_profile-XXXX
```

不能出现：

```text
/data/camoufox-profile
```

---

# 36. Integration test — persistent profile

启动：

```text
persistent_context=True
user_data_dir=/data/camoufox-profile
```

运行：

```bash
ps auxww | grep camoufox-bin
```

必须看到：

```text
-profile /data/camoufox-profile
```

不能看到：

```text
/tmp/playwright_firefoxdev_profile-
```

---

# 37. Persistent data test

在 Firefox 中：

1. 登录测试网站
2. 创建 cookie
3. 修改一个 Firefox setting
4. 如可行安装测试 extension
5. 停止 container
6. `docker compose down`
7. 重新启动
8. 使用同一个 profile mount

必须恢复：

```text
cookie
login state
Firefox profile state
extension/profile data
```

---

# 38. Ephemeral isolation test

ephemeral 模式：

第一次启动：

```text
设置 Cookie A
```

停止 BrowserServer / container。

重新启动。

必须：

```text
Cookie A 不再依赖之前临时 Firefox profile
```

新的 process 必须获得新的：

```text
/tmp/playwright_firefoxdev_profile-*
```

---

# 39. WebUI test

通过：

```text
https://localhost:3001
```

验证：

```text
Firefox 窗口可见
页面可正常刷新
鼠标正常
滚轮正常
键盘正常
Ctrl+C/Ctrl+V 正常
中文正常
Emoji 正常
```

---

# 40. Firefox popup test

这是重要验收项。

Firefox 中安装一个带 browserAction popup 的 extension。

执行：

```text
点击 extension toolbar icon
→ popup 出现
→ 移动鼠标进入 popup
→ popup 必须保持
→ 可以选择 popup 中的元素
```

不允许出现：

```text
一移动鼠标 popup 立即关闭
```

该测试用于确保：

```text
Selkies input + Xfwm4 + X11
```

没有之前 x11vnc 输入链路的问题。

---

# 41. Clipboard test

本地系统：

```text
复制：
这是一段中文 Clipboard 测试 😀 ABC123
```

进入远端 Firefox：

```text
Ctrl+V
```

必须得到完全一致的 Unicode 内容。

然后反向：

远端 Firefox 复制中文：

```text
Camoufox 反向复制测试 中文 🚀
```

本地粘贴。

也必须一致。

---

# 42. Rebuild test

执行：

```bash
docker compose build --no-cache
docker compose up -d --force-recreate
```

在 persistent profile 模式下：

```text
profile data
```

必须仍然存在。

在 ephemeral 模式下不做此保证。

---

# 43. Patch upgrade safety test

修改 / 升级 Playwright 版本后：

如果 patch script 无法安全识别 profile creation code：

```text
docker build
```

必须 FAIL。

例如：

```text
ERROR:
Unable to safely locate Playwright Firefox profile creation logic.
Playwright layout may have changed.
```

禁止构建出一个看似成功、实际 persistent profile 不工作的 image。

---

# 44. README

README 至少包含：

```text
项目简介
架构
Build
Run
WebUI URL
Playwright WebSocket
Ephemeral mode
Persistent mode
Profile volume
参数说明
安全说明
Troubleshooting
验证 profile 是否生效
```

提供验证命令：

```bash
docker compose exec camoufox \
    ps auxww | grep '[c]amoufox-bin'
```

ephemeral 应看到：

```text
-profile /tmp/...
```

persistent 应看到：

```text
-profile /data/camoufox-profile
```

---

# 45. Troubleshooting

README 必须包含以下情况。

## Profile 没生效

执行：

```bash
ps auxww | grep camoufox-bin
```

如果看到：

```text
-profile /tmp/playwright_firefoxdev_profile-*
```

说明 persistent patch 没进入实际 launch path。

不要仅通过：

```text
目录是否存在
```

判断。

---

## Profile 权限错误

检查：

```bash
ls -ld /data/camoufox-profile
id
```

Browser runtime user 必须可写。

---

## Selkies autostart 修改没有生效

说明：

Selkies：

```text
/defaults/autostart
```

只在第一次创建 `/config` 时复制。

已有：

```text
/config/.config/openbox/autostart
```

不会自动被 image 中的新 default 覆盖。([LinuxServer][1])

因此项目设计必须避免频繁修改 autostart 内容。

---

# 46. Definition of Done

只有下面所有条件满足才算完成：

```text
[ ] Docker image 从 baseimage-selkies 构建
[ ] 不包含 x11vnc
[ ] 不包含 noVNC
[ ] 不包含 websockify
[ ] 不使用 Apify baseimage

[ ] Selkies X11/Xfwm4 + Xfce Panel 模式正常
[ ] Camoufox headful 正常显示
[ ] 中文字体正常
[ ] Unicode clipboard 双向正常
[ ] Firefox extension popup 正常

[ ] Playwright Remote Server 可连接
[ ] 外部 Playwright 可创建 page / navigate / click

[ ] 默认使用临时 profile
[ ] persistent_context=True + user_data_dir 时才使用固定 profile
[ ] 两参数缺一时报错
[ ] persistent profile 不被 Playwright cleanup 删除
[ ] profile Docker volume 重建后仍存在
[ ] extension / cookie / prefs 能跨 container recreate

[ ] Playwright patch 有版本保护
[ ] patch idempotent
[ ] patch 失败时 Docker build 失败
[ ] unit tests 通过
[ ] integration tests 通过
[ ] README 完整
```

---

# 47. 实现优先级

实现时按以下阶段推进：

### Phase 1 — Selkies + Camoufox

先实现：

```text
Selkies
X11
Xfwm4
Xfce Panel
Camoufox headful
WebUI
```

验证：

```text
鼠标
键盘
中文 clipboard
popup
```

此阶段不要做 persistent patch。

### Phase 2 — Remote BrowserServer

实现：

```text
Camoufox launchServer
Playwright WebSocket
```

验证外部 Playwright connection。

### Phase 3 — Optional persistent profile

最后增加：

```text
persistent_context
user_data_dir
Python wrapper
Playwright profile patch
```

必须保证：

```text
关闭 persistent 功能后
行为与 upstream BrowserServer 一致
```

### Phase 4 — Tests / hardening

完成：

```text
unit tests
integration tests
Docker Compose examples
README
upgrade safety
```

---

# 48. 最重要的设计原则

实现过程中必须遵守：

```text
Selkies 负责 Desktop/WebUI
Camoufox 负责 Browser
Playwright 负责 Automation
本项目只扩展 BrowserServer 的 profile selection
```

不要重新实现：

```text
远程桌面
Clipboard
X server
Window manager
视频 streaming
```

这些全部交给 Selkies。

Profile patch 也必须尽量小：

```text
没有 persistent_context
    ↓
100% 使用 Playwright 原有 temporary profile

persistent_context=True
+
user_data_dir=/path
    ↓
仅把 Playwright 即将创建的 temporary userDataDir
替换成指定的固定 Firefox profile directory
```

除此以外：

```text
BrowserServer lifecycle
WebSocket protocol
Playwright connect()
Camoufox fingerprint
Camoufox launch options
```

全部保持上游行为。

---

## Reference context

LinuxServer Selkies 当前明确将 `/config` 作为持久化 surface，并建议 downstream GUI application 通过 `/defaults/autostart` 在 X11/Openbox 或 Wayland/labwc session 中启动。本项目的 `startwm.sh` 保留该 autostart 兼容路径，但实际使用 Xfwm4 和 Xfce Panel。([LinuxServer][1])

Camoufox 官方当前支持 in-process API：

```python
Camoufox(
    persistent_context=True,
    user_data_dir="/path/to/profile"
)
```

但 Playwright Server 模型不原生支持 persistent context；Camoufox 上游于 2026-08-20 合并的修改已经选择让 `launch_server()` 拒绝这两个参数，而不是继续静默忽略。([Camoufox][2])

本项目因此有意实现一个小型 compatibility extension：

```text
BrowserServer
+
fixed Firefox -profile
```

而不是试图把 `launchPersistentContext()` 直接塞进 Playwright BrowserServer。

[1]: https://docs.linuxserver.io/selkies/developer-guide/building-images/?utm_source=chatgpt.com "Building Custom Images - LinuxServer.io"
[2]: https://camoufox.com/python/usage/?utm_source=chatgpt.com "Usage | Camoufox"
[3]: https://github.com/daijro/camoufox/pull/707?utm_source=chatgpt.com "Lots of fixes + features by JWriter20 · Pull Request #707 · daijro/camoufox · GitHub"
[4]: https://github.com/daijro/camoufox/blob/main/pythonlib/camoufox/server.py?utm_source=chatgpt.com "camoufox/pythonlib/camoufox/server.py at main · daijro/camoufox · GitHub"
[5]: https://docs.linuxserver.io/selkies/developer-guide/?utm_source=chatgpt.com "Developer Guide - LinuxServer.io"
