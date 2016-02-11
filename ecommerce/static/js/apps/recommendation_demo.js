require([
        'jquery',
        'dataTablesBootstrap',
        'select2'
    ],
    function ($) {
        'use strict';

        function templateCourseResult(result) {
            if (result.loading) {
                return result.text;
            }

            return result.id + ' - ' + (result.name || result.text);
        }

        function templateCourseSelection(result) {
            if (result.id) {
                return result.id + ' - ' + (result.name || result.text);
            }

            return result.text;
        }

        function initializeTable($table, url, showWeightColumn) {
            var columns = [
                {data: 'id', sTitle: 'Course ID'},
                {data: 'name', sTitle: 'Course Title'}
            ];

            if (typeof showWeightColumn == 'undefined') {
                showWeightColumn = true;
            }

            if (showWeightColumn) {
                columns.unshift({data: 'weight', sTitle: 'Weight'})
            }

            $table.removeClass('hidden');

            return $table.DataTable({
                ajax: {
                    url: url,
                    dataSrc: ''
                },
                bFilter: false,
                bPaginate: false,
                columns: columns,
                order: [
                    [0, 'desc'],
                    [1, 'asc']
                ],
                processing: true
            })
        }

        $(function () {
            var $courseGroup = $('.course-specific'),
                $courseSpecificForm = $courseGroup.find('form'),
                $courseFormButton = $courseSpecificForm.find('button'),
                $courseField = $courseSpecificForm.find('select'),
                $userGroup = $('.user-specific'),
                $userSpecificForm = $userGroup.find('form'),
                $usernameField = $userSpecificForm.find('input'),
                $courseTable = null,
                $userRecommendationTable = null,
                $userEnrollmentTable = null;

            $courseField.select2({
                ajax: {
                    url: '/api/demo/courses/',
                    dataType: 'json',
                    delay: 250,
                    data: function (params) {
                        return {
                            q: params.term
                        };
                    },
                    minimumInputLength: 2,
                    cache: true
                },
                placeholder: 'Select a course',
                templateResult: templateCourseResult,
                templateSelection: templateCourseSelection
            });

            $courseField.on('select2:select', function(){
                $courseFormButton.focus();
            });

            $courseSpecificForm.submit(function (e) {
                var url = '/api/demo/courses/' + $courseField.val() + '/recommendations/';

                e.preventDefault();

                if ($courseTable) {
                    $courseTable.ajax.url(url).load();
                } else {
                    $courseTable = initializeTable($('.course-specific table.recommendations'), url);
                }
            });

            $userSpecificForm.submit(function (e) {
                var username = $usernameField.val(),
                    recommendationsUrl = '/api/demo/users/' + username + '/recommendations/',
                    enrollmentsUrl = '/api/demo/users/' + username + '/enrollments/';

                e.preventDefault();

                if (!username) {
                    alert('Input a username.');
                    return;
                }

                if ($userRecommendationTable) {
                    $userRecommendationTable.ajax.url(recommendationsUrl).load();
                    $userEnrollmentTable.ajax.url(enrollmentsUrl).load();
                } else {
                    $userRecommendationTable = initializeTable($('.user-specific table.recommendations'), recommendationsUrl);
                    $userEnrollmentTable = initializeTable($('.user-specific table.enrollments'), enrollmentsUrl, false);
                }
            });
        });
    }
);
