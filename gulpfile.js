(function () {
    'use strict';

    var jshint = require('gulp-jshint'),
        gulp = require('gulp'),
        karma = require('karma').server,
        path = require('path'),
        browserSync = require('browser-sync'),
        jscs = require('gulp-jscs'),
        paths = {
            spec: [
                'static/js/**/*.js',
                'static/js/test/**/*.js'
            ],
            lint: [
                'build.js',
                'gulpfile.js',
                'static/js/**/*.js',
                'static/js/test/**/*.js'
            ],
            templates: [
                'templates/*.html'
            ],
            sass: ['static/sass/*.scss'],
            karamaConf: 'karma.conf.js'
        };

    // kicks up karma to the tests once
    function runKarma(configFile, cb) {
        karma.start({
            configFile: path.resolve(configFile),
            singleRun: true
        }, cb);
    }

    gulp.task('lint', function () {
        return gulp.src(paths.lint)
            .pipe(jshint())
            .pipe(jshint.reporter('default'))
            .pipe(jshint.reporter('fail'));
    });

    gulp.task('jscs', function () {
        return gulp.src(paths.lint)
            .pipe(jscs());
    });

    // this task runs the tests.  It doesn't give you very detailed results,
    // so you may need to run the jasmine test page directly:
    //      http://127.0.0.1:8000/static/js/test/spec-runner.html
    gulp.task('test', function (cb) {
        runKarma(paths.karamaConf, cb);
    });

    // these are the default tasks when you run gulp
    gulp.task('default', ['test', 'lint']);

    // type 'gulp watch' to continuously run linting and tests
    gulp.task('watch', function () {
        gulp.watch(paths.spec, ['test', 'lint']);
    });

    // Proxy to django server (assuming that we're using port 8000 and
    // localhost)
    gulp.task('browser-sync', function () {
        // there is a little delay before reloading b/c the sass files need to
        // recompile, but we can't necessarily watch the generated directory
        // because django creates a new css file that browser-sync doesn't
        // know of and I can't figure out how to make it watch an entire
        // directory
        browserSync.init(null, {
            proxy: 'localhost:9000',
            files: paths.lint.concat(paths.templates).concat(paths.sass),
            reloadDelay: 1000
        });
    });

}());
