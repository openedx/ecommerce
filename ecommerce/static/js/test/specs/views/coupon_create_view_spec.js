define([
        'jquery',
        'views/coupon_create_edit_view',
        'views/alert_view',
        'models/coupon_model',
        'views/coupon_form_view'
    ],
    function ($,
              CouponCreateEditView,
              AlertView,
              Coupon,
              CouponFormView) {
        'use strict';

        describe('coupon create view', function () {
            var view,
                model,
                categoriesDropdownOptions = [
                    {
                        value: 4,
                        label: 'Affiliate Promotion',
                        selected: true
                    }
                ],
                mockedFetchedCategories = {
                    id: 3,
                    children: [
                        {
                            id: 4,
                            children: [],
                            path: '00020001',
                            depth: 2,
                            numchild: 0,
                            name: 'Affiliate Promotion',
                            description: '',
                            image: null,
                            slug: 'affiliate-promotion'
                        }
                    ]
                };

            beforeEach(function () {
                spyOn(CouponFormView.prototype.couponCategoryCollection, 'fetch')
                    .and.returnValue(mockedFetchedCategories);
                spyOn(CouponFormView.prototype, 'updateDropdown').and.callFake(function(){
                    this.categories = categoriesDropdownOptions;
                });
                model = new Coupon();
                view = new CouponCreateEditView({ model: model, editing: false }).render();
                spyOn(model, 'save');
            });

            describe('API call', function(){
                it('should populate categories', function(){
                    expect(view.formView.couponCategoryCollection.fetch).toHaveBeenCalled();
                    expect(view.formView.couponCategoryCollection.fetch())
                        .toEqual(mockedFetchedCategories);
                    expect(view.formView.couponCategoryCollection.parse(mockedFetchedCategories))
                        .toEqual(categoriesDropdownOptions);
                    expect(view.formView.categories).toEqual(categoriesDropdownOptions);
                });
            });

            it('should throw an error if submitted with blank fields', function () {
                var errorHTML = '<strong>Error!</strong> You must complete all required fields.';
                view.formView.submit($.Event('click'));
                expect(view.$el.find('.alert').length).toBe(1);
                expect(view.$el.find('.alert').html()).toBe(errorHTML);
            });

            it('should submit form with valid fields', function () {

                view.$el.find('[name=title]').val('Test Enrollment').trigger('change');
                view.$el.find('[name=code_type]').val('enrollment').trigger('change');
                view.$el.find('[name=client_username]').val('test_client').trigger('change');
                view.$el.find('[name=start_date]').val('2015-01-01T00:00').trigger('change');
                view.$el.find('[name=end_date]').val('2016-01-01T00:00').trigger('change');
                view.$el.find('[name=price]').val('100').trigger('change');
                spyOn(view.formView, 'fillFromCourse').and.callFake(function () {
                    var seatTypes = [$('<option></option>')
                        .text('Verified')
                        .val('Verified')
                        .data({
                            price: '100',
                            stockrecords: [1]
                        })];
                    this.$el.find('[name=seat_type]')
                        .html(seatTypes)
                        .trigger('change');
                });
                view.formView.delegateEvents();
                view.$el.find('[name=course_id]').val('course-v1:edX+DemoX+Demo_Course').trigger('input');
                view.$el.find('[name=category]').val(categoriesDropdownOptions[0].value).trigger('change');
                view.$el.find('[name=note]').val('TESTNOTE').trigger('change');
                view.formView.submit($.Event('click'));
                expect(model.isValid()).toBe(true);
                expect(model.save).toHaveBeenCalled();
                
            });

        });
    }
);
