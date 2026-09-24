# 使用与配置

## 构建镜像

默认 Compose 使用发布镜像 `wingao/docker-camoufox-selkies:latest`：

```bash
docker compose pull
docker compose up -d
```

开发时从当前代码本地构建：

```bash
docker compose -f docker-compose.dev.yml up --build -d
docker compose -f docker-compose.dev.yml build --no-cache
```

也可以使用根目录的 `justfile`：

```bash
just build
just build-no-cache
just push
TAG=v1.0.0 just build
```

默认镜像为 `wingao/docker-camoufox-selkies:latest`。可通过 `IMAGE`、`TAG`、`DEBIAN_MIRROR`、`DEBIAN_SECURITY_MIRROR` 和 `PIP_INDEX_URL` 覆盖镜像名、标签与软件源。

默认构建源如下：

| 参数 | 默认值 |
| --- | --- |
| `DEBIAN_MIRROR` | `https://mirrors.aliyun.com/debian` |
| `DEBIAN_SECURITY_MIRROR` | `https://mirrors.aliyun.com/debian-security` |
| `PIP_INDEX_URL` | `https://mirrors.aliyun.com/pypi/simple/` |

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `CAMOUFOX_PORT` | `1234` | 容器内 BrowserServer 端口 |
| `CAMOUFOX_HOST_PORT` | Compose 默认值 | 宿主机映射端口 |
| `CAMOUFOX_WS_PATH` | 空 | 固定 WebSocket path；为空时每次启动生成随机 path |
| `CAMOUFOX_PERSISTENT_CONTEXT` | `false` | 是否使用固定 profile |
| `CAMOUFOX_USER_DATA_DIR` | 空 | 固定 profile 的绝对路径 |
| `CAMOUFOX_DEBUG` | `false` | 输出诊断信息 |
| `CAMOUFOX_STARTUP_TIMEOUT` | `120` | 等待 endpoint 的秒数 |
| `PIXELFLUX_WAYLAND` | `false` | 必须保持为 `false`，项目使用 X11 |
| `PUID` / `PGID` | `1000` | LinuxServer 运行用户映射 |

例如修改容器和宿主机端口：

```bash
CAMOUFOX_PORT=4321 CAMOUFOX_HOST_PORT=14321 docker compose up -d
```

profile 参数必须成对使用：`false + 空 user_data_dir` 表示临时 profile，`true + 绝对 user_data_dir` 表示持久化 profile。路径不存在、不可写或使用相对路径都会使启动失败。

## 持久化 profile

默认 `./config:/config` 只保存 Selkies 桌面配置。持久化 compose 使用 `./camoufox-profile:/data/camoufox-profile`，端口为 `11040`、`11041` 和 `11042`。不要使用 `docker compose ... down -v`。

如需使用其他 bind mount：

```bash
mkdir -p profile
sudo chown 1000:1000 profile
chmod 700 profile
```

一个 Firefox profile 同时只能由一个 Camoufox 实例使用。

## Remote Playwright

endpoint 会写入日志和 `/config/.cache/camoufox-server/ws_endpoint`：

```bash
docker compose logs camoufox | grep '\[camoufox\] websocket='
```

固定 path：

```bash
CAMOUFOX_WS_PATH=/agents/camoufox docker compose up -d
```

path 不是认证凭据；不要把未认证的 Playwright 服务直接暴露到公网。跨主机访问应使用受控网络、VPN 或具备认证和 TLS 的反向代理。客户端应使用与容器相同主次版本的 Playwright。

也可以直接调用容器内 CLI：

```bash
XDG_CACHE_HOME=/opt /opt/camoufox-venv/bin/python /app/server_entrypoint.py --port 1234
XDG_CACHE_HOME=/opt /opt/camoufox-venv/bin/python /app/server_entrypoint.py \
  --port 1234 --ws-path /agents/camoufox \
  --persistent-context --user-data-dir /data/camoufox-profile
```

## 安全

Selkies basic auth 适用于可信网络，不应视为公网网关。若将端口绑定到 `0.0.0.0`，至少设置 `CUSTOM_USER` 和 `PASSWORD`，并建议使用认证反向代理。

宿主机 seccomp 阻止 Firefox syscall 时，可在可信环境中临时尝试：

```yaml
security_opt:
  - seccomp=unconfined
```

该选项会降低隔离强度，不应默认启用。

## 故障排查

```bash
docker compose ps
docker compose logs camoufox
docker compose exec camoufox ps auxww | grep '[c]amoufox-bin'
```

默认模式应看到 `/tmp/playwright_firefoxdev_profile-*`，持久化模式应看到 `/data/camoufox-profile`。仅检查目录存在不能证明 Firefox 正在使用该目录；必要时设置 `CAMOUFOX_DEBUG=true` 并无缓存重建。

Selkies 只会在首次创建 `/config` 时复制默认 autostart。恢复默认 Xfce 布局前请备份配置，再删除 `/config/.config/xfce4` 并重启容器，这不会删除 Firefox profile。

中文剪贴板需要使用 HTTPS 3001、允许浏览器剪贴板权限，并保持 `LANG=C.UTF-8`、`LC_ALL=C.UTF-8` 与 X11 模式。
