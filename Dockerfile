# To build this Dockerfile:
#
# From the e2e folder of the ecommerce repository:
#
# docker build . -t edxops/e2e-ecommerce:latest

FROM python:3.8-slim
MAINTAINER edxops

# Install system libraries needed for lxml
RUN apt-get update -qqy \
    && apt-get -qqy install \
    libxml2-dev \
    libxslt1-dev \
    make \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/*

ADD . /edx-e2e-tests
WORKDIR /edx-e2e-tests

# Install requirements and pages
# Deletes the edx-platform checkout afterwards, it will be mapped in from the host
RUN pip install -r requirements.txt

# Just wait for the user to launch a shell when started via docker-compose
CMD ["sleep", "infinity"]
