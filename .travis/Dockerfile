FROM edxops/ecommerce:latest

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
        firefox \
        xvfb \
    && rm -rf /var/lib/apt/lists/*
