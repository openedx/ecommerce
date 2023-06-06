define([], function() {
    'use strict';

    var enrollmentCodeVoucher = {
            id: 1,
            name: 'Test Enrollment Code',
            code: 'XP54BC4M',
            redeem_url: 'http://localhost:8002/coupons/offer/?code=XP54BC4M',
            usage: 'Single use',
            start_datetime: '2015-01-01T00:00:00Z',
            end_datetime: '3500-01-01T00:00:00Z',
            num_basket_additions: 0,
            num_orders: 0,
            total_discount: '0.00',
            date_created: '2015-12-23',
            offers: [
                1
            ],
            is_available_to_user: [
                true,
                ''
            ],
            benefit: {
                type: 'Percentage',
                value: 100.0
            }
        },
        lastEditData = [
            'user',
            '2016-01-15T07:26:22.926Z'
        ],
        percentageDiscountCodeVoucher = {
            id: 1,
            name: 'Test Discount Code',
            code: 'TST1234',
            redeem_url: 'http://localhost:8002/coupons/offer/?code=TST1234',
            usage: 'Single use',
            start_datetime: '2015-01-01T00:00:00Z',
            end_datetime: '3500-01-01T00:00:00Z',
            num_basket_additions: 0,
            num_orders: 0,
            total_discount: '0.00',
            date_created: '2015-12-23',
            offers: [
                1
            ],
            is_available_to_user: [
                true,
                ''
            ],
            benefit: {
                type: 'Percentage',
                value: 50.0
            }
        },
        valueDiscountCodeVoucher = {
            id: 1,
            name: 'Test Discount Code',
            code: 'TST1234',
            redeem_url: 'http://localhost:8002/coupons/offer/?code=TST1234',
            usage: 'Once per customer',
            start_datetime: '2015-01-01T00:00:00Z',
            end_datetime: '3500-01-01T00:00:00Z',
            num_basket_additions: 0,
            num_orders: 0,
            total_discount: '0.00',
            date_created: '2015-12-23',
            offers: [
                1
            ],
            is_available_to_user: [
                true,
                ''
            ],
            benefit_type: 'Absolute',
            benefit_value: 12.0
        },
        verifiedSeat = {
            id: 9,
            url: 'http://ecommerce.local:8002/api/v2/products/9/',
            structure: 'child',
            product_class: 'Seat',
            title: 'Seat in edX Demonstration Course with verified certificate',
            price: '15.00',
            expires: '2020-01-01T00:00:00Z',
            attribute_values: [
                {
                    name: 'certificate_type',
                    value: 'verified'
                },
                {
                    name: 'course_key',
                    value: 'course-v1:edX+DemoX+Demo_Course'
                },
                {
                    name: 'id_verification_required',
                    value: true
                }
            ],
            is_available_to_buy: true
        },
        courseData = {
            id: 'course-v1:edX+DemoX+Demo_Course',
            name: 'Demo Course',
            type: 'verified',
            products: [
                {
                    id: 3,
                    product_class: 'Seat',
                    structure: 'child',
                    expires: null,
                    attribute_values: [
                        {
                            name: 'certificate_type',
                            value: 'verified'
                        }
                    ],
                    is_available_to_buy: true,
                    stockrecords: [
                        {
                            id: 2,
                            product: 3,
                            partner: 1
                        }
                    ]
                },
                {
                    id: 2,
                    product_class: 'Seat',
                    structure: 'child',
                    expires: null,
                    attribute_values: [
                        {
                            name: 'certificate_type',
                            value: 'honor'
                        }
                    ],
                    stockrecords: [
                        {
                            id: 1,
                            product: 2,
                            partner: 1
                        }
                    ]
                }
            ]
        },
        discountCodeCouponData = {
            id: 11,
            title: 'Test Discount Code',
            coupon_type: 'Discount code',
            last_edited: lastEditData,
            seats: [verifiedSeat],
            client: 'Client Name',
            price: '100.00',
            categories: [
                {
                    id: 4,
                    name: 'TESTCAT'
                }
            ],
            start_date: '2015-01-01T00:00:00Z',
            end_date: '2016-01-01T00:00:00Z',
            voucher_type: 'Single use',
            benefit_type: 'Percentage',
            benefit_value: 25
        },
        discountCodeCouponModelData = {
            title: 'Test Discount',
            coupon_type: 'Discount code',
            client: 'test_client',
            start_date: '2015-01-01T00:00:00Z',
            end_date: '2016-01-01T00:00:00Z',
            stock_record_ids: [1],
            code: 'TESTCODE',
            voucher_type: 'Single use',
            benefit_type: 'Percentage',
            benefit_value: 25,
            course_id: 'a/b/c',
            seat_type: 'verified',
            course: verifiedSeat,
            price: 100,
            category: 4,
            invoice_type: 'Not-Applicable'
        },
        enrollmentCodeCouponData = {
            id: 10,
            title: 'Test Enrollment Code',
            code_type: 'Enrollment code',
            last_edited: lastEditData,
            seats: [verifiedSeat],
            client: 'Client Name',
            category: {
                id: 4,
                name: 'TESTCAT'
            },
            course_catalog: null,
            enterprise_customer: {id: '349bef52-c0fb-4901-a5b5-26e9b70a4102', name: 'test client'},
            price: '100.00',
            invoice_type: 'Prepaid',
            invoice_discount_type: 'Percentage',
            invoice_discount_value: 40,
            invoice_number: 'INV-00001',
            invoice_payment_date: '2015-01-01T00:00:00Z',
            tax_deducted_source: 50,
            start_date: '2015-01-01T00:00:00Z',
            end_date: '2016-01-01T00:00:00Z',
            voucher_type: 'Single use',
            code_status: 'ACTIVE',
            coupon_type: 'Enrollment Code',
            benefit_type: 'Percentage',
            benefit_value: 100
        },
        enrollmentCodeCouponModelData = {
            title: 'Test Enrollment',
            coupon_type: 'Enrollment code',
            client: 'test_client',
            start_date: '2015-01-01T00:00:00Z',
            end_date: '2016-01-01T00:00:00Z',
            stock_record_ids: [1],
            voucher_type: 'Single use',
            price: 100,
            course_id: 'a/b/c',
            seat_type: 'verified',
            course: verifiedSeat
        },
        enterpriseCouponData = {
            id: 11,
            title: 'Test Enterprise Code',
            code_type: 'Enrollment code',
            last_edited: lastEditData,
            seats: [verifiedSeat],
            client: 'TestEnterprise',
            category: {
                id: 4,
                name: 'TESTCAT'
            },
            enterprise_customer: {id: '349bef52-c0fb-4901-a5b5-26e9b70a4102', name: 'test client'},
            enterprise_customer_catalog: 'f9098aab184245c881a20e53d8e7609a',
            invoice_type: 'Prepaid',
            invoice_discount_type: 'Percentage',
            invoice_discount_value: 40,
            invoice_number: 'INV-00001',
            invoice_payment_date: '2015-01-01T00:00:00Z',
            tax_deducted_source: 50,
            start_date: '2015-01-01T00:00:00Z',
            end_date: '2016-01-01T00:00:00Z',
            voucher_type: 'Single use',
            code_status: 'ACTIVE',
            coupon_type: 'Enrollment Code',
            benefit_type: 'Percentage',
            benefit_value: 100
        },
        enterpriseCouponModelData = {
            title: 'Test Enterprise',
            coupon_type: 'Enrollment code',
            start_date: '2015-01-01T00:00:00Z',
            end_date: '2016-01-01T00:00:00Z',
            voucher_type: 'Single use',
            enterprise_customer: {id: '349bef52-c0fb-4901-a5b5-26e9b70a4102', name: 'test client'},
            enterprise_customer_catalog: 'f9098aab-1842-45c8-81a2-0e53d8e7609a',
            notify_email: 'batman@gotham.comics',
            contract_discount_value: 30,
            prepaid_invoice_amount: 10000,
            sales_force_id: '006ABCDE0123456789',
            salesforce_opportunity_line_item: '000ABCDE9876543210',
            invoice_type: 'Not-Applicable'
        },
        couponAPIResponseData = {
            count: 1,
            next: null,
            previous: null,
            results: [
                {
                    id: 4,
                    url: 'http://localhost:8002/api/v2/coupons/4/',
                    structure: 'standalone',
                    product_class: 'Coupon',
                    title: 'Coupon',
                    price: '100.00',
                    expires: null,
                    attribute_values: [
                        {
                            name: 'Coupon vouchers',
                            value: [enrollmentCodeCouponData]
                        }
                    ],
                    is_available_to_buy: true,
                    stockrecords: []
                }
            ]
        },
        dynamicCouponData = {
            id: 12,
            title: 'Test Dynamic Code',
            coupon_type: 'Enrollment code',
            last_edited: lastEditData,
            seats: [],
            client: 'Client Name',
            price: '100.00',
            categories: [
                {
                    id: 4,
                    name: 'TESTCAT'
                }
            ],
            start_date: '2015-01-01T00:00:00Z',
            end_date: '2017-01-01T00:00:00Z',
            voucher_type: 'Single use',
            benefit_type: 'Percentage',
            benefit_value: 10,
            catalog_type: 'Multiple courses',
            catalog_query: 'org:edX',
            course_seat_types: [
                'verified', 'professional'
            ]
        },
        couponWithInvoiceData = {
            id: 2,
            title: 'Test Enrollment',
            catalog_type: 'Single course',
            categories: [
                {
                    id: 4,
                    name: 'TESTCAT'
                }
            ],
            coupon_type: 'Enrollment code',
            client: 'test_client',
            last_edited: lastEditData,
            note: null,
            start_date: '2015-01-01T00:00:00Z',
            end_date: '2016-01-01T00:00:00Z',
            stock_record_ids: [1],
            voucher_type: 'Single use',
            price: 100,
            course_id: 'a/b/c',
            seats: [verifiedSeat],
            seat_type: 'verified',
            course: verifiedSeat,
            total_value: 100,
            vouchers: [percentageDiscountCodeVoucher],
            payment_information: {
                Invoice: {
                    type: 'Prepaid',
                    discount_type: null,
                    discount_value: null,
                    number: 'INV-00001',
                    payment_date: '2015-01-01T00:00:00Z',
                    tax_deducted_source: '50'
                }
            }
        },
        enrollmentMultiUseCouponData = {
            id: 13,
            title: 'Test enrollment Muti-use coupon',
            coupon_type: 'Enrollment code',
            last_edited: lastEditData,
            seats: [verifiedSeat],
            client: 'Client Name',
            price: '100.00',
            categories: [
                {
                    id: 4,
                    name: 'TESTCAT'
                }
            ],
            start_date: '2015-01-01T00:00:00Z',
            end_date: '3500-01-01T00:00:00Z',
            voucher_type: 'Multi-use',
            max_uses: '5',
            benefit_type: 'Percentage',
            num_uses: '3',
            benefit_value: 100
        };
    return {
        couponAPIResponseData: couponAPIResponseData,
        couponWithInvoiceData: couponWithInvoiceData,
        courseData: courseData,
        discountCodeCouponData: discountCodeCouponData,
        discountCodeCouponModelData: discountCodeCouponModelData,
        dynamicCouponData: dynamicCouponData,
        enrollmentCodeCouponData: enrollmentCodeCouponData,
        enrollmentCodeCouponModelData: enrollmentCodeCouponModelData,
        enterpriseCouponData: enterpriseCouponData,
        enterpriseCouponModelData: enterpriseCouponModelData,
        enrollmentCodeVoucher: enrollmentCodeVoucher,
        enrollmentMultiUseCouponData: enrollmentMultiUseCouponData,
        lastEditData: lastEditData,
        percentageDiscountCodeVoucher: percentageDiscountCodeVoucher,
        valueDiscountCodeVoucher: valueDiscountCodeVoucher,
        verifiedSeat: verifiedSeat
    };
});
