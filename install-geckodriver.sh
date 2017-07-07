#!/bin/bash
set -e
# Download geckodriver from Github.

if [ -f "geckodriver" ]; then
    echo "geckodriver is already installed"
    exit 0
fi

tag="v0.17.0"
platform="linux64"

if [[ $(uname) == "Darwin" ]]; then
    platform="macos"
    url="https://github.com/mozilla/geckodriver/releases/download/$tag/geckodriver-$tag-linux64.tar.gz"
fi

url="https://github.com/mozilla/geckodriver/releases/download/$tag/geckodriver-$tag-$platform.tar.gz"
curl -s -L "$url" | tar -xz
chmod +x geckodriver
echo "Installed geckodriver"
