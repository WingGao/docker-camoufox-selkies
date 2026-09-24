set shell := ["bash", "-euo", "pipefail", "-c"]

image := env_var_or_default("IMAGE", "wingao/docker-camoufox-selkies")
tag := env_var_or_default("TAG", "latest")
debian_mirror := env_var_or_default("DEBIAN_MIRROR", "https://mirrors.aliyun.com/debian")
debian_security_mirror := env_var_or_default("DEBIAN_SECURITY_MIRROR", "https://mirrors.aliyun.com/debian-security")
pip_index_url := env_var_or_default("PIP_INDEX_URL", "https://mirrors.aliyun.com/pypi/simple/")

default:
    @just --list

build:
    docker build \
        --tag "{{image}}:{{tag}}" \
        --build-arg "DEBIAN_MIRROR={{debian_mirror}}" \
        --build-arg "DEBIAN_SECURITY_MIRROR={{debian_security_mirror}}" \
        --build-arg "PIP_INDEX_URL={{pip_index_url}}" \
        .

build-no-cache:
    docker build --no-cache \
        --tag "{{image}}:{{tag}}" \
        --build-arg "DEBIAN_MIRROR={{debian_mirror}}" \
        --build-arg "DEBIAN_SECURITY_MIRROR={{debian_security_mirror}}" \
        --build-arg "PIP_INDEX_URL={{pip_index_url}}" \
        .

push: build
    docker push "{{image}}:{{tag}}"
