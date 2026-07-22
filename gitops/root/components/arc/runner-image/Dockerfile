# Microscaler ARC runner image — extends official actions-runner with CI toolchain.
# Build/push (ms02):
#   just arc-runner-image-build
#
# Packages match the retired Multipass gha-runner host set so Rust/Python/Helm jobs work.
ARG RUNNER_VERSION=2.336.0
FROM ghcr.io/actions/actions-runner:${RUNNER_VERSION}

USER root
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential \
      pkg-config \
      libssl-dev \
      python3-pip \
      python3-venv \
      jq \
      uuid-runtime \
      mold \
      curl \
      git \
      ca-certificates \
 && (apt-get install -y --no-install-recommends docker-compose-plugin \
     || apt-get install -y --no-install-recommends docker-compose-v2) \
 && rm -rf /var/lib/apt/lists/*

USER runner
