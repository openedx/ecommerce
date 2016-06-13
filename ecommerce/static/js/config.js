require.config({
    baseUrl: '/static/',
    paths: {
        'backbone': 'bower_components/backbone/backbone',
        'backbone.relational': 'bower_components/backbone-relational/backbone-relational',
        'backbone.route-filter': 'bower_components/backbone-route-filter/backbone-route-filter',
        'backbone.stickit': 'bower_components/backbone.stickit/backbone.stickit',
        'backbone.super': 'bower_components/backbone-super/backbone-super/backbone-super',
        'backbone.validation': 'bower_components/backbone-validation/dist/backbone-validation-amd',
        'bootstrap': 'bower_components/bootstrap-sass/assets/javascripts/bootstrap',
        'bootstrap_accessibility': 'bower_components/bootstrapaccessibilityplugin/plugins/js/bootstrap-accessibility',
        'collections': 'js/collections',
        'datatables.net': 'bower_components/datatables/media/js/jquery.dataTables',
        'dataTablesBootstrap': 'bower_components/datatables/media/js/dataTables.bootstrap',
        'ecommerce': 'js/shims/ecommerce',
        'jquery': 'bower_components/jquery/dist/jquery',
        'js-cookie': 'bower_components/js-cookie/src/js.cookie',
        'models': 'js/models',
        'moment': 'bower_components/moment/moment',
        'pages': 'js/pages',
        'pikaday': 'bower_components/pikaday/pikaday',
        'requirejs': 'bower_components/requirejs/require',
        'routers': 'js/routers',
        'templates': 'templates',
        'test': 'js/test',
        'text': 'bower_components/text/text',
        'underscore': 'bower_components/underscore/underscore',
        'underscore.string': 'bower_components/underscore.string/dist/underscore.string',
        'utils': 'js/utils',
        'views': 'js/views'
    },
    shim: {
        bootstrap: {
            deps: ['jquery']
        },
        bootstrap_accessibility: {
            deps: ['bootstrap']
        },
        'datatables.net': {
            deps: ['jquery']
        },
        dataTablesBootstrap: {
            deps: ['jquery', 'datatables.net']
        },
        'pikaday': {
            deps: ['moment']
        }
    }
});
