# 开发与实现

## 代码结构

```text
app/                         BrowserServer launcher 和 Playwright 集成
scripts/                     浏览器下载、安装、策略和 Playwright patch
root/                        LinuxServer 启动脚本、autostart 和容器初始化
tests/                       单元测试与 smoke test
Dockerfile                   镜像构建和运行时依赖
docker-compose*.yml          默认与持久化部署配置
justfile                     镜像构建和推送命令
```

## 构建流程

镜像基于 `ghcr.io/linuxserver/baseimage-selkies:debiantrixie`，安装 Xfwm4、Xfce Panel、Python 和 Camoufox。构建时通过 Camoufox 官方 package fetch API 下载 browser bundle，将浏览器固定到 `/opt/camoufox/browser/camoufox-bin`，然后严格 patch 实际安装的 Playwright driver。

构建会检查浏览器可执行文件、browser manifest、patch 路径、Node 语法和 Python 字节码。只下载浏览器，不在构建时访问 Mozilla 下载可选扩展；profile 逻辑无法唯一识别或校验失败时直接终止构建。

## 本地验证

```bash
python3 -m unittest discover -v
python3 tests/smoke/connect.py 'ws://127.0.0.1:1234/<id>'
```

持久化状态测试：

```bash
python3 tests/smoke/persistence.py write 'ws://127.0.0.1:1234/<id>'
docker compose -f docker-compose.persistent.yml down
docker compose -f docker-compose.persistent.yml up -d
python3 tests/smoke/persistence.py verify 'ws://127.0.0.1:1234/<new-id>'
```

## WebUI 人工验收

在真实浏览器打开 `https://localhost:3001`，确认：

1. Firefox 窗口可见，刷新、鼠标、滚轮和键盘正常。
2. `你好，Camoufox 中文测试 😀 123` 可以从本机复制到 Firefox，内容逐字一致。
3. `Camoufox 反向复制测试 中文 🚀` 可以从远端复制到本机，内容逐字一致。
4. 中文网页、Emoji 和 Firefox 原生菜单显示正常。
5. 带 browserAction popup 的扩展可以打开，鼠标移入后 popup 仍保持打开且内部元素可点击。

## 设计约束

BrowserServer 使用 Playwright shared BrowserServer 分支，WebUI 中的长期 Firefox context 与远程 Agent 连接看到的是同一 context。客户端应复用 `browser.contexts[0]`，不要关闭这个长期 context，否则持久化页面、cookie 和登录状态无法跨连接保留。

项目依赖 LinuxServer Selkies 提供 patched Xvfb、输入、音频、视频和剪贴板能力；不要在应用层重新启动 Xvfb，也不要引入 x11vnc、noVNC、websockify 或 Wayland。
