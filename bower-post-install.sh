#!/usr/bin/env bash

# This hack is necessary since edx-ux-pattern-library is not a bower package, but our SASS files only have access
# to bower packages (instead of node modules).
cp -r ./node_modules/edx-ux-pattern-library ecommerce/static/bower_components
