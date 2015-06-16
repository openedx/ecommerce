/* jshint asi:true, expr:true */
({
    mainConfigFile: 'ecommerce/static/js/config.js',
    baseUrl: 'ecommerce/static',
    dir: 'ecommerce/static/build',
    removeCombined: true,
    findNestedDependencies: true,

    // Disable all optimization. django-compressor will handle that for us.
    optimizeCss: false,
    optimize: 'none',
    normalizeDirDefines: 'all',
    skipDirOptimize: true,

    preserveLicenseComments: true,
    modules: [
        {
            name: 'js/common'
        },
        {
            name: 'js/config'
        },
        // Example module
        //{
        //    name: 'js/engagement-content-main',
        //
        //    // Always exclude js/common since it should be included in the base template.
        //    exclude: ['js/common']
        //}
    ]
})
