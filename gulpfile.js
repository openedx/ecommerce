'use strict';

var gulp = require('gulp'),
    jscs = require('gulp-jscs'),
    jshint = require('gulp-jshint'),
    KarmaServer = require('karma').Server,
    path = require('path'),
    paths = {
        spec: [
            'ecommerce/static/js/**/*.js',
            'ecommerce/static/js/test/**/*.js',
            'ecommerce/static/templates/**/*.js'
        ],
        lint: [
            'build.js',
            'gulpfile.js',
            'ecommerce/static/js/**/*.js',
            'ecommerce/static/js/test/**/*.js'
        ],
        karamaConf: 'karma.conf.js'
    };

/**
 * Runs the JS unit tests
 */
gulp.task('test', function (cb) {
    new KarmaServer({
        configFile: path.resolve('karma.conf.js')
    }, cb).start();
});

/**
 * Runs the JSHint linter.
 *
 * http://jshint.com/about/
 */
gulp.task('lint', function () {
    return gulp.src(paths.lint)
        .pipe(jshint())
        .pipe(jshint.reporter('default'))
        .pipe(jshint.reporter('fail'));
});

/**
 * Runs the JavaScript Code Style (JSCS) linter.
 *
 * http://jscs.info/
 */
gulp.task('jscs', function () {
    return gulp.src(paths.lint)
        .pipe(jscs());
});

/**
 * Monitors the source and test files, running tests
 * and linters when changes detected.
 */
gulp.task('watch', function () {
    gulp.watch(paths.spec, ['test', 'lint', 'jscs']);
});

gulp.task('default', ['test']);
