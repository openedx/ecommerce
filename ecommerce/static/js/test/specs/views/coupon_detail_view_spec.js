define([
        'jquery',
        'underscore.string',
        'models/coupon_model',
        'views/coupon_detail_view',
        'test/mock_data/coupons',
        'moment',
    ],
    function ($,
              _s,
              Coupon,
              CouponDetailView,
              Mock_Coupons,
              moment) {
        'use strict';

        describe('coupon detail view', function() {
            var data,
                enrollmentCodeVoucher,
                lastEditData,
                model,
                percentageDiscountCodeVoucher,
                valueDiscountCodeVoucher,
                verifiedSeat,
                view;

            beforeEach(function () {
                data = Mock_Coupons.enrollmentCodeCouponData;
                model = Coupon.findOrCreate(data, {parse: true});
                view = new CouponDetailView({model: model});
                enrollmentCodeVoucher = Mock_Coupons.enrollmentCodeVoucher;
                lastEditData = Mock_Coupons.lastEditData;
                percentageDiscountCodeVoucher = Mock_Coupons.percentageDiscountCodeVoucher;
                valueDiscountCodeVoucher = Mock_Coupons.valueDiscountCodeVoucher;
                verifiedSeat = Mock_Coupons.verifiedSeat;
            });

            it('should get code status from voucher data', function () {
                expect(view.codeStatus(enrollmentCodeVoucher)).toBe('ACTIVE');

                enrollmentCodeVoucher.end_datetime = moment().fromNow();
                expect(view.codeStatus(enrollmentCodeVoucher)).toBe('INACTIVE');

                enrollmentCodeVoucher.start_datetime = moment().toNow();
                enrollmentCodeVoucher.end_datetime = moment(enrollmentCodeVoucher.start_datetime).toNow();
                expect(view.codeStatus(enrollmentCodeVoucher)).toBe('INACTIVE');
            });

            it('should get coupon type from voucher data', function () {
                expect(view.couponType(percentageDiscountCodeVoucher)).toBe('Discount Code');
                expect(view.couponType(enrollmentCodeVoucher)).toBe('Enrollment Code');
            });

            it('should get discount value from voucher data', function () {
                expect(view.discountValue(percentageDiscountCodeVoucher)).toBe('50%');
                expect(view.discountValue(valueDiscountCodeVoucher)).toBe('$12');
                expect(view.discountValue(enrollmentCodeVoucher)).toBe('100%');
            });

            it('should format date time as MM/DD/YYYY h:mm A', function () {
                expect(view.formatDateTime('2015-01-01T00:00:00Z')).toBe('01/01/2015 12:00 AM');
            });

            it('should format last edit data', function () {
                expect(view.formatLastEditedData(lastEditData)).toBe('user - 01/15/2016 7:26 AM');
            });

            it('should get usage limitation from voucher data', function () {
                expect(view.usageLimitation(enrollmentCodeVoucher)).toBe('Can be used once by one customer');
                expect(view.usageLimitation(valueDiscountCodeVoucher)).toBe('Can be used once by multiple customers');

                valueDiscountCodeVoucher.usage = 'Multi-use';
                expect(view.usageLimitation(valueDiscountCodeVoucher)).toBe(
                    'Can be used multiple times by multiple customers'
                );

                valueDiscountCodeVoucher.usage = '';
                expect(view.usageLimitation(valueDiscountCodeVoucher)).toBe('');
            });

            it('should display correct data upon rendering', function () {
                var voucher = model.get('vouchers')[0],
                    category = model.get('categories')[0].name;

                spyOn(view, 'renderVoucherTable');
                view.render();
                expect(view.$el.find('.coupon-title').text()).toEqual(model.get('title'));
                expect(view.$el.find('.coupon-type').text()).toEqual(view.couponType(voucher));
                expect(view.$el.find('.code-status').text()).toEqual(view.codeStatus(voucher));
                expect(view.$el.find('.coupon-information > .heading > .pull-right > span').text()).toEqual(
                    view.formatLastEditedData(model.get('last_edited'))
                );
                expect(view.$el.find('.category > .value').text()).toEqual(category);
                expect(view.$el.find('.discount-value > .value').text()).toEqual(view.discountValue(voucher));
                expect(view.$el.find('.course-info > .value').contents().get(0).nodeValue).toEqual(
                    'course-v1:edX+DemoX+Demo_Course'
                );
                expect(view.$el.find('.course-info > .value > .pull-right').text()).toEqual('verified');
                expect(view.$el.find('.start-date-info > .value').text()).toEqual(
                    view.formatDateTime(voucher.start_datetime)
                );
                expect(view.$el.find('.end-date-info > .value').text()).toEqual(
                    view.formatDateTime(voucher.end_datetime)
                );
                expect(view.$el.find('.usage-limitations > .value').text()).toEqual(view.usageLimitation(voucher));
                expect(view.$el.find('.client-info > .value').text()).toEqual(model.get('client'));
                expect(view.$el.find('.total-paid > .value').text()).toEqual(
                    _s.sprintf('$%s', model.get('price'))
                );
                expect(view.renderVoucherTable).toHaveBeenCalled();
                expect(view.$el.find('.invoice-type > .value').text()).toEqual(model.get('invoice_type'));
                expect(view.$el.find('.invoice-number > .value').text()).toEqual(model.get('invoice_number'));
                expect(view.$el.find('.invoiced-amount > .value').text()).toEqual(
                    model.get('invoiced_amount').toString()
                );
                expect(view.$el.find('.invoice-payment-date > .value').text()).toEqual(
                    view.formatDateTime(model.get('invoice_payment_date'))
                );
                expect(view.$el.find('.tax-deducted-source-value > .value').text()).toEqual(
                    view.taxDeductedSource(model.get('tax_deducted_source_value'))
                );
            });

            it('should render course data', function () {
                view.model.set({
                    'catalog_type': 'Single course',
                    'course_id': 'a/b/c',
                    'seat_type': 'Verified'
                });

                view.render();

                var course_info = view.$el.find('.course-info .value');
                expect(course_info.length).toEqual(1);
                expect(course_info.text()).toEqual('a/b/cVerified');

                view.model.set({
                    'catalog_type': 'Multiple courses',
                    'catalog_query': 'id:*',
                    'course_seat_types': ['verified', 'professional']
                });

                view.render();

                expect(view.$el.find('.catalog-query .value').text()).toEqual('id:*');
                expect(view.$el.find('.seat-types .value').text()).toEqual('verified,professional');
            });

            it('should display data table', function () {
                view.renderVoucherTable();
                expect(view.$el.find('#vouchersTable').DataTable().autowidth).toBeFalsy();
                expect(view.$el.find('#vouchersTable').DataTable().paging).toBeFalsy();
                expect(view.$el.find('#vouchersTable').DataTable().ordering).toBeFalsy();
                expect(view.$el.find('#vouchersTable').DataTable().searching).toBeFalsy();
            });

            it('should download voucher report in the new tab', function () {
                var e = $.Event('click'),
                    url = _s.sprintf('/api/v2/coupons/coupon_reports/%d', model.id);
                spyOn(e, 'preventDefault');
                spyOn(window, 'open');
                view.downloadCouponReport(e);
                expect(e.preventDefault).toHaveBeenCalled();
                expect(window.open).toHaveBeenCalledWith(url, '_blank');
            });
        });
    }
);
