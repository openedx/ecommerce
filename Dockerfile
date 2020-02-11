FROM ubuntu:xenial as openedx

RUN apt update && \
  apt install -qy git-core language-pack-en libmysqlclient-dev libssl-dev python3.5 python3-pip python3.5-dev && \
  pip3 install nodeenv && \
  pip3 install --upgrade pip setuptools && \
  rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/bin/pip3 /usr/bin/pip
RUN ln -s /usr/bin/python3 /usr/bin/python

RUN locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

# Create python venv
RUN mkdir -p /edx/app/ecommerce

# Install a recent version of nodejs
RUN nodeenv /openedx/nodeenv --node=8.9.3 --prebuilt
ENV PATH /openedx/nodeenv/bin:${PATH}

WORKDIR /edx/app/ecommerce

# Install ecommerce
COPY . /edx/app/ecommerce

# nodejs requirements
RUN npm install
RUN ./node_modules/.bin/bower install --allow-root

# python requirements
RUN pip install -r requirements.txt

RUN useradd -m --shell /bin/false app
USER app

EXPOSE 8000
CMD gunicorn -c /edx/app/ecommerce/ecommerce/docker_gunicorn_configuration.py --bind=0.0.0.0:8000 --workers 2 --max-requests=1000 ecommerce.wsgi:application

FROM openedx as edx.org
RUN pip install newrelic
CMD newrelic-admin run-program gunicorn -c /edx/app/ecommerce/ecommerce/docker_gunicorn_configuration.py --bind=0.0.0.0:8000 --workers 2 --max-requests=1000 ecommerce.wsgi:application
