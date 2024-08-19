# Check github.com/prefix-dev/pixi/blob/main/example/docker-build/pixi.toml
FROM ubuntu:latest

# Install curl and tar to install pixi bin
RUN apt update && \
    apt install -y curl tar

# Environment variables
ENV PIXI_VERSION=latest
ENV INSTALL_DIR=/usr/local/bin
ENV PIXI_REPO=prefix-dev/pixi
ENV PLATFORM=unknown-linux-musl
ENV PROJECT_NAME=gee-data-fetcher
ENV DEFAULT_ARGS="--help"

# Install pixi
RUN if [ "$PIXI_VERSION" = "latest" ]; then \
        DOWNLOAD_URL="https://github.com/$PIXI_REPO/releases/latest/download/pixi-$(uname -m)-$PLATFORM.tar.gz"; \
    else \
        DOWNLOAD_URL="https://github.com/$PIXI_REPO/releases/download/$PIXI_VERSION/pixi-$(uname -m)-$PLATFORM.tar.gz"; \
    fi && \
    curl -SL "$DOWNLOAD_URL" | tar -xz -C "$INSTALL_DIR"

# Setup project dir
RUN mkdir -p /root/$PROJECT_NAME
WORKDIR /root/$PROJECT_NAME

# Copy pixi project file and lockfile
COPY ./pixi.lock ./pixi.toml ./

# Install the environment
RUN --mount=type=cache,target=/root/.cache/rattler pixi install

# Copy remaining files
COPY ./gee_data_fetcher ./

# RUN pixi run install

# Script entry
CMD pixi run cmd ${ARGS:-${DEFAULT_ARGS}}
