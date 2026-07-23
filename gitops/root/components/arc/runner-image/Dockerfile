# Microscaler ARC runner image — extends official actions-runner with CI toolchain.
# Build/push (ms02):
#   just arc-runner-image-build
#   just arc-runner-rollout
#
# Tooling inventory driven by octopilot/actions (lint/test/setup-tools):
#   docker compose plugin, helm, mold, pkg-config, libssl-dev,
#   python3-full + pipx + pre-commit (PEP 668 — never pip install --user on
#   system Python), build-essential.
#
# Official actions-runner ships docker CLI + buildx under
# /usr/local/lib/docker/cli-plugins/. Apt docker-compose-v2 does NOT register
# there — install the Compose GitHub release binary next to buildx.
ARG RUNNER_VERSION=2.336.0
ARG COMPOSE_VERSION=v2.40.3
ARG HELM_VERSION=v3.16.4

FROM ghcr.io/actions/actions-runner:${RUNNER_VERSION}

USER root
ENV DEBIAN_FRONTEND=noninteractive
# pipx installs CLI apps system-wide for all jobs (pre-commit on PATH).
ENV PIPX_HOME=/opt/pipx
ENV PIPX_BIN_DIR=/usr/local/bin

ARG COMPOSE_VERSION
ARG HELM_VERSION

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential \
      pkg-config \
      libssl-dev \
      python3-full \
      python3-pip \
      python3-venv \
      pipx \
      jq \
      uuid-runtime \
      mold \
      curl \
      git \
      ca-certificates \
      unzip \
 && rm -rf /var/lib/apt/lists/*

# Docker Compose v2 CLI plugin (same path as stock buildx).
RUN mkdir -p /usr/local/lib/docker/cli-plugins \
 && curl -fsSL \
      "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-x86_64" \
      -o /usr/local/lib/docker/cli-plugins/docker-compose \
 && chmod +x /usr/local/lib/docker/cli-plugins/docker-compose \
 && ln -sf /usr/local/lib/docker/cli-plugins/docker-compose /usr/local/bin/docker-compose \
 && docker compose version

# Helm 3 (pinned; matches octopilot/actions lint+test install scripts).
RUN curl -fsSL "https://get.helm.sh/helm-${HELM_VERSION}-linux-amd64.tar.gz" \
      | tar -xz -C /tmp \
 && install -m 0755 /tmp/linux-amd64/helm /usr/local/bin/helm \
 && rm -rf /tmp/linux-amd64 \
 && helm version --short

# pre-commit via pipx — avoids PEP 668 externally-managed-environment on
# Ubuntu 24.04 system Python (octopilot/actions lint Install pre-commit step).
RUN mkdir -p "${PIPX_HOME}" \
 && pipx install pre-commit \
 && pre-commit --version \
 && python3 -m venv --help >/dev/null

USER runner
