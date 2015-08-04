require.config({
    baseUrl: '/static/',
    paths: {
        'backbone': 'bower_components/backbone/backbone',
        'backbone-relational': 'bower_components/backbone-relational/backbone-relational',
        'backbone-super': 'bower_components/backbone-super/backbone-super/backbone-super',
        'backbone-validation': 'bower_components/backbone-validation/dist/backbone-validation-amd',
        'backbone.paginator': 'bower_components/backbone.paginator/lib/backbone.paginator',
        'backbone.stickit': 'bower_components/backbone.stickit/backbone.stickit',
        'bootstrap': 'bower_components/bootstrap-sass/assets/javascripts/bootstrap',
        'bootstrap_accessibility': 'bower_components/bootstrapaccessibilityplugin/plugins/js/bootstrap-accessibility',
        'collections': 'js/collections',
        'dataTables': 'bower_components/datatables/media/js/jquery.dataTables',
        'dataTablesBootstrap': 'vendor/dataTables/dataTables.bootstrap',
        'jquery': 'bower_components/jquery/dist/jquery',
        'jquery-cookie': 'bower_components/jquery-cookie/jquery.cookie',
        'models': 'js/models',
        'moment': 'bower_components/moment/moment',
        'requirejs': 'bower_components/requirejs/require',
        'templates': 'templates',
        'text': 'bower_components/text/text',
        'underscore': 'bower_components/underscore/underscore',
        'underscore.string': 'bower_components/underscore.string/dist/underscore.string',
        'views': 'js/views'
    },
    shim: {
        bootstrap: {
            deps: ['jquery']
        },
        bootstrap_accessibility: {
            deps: ['bootstrap']
        },
        dataTables: {
            deps: ['jquery']
        },
        dataTablesBootstrap: {
            deps: ['jquery', 'dataTables']
        },
        'jquery-cookie': {
            deps: ['jquery']
        }
    }
});
