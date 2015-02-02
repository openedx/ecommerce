// Karma configuration
// Generated on Thu Jun 26 2014 17:49:39 GMT-0400 (EDT)

module.exports = function (config) {
    config.set({

        // base path that will be used to resolve all patterns (eg. files, exclude)
        basePath: '',


        // frameworks to use
        // available frameworks: https://npmjs.org/browse/keyword/karma-adapter
        frameworks: ['jasmine', 'requirejs', 'sinon'],


        // list of files / patterns to load in the browser
        files: [
            {pattern: 'static/vendor/**/*.js', included: false},
            {pattern: 'static/bower_components/**/*.js', included: false},
            {pattern: 'static/bower_components/**/*.json', included: false},
            {pattern: 'static/js/models/**/*.js', included: false},
            {pattern: 'static/js/views/**/*.js', included: false},
            {pattern: 'static/js/utils/**/*.js', included: false},
            {pattern: 'static/js/test/specs/*.js', included: false},
            'static/js/config.js',
            'static/js/test/spec-runner.js'
        ],


        // preprocess matching files before serving them to the browser
        // available preprocessors: https://npmjs.org/browse/keyword/karma-preprocessor
        preprocessors: {
            'static/js/models/**/*.js': ['coverage'],
            'static/js/views/**/*.js': ['coverage'],
            'static/js/utils/**/*.js': ['coverage']
        },

        // plugins required for running the karma tests
        plugins:[
            'karma-jasmine',
            'karma-requirejs',
            'karma-phantomjs-launcher',
            'karma-coverage',
            'karma-sinon'
        ],

        // test results reporter to use
        // possible values: 'dots', 'progress'
        // available reporters: https://npmjs.org/browse/keyword/karma-reporter
        reporters: ['progress', 'coverage'],

        coverageReporter: {
            dir:'build', subdir: 'coverage-js',
            reporters:[
                {type: 'html', subdir: 'coverage-js/html'},
                {type: 'cobertura', file: 'coverage.xml'},
                {type: 'text-summary'}
            ]
        },

        // web server port
        port: 9876,


        // enable / disable colors in the output (reporters and logs)
        colors: true,


        // level of logging
        // possible values: config.LOG_DISABLE || config.LOG_ERROR || config.LOG_WARN || config.LOG_INFO || config.LOG_DEBUG
        logLevel: config.LOG_INFO,


        // enable / disable watching file and executing tests whenever any file changes
        autoWatch: true,


        // start these browsers
        // available browser launchers: https://npmjs.org/browse/keyword/karma-launcher
        // you can also add Chrome or other browsers too
        browsers: ['PhantomJS'],

        captureTimeout: 60000,

        // Continuous Integration mode
        // if true, Karma captures browsers, runs the tests and exits
        singleRun: false
    });
};
