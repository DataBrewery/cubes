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

var CubesModelerApp = angular.module('CubesModelerApp', [
    'ngRoute',
    'ModelerControllers'
]);
 
CubesModelerApp.config(
    ['$routeProvider',
    function($routeProvider) {
        $routeProvider.
        when('/cubes', {
            templateUrl: 'partials/cube-list.html',
            controller: 'CubeListController'
        }).
        when('/cubes/:cubeId', {
            templateUrl: 'partials/cube-detail.html',
            controller: 'CubeController'
        }).
        when('/cubes/:cubeId/:activeTab', {
            templateUrl: 'partials/cube-detail.html',
            controller: 'CubeController'
        }).
        otherwise({
            redirectTo: '/cubes'
        });
    }
]);
