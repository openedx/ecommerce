define([
  'underscore',
  'collections/drf_pageable_collection',
  'models/course_model'
], function (_, DrfPageableCollection, CourseModel) {

  return DrfPageableCollection.extend({
    model: CourseModel,
    url: '/api/v2/courses/',
  });

});
