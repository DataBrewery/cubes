var _ = {};

_.map = function(ary, f) {
  var ret = [];
  for (var i = 0; i < ary.length; i++) {
    ret.push(f(ary[i]));
  }
  return ret;
};

_.filter = function(ary, f) {
  var ret = [];
  for (var i = 0; i < ary.length; i++) {
    if ( f(ary[i]) ) ret.push(ary[i]);
  }
  return ret;
};

_.find = function(ary, f) {
  var i;
  if (Object.prototype.toString.call(ary) === '[object Array]') {
    for (i = 0; i < ary.length; i++) {
      if ( f(ary[i]) ) return ary[i];
    }
  } else {
    for (i in ary) {
      if ( f(ary[i]) ) return ary[i];
    }
  }
  return null;
};

_.isString = function(o) {
  return Object.prototype.toString.call(o) === '[object String]';
};


// Move item in array from from_index to to_index
_.moveItem = function (array, from_index, to_index) {
    array.splice(to_index, 0, array.splice(from_index, 1)[0]);
    return array;
};

_.relativeMoveItem = function(array, obj, offset){
    // Direction: -1=down 1=up
    from_index = array.indexOf(obj);
    to_index = from_index + offset;
    to_index = to_index < 0 ? 0 : to_index;
    to_index = to_index >= array.length ? array.length-1 : to_index;
    _.moveItem(array, from_index, to_index);
};



var CubesModelerApp = angular.module('CubesModelerApp', [
    'ngRoute',
    'ModelerControllers'
]);
 
CubesModelerApp.config(
    ['$routeProvider',
    function($routeProvider) {
        $routeProvider.
        when('/cubes', {
            templateUrl: 'views/cube-list.html',
            controller: 'CubeListController'
        }).
        when('/cubes/:cubeId', {
            templateUrl: 'views/cube-detail.html',
            controller: 'CubeController'
        }).
        when('/cubes/:cubeId/:activeTab', {
            templateUrl: 'views/cube-detail.html',
            controller: 'CubeController'
        }).
        when('/dimensions', {
            templateUrl: 'views/dimension-list.html',
            controller: 'DimensionListController'
        }).
        when('/dimensions/:dimId', {
            templateUrl: 'views/dimension-detail.html',
            controller: 'DimensionController'
        }).
        when('/dimensions/:dimId/:activeTab', {
            templateUrl: 'views/dimension-detail.html',
            controller: 'DimensionController'
        }).
        when('/joins', {
            templateUrl: 'views/model-joins.html',
            controller: 'ModelController'
        }).
        when('/mappings', {
            templateUrl: 'views/model-mappings.html',
            controller: 'ModelController'
        }).
        otherwise({
            templateUrl: 'views/model-overview.html',
            redirectTo: '/'
        });
    }
]);
