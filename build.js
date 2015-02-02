/* jshint asi: true, expr:true */
({
    mainConfigFile: 'static/js/config.js',
    baseUrl: 'static',
    dir: 'static/dist',
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
            name: 'js/engagement-content-main',
            exclude: ['js/common']
        },
        {
            name: 'js/enrollment-activity-main',
            exclude: ['js/common']
        },
        {
            name: 'js/enrollment-geography-main',
            exclude: ['js/common']
        },
        {
            name: 'js/enrollment-demographics-age-main',
            exclude: ['js/common']
        },
        {
            name: 'js/enrollment-demographics-education-main',
            exclude: ['js/common']
        },
        {
            name: 'js/enrollment-demographics-gender-main',
            exclude: ['js/common']
        },
        {
            name: 'js/performance-answer-distribution-main',
            exclude: ['js/common']
        }
    ]
})
