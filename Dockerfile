# syntax=docker/dockerfile:1
FROM ghcr.io/linuxserver/baseimage-selkies:debiantrixie

ARG DEBIAN_MIRROR=https://mirrors.aliyun.com/debian
ARG DEBIAN_SECURITY_MIRROR=https://mirrors.aliyun.com/debian-security
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PIXELFLUX_WAYLAND=false \
    GDK_BACKEND=x11 \
    MOZ_ENABLE_WAYLAND=0 \
    CAMOUFOX_PORT=1234 \
    CAMOUFOX_PERSISTENT_CONTEXT=false \
    START_DOCKER=false \
    TITLE=Camoufox

RUN set -eux; \
    rm -f /etc/apt/sources.list.d/docker.* /etc/apt/sources.list.d/nodesource.*; \
    for source in /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources; do \
        if [ -f "$source" ]; then \
            sed -i \
                -e "s|https\?://deb.debian.org/debian-security|${DEBIAN_SECURITY_MIRROR}|g" \
                -e "s|https\?://security.debian.org/debian-security|${DEBIAN_SECURITY_MIRROR}|g" \
                -e "s|https\?://deb.debian.org/debian|${DEBIAN_MIRROR}|g" \
                "$source"; \
        fi; \
    done; \
    apt-get update; \
    apt-get install --no-install-recommends -y \
        ca-certificates \
        fonts-noto-cjk \
        fonts-noto-color-emoji \
        libasound2t64 \
        libdbus-glib-1-2 \
        libgtk-3-0t64 \
        libnss3 \
        python3 \
        python3-xdg \
        python3-venv; \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN set -eux; \
    python3 -m venv /opt/camoufox-venv; \
    /opt/camoufox-venv/bin/pip install --upgrade pip; \
    /opt/camoufox-venv/bin/pip install camoufox==0.5.5

COPY scripts /tmp/camoufox-scripts
RUN set -eux; \
    mkdir -p /opt/camoufox /data/camoufox-profile; \
    chmod 0777 /data/camoufox-profile; \
    XDG_CACHE_HOME=/opt /opt/camoufox-venv/bin/python \
        /tmp/camoufox-scripts/fetch_camoufox_browser.py

RUN set -eux; \
    /opt/camoufox-venv/bin/pip install -r /tmp/requirements.txt; \
    rm /tmp/requirements.txt

RUN set -eux; \
    XDG_CACHE_HOME=/opt /opt/camoufox-venv/bin/python /tmp/camoufox-scripts/install_camoufox_browser.py; \
    /opt/camoufox-venv/bin/python /tmp/camoufox-scripts/configure_camoufox_policies.py; \
    /opt/camoufox-venv/bin/python /tmp/camoufox-scripts/patch_playwright_profile.py \
        --record-path /opt/camoufox/playwright-patch-path; \
    find /opt/camoufox-venv -name '*.pre-camoufox-patch' -delete; \
    rm -rf /tmp/camoufox-scripts; \
    test -x /opt/camoufox/browser/camoufox-bin; \
    test -s /opt/camoufox/browser-manifest.json; \
    test -s /opt/camoufox/playwright-patch-path

COPY --chmod=0755 root/ /
COPY --chmod=0755 scripts/configure_camoufox_policies.py /usr/local/bin/configure-camoufox-policies
COPY --chown=root:root app/ /app/
RUN set -eux; \
    NODE="$(/opt/camoufox-venv/bin/python -c 'from playwright._impl._driver import compute_driver_executable; print(compute_driver_executable()[0])')"; \
    "$NODE" --check /app/launch_server.js; \
    /opt/camoufox-venv/bin/python -m compileall -q /app

EXPOSE 3000 3001 1234
VOLUME /config
