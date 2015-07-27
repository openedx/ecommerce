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
        config.baseUrl + 'js/test/specs/course_detail_view_spec.js'
    ];
} else {
    // gettext is normally loaded from Django. Add a shim so that tests continue to
    // function without having to run Django.
    if (!window.gettext) {
        window.gettext = function(text) {
            'use strict';
            return text;
        };
    }

    // Automatically load spec files
    for (var file in window.__karma__.files) {
        if (/spec\.js$/.test(file)) {
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
    //jasmine 2.0 needs boot.js to run, which loads on a window load, so this is
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
