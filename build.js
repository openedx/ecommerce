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
        {
            name: 'js/pages/course_list_page',
            exclude: ['js/common']
        },
        {
            name: 'js/pages/credit_checkout',
            exclude: ['js/common']
        }
    ]
})
