var gulp = require('gulp'),
    KarmaServer = require('karma').Server,
    path = require('path');

gulp.task('test', function (cb) {
    new KarmaServer({
        configFile: path.resolve('karma.conf.js'),
    }, cb).start();
});

gulp.task('default', ['test']);
