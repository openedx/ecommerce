/**
 * This is where your tests go.  It should happen automatically when you
 * add files to the karma configuration.
 */

var isBrowser = window.__karma__ === undefined,
    specs = [],
    config = {};

// Two execution paths: browser or gulp
if (isBrowser) {
    // The browser cannot read directories, so all files must be enumerated below.
    specs = [
        config.baseUrl + 'js/test/specs/test_spec.js'
    ];
} else {
    // the E-Commerce application loads gettext identity library via django, thus
    // components reference gettext globally so a shim is added here to reflect
    // the text so tests can be run if modules reference gettext
    if (!window.gettext) {
        window.gettext = function(text) {
            'use strict';
            return text;
        };
    }

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
}

requirejs.config(config);

// the browser needs to kick off jasmine.  The gulp task does it through
// node
if (isBrowser) {
    // jasmine 2.0 needs boot.js to run, which loads on a window load, so this is
    // a hack
    // http://stackoverflow.com/questions/19240302/does-jasmine-2-0-really-not-work-with-require-js
    require(['boot'], function () {
        'use strict';
        require(specs,
            function () {
                window.onload();
            });
    });
}
