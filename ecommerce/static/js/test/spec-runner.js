/**
 * This is where your tests go.  It should happen automatically when you
 * add files to the karma configuration.
 */

'use strict';

var specs = [],
    config = {};

// the E-Commerce application loads gettext identity library via django, thus
// components reference gettext globally so a shim is added here to reflect
// the text so tests can be run if modules reference gettext
if (!window.gettext) {
    window.gettext = function (text) {
        return text;
    };
}

// Establish the global namespace
window.ecommerce = window.ecommerce || {};
window.ecommerce.coupons = window.ecommerce.coupons || {};
window.ecommerce.credit = window.ecommerce.credit || {};

// you can automatically get the test files using karma's configs
for (var file in window.__karma__.files) {
    if (/js\/test\/specs\/.*spec\.js$/.test(file)) {
        specs.push(file);
    }
}

// This is where karma puts the files
config.baseUrl = '/base/ecommerce/static/';

// Karma lets you list the test files here
config.deps = specs;
config.callback = window.__karma__.start;

requirejs.config(config);
