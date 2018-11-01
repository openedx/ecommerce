FROM edxops/ecommerce:latest

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
        firefox \
        xvfb \
    # Remove firefox but leave its dependencies, and then download and install a working version of firefox.
    # Note: wget only required for firefox retrieval.
        wget \
    && sudo dpkg -r --force-all firefox && TEMP_DEB="$(mktemp)" && wget -O "$TEMP_DEB" https://s3.amazonaws.com/vagrant.testeng.edx.org/firefox_61.0.1%2Bbuild1-0ubuntu0.16.04.1_amd64.deb && dpkg -i "$TEMP_DEB" \
    && rm -rf /var/lib/apt/lists/*
