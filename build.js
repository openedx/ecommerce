/* eslint semi: 0 */
({ // eslint-disable-line no-unused-expressions
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
            name: 'js/apps/course_admin_app',
            exclude: ['js/common']
        },
        {
            name: 'js/apps/coupon_admin_app',
            exclude: ['js/common']
        },
        {
            name: 'js/apps/credit_checkout',
            exclude: ['js/common']
        },
        {
            name: 'js/apps/basket_app',
            exclude: ['js/common']
        },
        {
            name: 'js/apps/order_receipt_app',
            exclude: ['js/common']
        },
        {
            name: 'js/pages/program_offer_list_page',
            exclude: ['js/common']
        },
        {
            name: 'js/pages/program_offer_form_page',
            exclude: ['js/common']
        }
    ]
})
