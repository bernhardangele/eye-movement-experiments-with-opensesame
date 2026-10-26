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
USER ubuntu
WORKDIR /workspaces/experiments