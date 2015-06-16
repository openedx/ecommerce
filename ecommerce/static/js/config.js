require.config({
    baseUrl: '/static/',
    paths: {
        backbone: 'bower_components/backbone/backbone',
        bootstrap: 'bower_components/bootstrap-sass/assets/javascripts/bootstrap',
        bootstrap_accessibility: 'bower_components/bootstrapaccessibilityplugin/plugins/js/bootstrap-accessibility',
        dataTables: 'bower_components/datatables/media/js/jquery.dataTables',
        dataTablesBootstrap: 'vendor/dataTables/dataTables.bootstrap',
        jquery: 'bower_components/jquery/dist/jquery',
        'jquery-cookie': 'bower_components/jquery-cookie/jquery.cookie',
        requirejs: 'bower_components/requirejs/require',
        underscore: 'bower_components/underscore/underscore'
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
        },
    }
});
