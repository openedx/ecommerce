var gulp = require('gulp'),
    eslint = require('gulp-eslint'),
    KarmaServer = require('karma').Server,
    path = require('path');

(function() {
    'use strict';

    var paths = {
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
    gulp.task('test', function(cb) {
        new KarmaServer({
            configFile: path.resolve('karma.conf.js')
        }, cb).start();
    });

/**
 * Runs the ESLint linter.
 *
 * http://eslint.org/docs/about/
 */
    gulp.task('lint', function() {
        return gulp.src(paths.lint)
        .pipe(eslint())
        .pipe(eslint.format())
        .pipe(eslint.failAfterError());
    });

/**
 * Monitors the source and test files, running tests
 * and linters when changes detected.
 */
    gulp.task('watch', function() {
        gulp.watch(paths.spec, ['test', 'lint']);
    });

    gulp.task('default', gulp.series('test'));
}());
