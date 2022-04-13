FROM ubuntu:focal as app
MAINTAINER sre@edx.org

# Packages installed:
# git; Used to pull in particular requirements from github rather than pypi,
# and to check the sha of the code checkout.

# build-essentials; so we can use make with the docker container

# language-pack-en locales; ubuntu locale support so that system utilities have a consistent
# language and time zone.

# python; ubuntu doesnt ship with python, so this is the python we will use to run the application

# python3-pip; install pip to install application requirements.txt files

# libmysqlclient-dev; to install header files needed to use native C implementation for
# MySQL-python for performance gains.

# libssl-dev; # mysqlclient wont install without this.

# python3-dev; to install header files for python extensions; much wheel-building depends on this

# gcc; for compiling python extensions distributed with python packages like mysql-client

# If you add a package here please include a comment above describing what it is used for
RUN apt-get update && apt-get -qy install --no-install-recommends \
 language-pack-en \
 locales \
 python3.8 \
 python3-pip \
 libmysqlclient-dev \
 libssl-dev \
 python3-dev \
 gcc \
 build-essential \
 git


RUN pip install --upgrade pip setuptools
# delete apt package lists because we do not need them inflating our image
RUN rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/bin/python3 /usr/bin/python

RUN locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8
ENV DJANGO_SETTINGS_MODULE ecommerce.settings.production

# Env vars: configuration
ENV CONFIG_ROOT='/edx/etc'
ENV ECOMMERCE_CFG="$CONFIG_ROOT/ecommerce.yml"

EXPOSE 18130
EXPOSE 18131
RUN useradd -m --shell /bin/false app

# Create config directory. Create, define, and switch to working directory.
RUN mkdir -p "$CONFIG_ROOT"
WORKDIR /edx/app/ecommerce

# Copy the requirements explicitly even though we copy everything below
# this prevents the image cache from busting unless the dependencies have changed.
COPY requirements/production.txt /edx/app/ecommerce/requirements/production.txt

# Dependencies are installed as root so they cannot be modified by the application user.
RUN pip install -r requirements/production.txt


RUN mkdir -p /edx/var/log

# Code is owned by root so it cannot be modified by the application user.
# So we copy it before changing users.
USER app

# Gunicorn 19 does not log to stdout or stderr by default. Once we are past gunicorn 19, the logging to STDOUT need not be specified.
CMD gunicorn --workers=2 --name ecommerce -c /edx/app/ecommerce/ecommerce/docker_gunicorn_configuration.py --log-file - --max-requests=1000 ecommerce.wsgi:application


# This line is after the requirements so that changes to the code will not
# bust the image cache
COPY . /edx/app/ecommerce


##################################################
FROM app as newrelic
RUN pip install newrelic
CMD newrelic-admin run-program gunicorn --workers=2 --name ecommerce -c /edx/app/ecommerce/ecommerce/docker_gunicorn_configuration.py --log-file - --max-requests=1000 ecommerce.wsgi:application


##################################################
FROM app as ecommerce-docker
ARG ECOMMERCE_CFG_OVERRIDE
RUN echo "$ECOMMERCE_CFG_OVERRIDE"
ENV ECOMMERCE_CFG="${ECOMMERCE_CFG_OVERRIDE:-$ECOMMERCE_CFG}"
RUN echo "$ECOMMERCE_CFG"
ENV DJANGO_SETTINGS_MODULE="ecommerce.settings.docker-production"
RUN pip install edx-arch-experiments


##################################################
# Define an experimental docker target
# Setting user to root to allow for free range of your container
#
# Useful for testing config changes before going to production
FROM app as docker-experimental
ENV DJANGO_SETTINGS_MODULE="ecommerce.settings.docker-production"
RUN pip install edx-arch-experiments
USER root
RUN ln -s "$(pwd)/ecommerce/settings/docker-experimental.yml" "$ECOMMERCE_CFG"
