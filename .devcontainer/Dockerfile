# Workshop image: the OpenSesame/PyGaze test container plus Quarto (for the slides).
FROM bangele1/opensesame-test-container:latest
USER root
ARG QUARTO_VERSION=1.5.57
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && ARCH="$(dpkg --print-architecture)" \
    && curl -fsSL -o /tmp/quarto.deb \
       "https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VERSION}/quarto-${QUARTO_VERSION}-linux-${ARCH}.deb" \
    && apt-get install -y /tmp/quarto.deb \
    && rm -rf /tmp/quarto.deb /var/lib/apt/lists/*
# Headless Chromium + Playwright for checking the rendered slides
# (slides/check_slides.py): a separate venv, so the OpenSesame venv is untouched.
ARG PLAYWRIGHT_VERSION=1.64.1
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright
RUN apt-get update && apt-get install -y --no-install-recommends python3-venv \
    && python3 -m venv /opt/slides-check \
    && /opt/slides-check/bin/pip install --no-cache-dir "playwright==${PLAYWRIGHT_VERSION}" pillow \
    && /opt/slides-check/bin/playwright install --with-deps chromium \
    && chmod -R a+rX /opt/ms-playwright \
    && rm -rf /var/lib/apt/lists/*
USER ubuntu
WORKDIR /workspaces/experiments