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
        otherwise({
            redirectTo: '/cubes'
        });
    }
]);
