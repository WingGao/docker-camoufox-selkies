# docker-camoufox-selkies

基于 LinuxServer Selkies 的 Docker 化 Camoufox/Firefox 浏览器环境，提供可通过 WebUI 操作的 X11 桌面、Playwright WebSocket 远程控制和可选的持久化 profile。

## 项目架构

```text
浏览器 ── HTTPS :3001 ──> Selkies ──> X11/Xfwm4 + Xfce Panel ──> Camoufox/Firefox
外部 Agent ── WebSocket :1234 ──> Playwright BrowserServer ──> Camoufox/Firefox
```

- Selkies 提供浏览器桌面、视频、音频、键鼠输入、Unicode 剪贴板和 Nginx。
- X11 会话使用 `xfwm4` 管理窗口，使用 `xfce4-panel` 提供任务栏、窗口按钮和工作区切换。
- Camoufox 通过官方 Python package 安装；BrowserServer 与 WebUI 中的 Firefox 共享同一个长期 context。
- 项目使用 LinuxServer 的 patched Xvfb，不自行启动 Xvfb，也不使用 x11vnc、noVNC、websockify 或 Wayland。

## 快速开始

### 构建并启动

默认模式使用临时 Firefox profile，容器重建后不会保留浏览器登录状态：

```bash
docker compose pull
docker compose up -d
docker compose logs -f camoufox
```

默认使用镜像 `wingao/docker-camoufox-selkies:latest`。需要从当前代码本地构建时，使用 [`docker-compose.dev.yml`](docker-compose.dev.yml)：

```bash
docker compose -f docker-compose.dev.yml up --build -d
```

启动后访问：

```text
WebUI:      https://localhost:3001
HTTP:       http://localhost:3000
WebSocket:  127.0.0.1:1234
```

3001 使用容器生成的 HTTPS 证书，首次访问时浏览器可能提示自签名证书。默认端口只绑定宿主机 loopback，不会直接监听所有网卡。

### 持久化运行

需要保留页面、cookie 和登录状态时，使用持久化 compose：

```bash
docker compose -f docker-compose.persistent.yml up -d
docker compose -f docker-compose.persistent.yml logs -f camoufox
```

该配置将 profile 保存到 `./camoufox-profile`，端口为 `11040`（HTTP）、`11041`（WebUI）和 `11042`（WebSocket）。停止或重建容器不会删除 profile；不要使用 `docker compose ... down -v`。

一个 Firefox profile 同一时间只能由一个 Camoufox 实例使用。需要运行多个实例时，请为每个实例使用不同的 profile 目录。

### 连接远程 Playwright

启动日志会输出完整的动态 endpoint：

```text
[camoufox] websocket=ws://0.0.0.0:1234/<id>
```

连接时把 `0.0.0.0` 替换为 Docker 主机地址，并优先复用 `browser.contexts[0]`：

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

完整配置、endpoint 管理、安全说明和故障排查见 [`docs/usage.md`](docs/usage.md)。

## 文档索引

- [`docs/usage.md`](docs/usage.md)：Docker 配置、持久化、远程 Playwright、安全和故障排查。
- [`docs/development.md`](docs/development.md)：构建参数、实现结构、测试和开发说明。

## 开发

开发、构建和验证相关内容统一放在 [`docs/development.md`](docs/development.md)，包括代码目录、镜像构建流程、单元测试、smoke test 和 WebUI 人工验收步骤。
