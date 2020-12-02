#!/bin/bash -xe
. /edx/app/ecommerce/venvs/ecommerce/bin/activate
cd /edx/app/ecommerce/ecommerce
coverage xml
