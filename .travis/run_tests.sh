#!/bin/bash -xe
. /edx/app/ecommerce/venvs/ecommerce/bin/activate
. /edx/app/ecommerce/nodeenvs/ecommerce/bin/activate

apt update
apt install -y xvfb firefox gettext

cd /edx/app/ecommerce/ecommerce

# Make it so bower can run without sudo.
# https://github.com/GeoNode/geonode/pull/1070
echo '{ "allow_root": true }' > /root/.bowerrc

make requirements

# Ensure documentation can be compiled
cd docs && make html
cd ..

export DJANGO_SETTINGS_MODULE=ecommerce.settings.test

# Check if translation files are up-to-date
make validate_translations

# Compile assets and run validation
make clean_static
make static
xvfb-run make validate_python
xvfb-run make validate_js
