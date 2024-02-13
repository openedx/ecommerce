FROM ubuntu:focal as app

ENV DEBIAN_FRONTEND noninteractive
# System requirements.
RUN apt update && \
  apt-get install -qy \ 
  curl \
  git \
  language-pack-en \
  build-essential \
  python3.8-dev \
  python3-virtualenv \
  python3.8-distutils \
  libmysqlclient-dev \
  libssl-dev \
  libcairo2-dev && \
  rm -rf /var/lib/apt/lists/*

# Use UTF-8.
RUN locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

ARG COMMON_APP_DIR="/edx/app"
ARG COMMON_CFG_DIR="/edx/etc"
ARG SERVICE_NAME="ecommerce"
ARG ECOMMERCE_APP_DIR="${COMMON_APP_DIR}/${SERVICE_NAME}"
ARG ECOMMERCE_VENV_DIR="${COMMON_APP_DIR}/${SERVICE_NAME}/venvs/${SERVICE_NAME}"
ARG ECOMMERCE_CODE_DIR="${ECOMMERCE_APP_DIR}/${SERVICE_NAME}"
ARG ECOMMERCE_NODEENV_DIR="${ECOMMERCE_APP_DIR}/nodeenvs/${SERVICE_NAME}"

ENV ECOMMERCE_CFG "${COMMON_CFG_DIR}/ecommerce.yml"
ENV ECOMMERCE_CODE_DIR "${ECOMMERCE_CODE_DIR}"
ENV ECOMMERCE_APP_DIR "${ECOMMERCE_APP_DIR}"

# Add virtual env and node env to PATH, in order to activate them
ENV PATH "${ECOMMERCE_VENV_DIR}/bin:${ECOMMERCE_NODEENV_DIR}/bin:$PATH"

RUN virtualenv -p python3.8 --always-copy ${ECOMMERCE_VENV_DIR}

RUN pip install nodeenv

RUN nodeenv ${ECOMMERCE_NODEENV_DIR} --node=16.14.0 --prebuilt && npm install -g npm@8.5.x

# Set working directory to the root of the repo
WORKDIR ${ECOMMERCE_CODE_DIR}

# Install JS requirements
COPY package.json package.json
COPY package-lock.json package-lock.json
COPY bower.json bower.json
RUN npm install --production && ./node_modules/.bin/bower install --allow-root --production

# Expose canonical ecommerce port
EXPOSE 18130

FROM app as prod

ENV DJANGO_SETTINGS_MODULE "ecommerce.settings.production"

COPY requirements/production.txt ${ECOMMERCE_CODE_DIR}/requirements/production.txt

RUN pip install -r ${ECOMMERCE_CODE_DIR}/requirements/production.txt

# Copy over rest of code.
# We do this AFTER requirements so that the requirements cache isn't busted
# every time any bit of code is changed.
COPY . .

CMD gunicorn --bind=0.0.0.0:18130 --workers 2 --max-requests=1000 -c ecommerce/docker_gunicorn_configuration.py ecommerce.wsgi:application

FROM app as dev

ENV DJANGO_SETTINGS_MODULE "ecommerce.settings.devstack"

COPY requirements/dev.txt ${ECOMMERCE_CODE_DIR}/requirements/dev.txt

RUN pip install -r ${ECOMMERCE_CODE_DIR}/requirements/dev.txt

# Devstack related step for backwards compatibility
RUN touch ${ECOMMERCE_APP_DIR}/ecommerce_env

# Copy over rest of code.
# We do this AFTER requirements so that the requirements cache isn't busted
# every time any bit of code is changed.
COPY . .

CMD while true; do python ./manage.py runserver 0.0.0.0:18130; sleep 2; done
