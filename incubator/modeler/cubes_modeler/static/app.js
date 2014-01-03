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
    }
    else {
        for (i in ary) {
            if ( f(ary[i]) ) return ary[i];
        }
    }
    return null;
};

_.find_by_name = function(ary, name) {
    return _.find(ary, function(o) {
        if(o) {
            return o.name == name;
        }
        else {
            return false;
        };
    } ); 
};

_.isString = function(o) {
  return Object.prototype.toString.call(o) === '[object String]';
};

_.hasEmptyValues = function(o) {
    for(key in o) {
        if(o[key] != null && o[key] != ""){
            return false;
        }
    }
    return true;
}

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

// Remove `item` from `array` and return item just before the one removed or
// nothing if no items are left.
// This is UI helper function.
_.removeListItem = function(array, item) {
    var index = array.indexOf(item);
    if(index != -1){
        array.splice(index, 1)
    };
    if(array.length > 0) {
        return array[Math.max(0, index-1)]
    };
    return null;
}



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
        when('/cube/:cubeId', {
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
            templateUrl: 'views/model-joins.html'
        }).
        when('/mappings', {
            templateUrl: 'views/model-mappings.html',
        }).
        when('/info', {
            templateUrl: 'views/model-info.html',
        }).
        otherwise({
            templateUrl: 'views/model-overview.html',
            redirectTo: '/'
        });
    }
]);


// Cubes Model Utils
// TODO: Make this separate or integrate in cubes.js/cubes_model.js as modeler
// utils
//

var CM = {};

CM.cube_attribute = function(cube, name) {
    // Return cube attribute
    // TODO: this is same as Cube.attribute()
    //
    if(cube.aggregates) {
        attr = _.find_by_name(cube.aggregates, name);
        if(attr) {
            return attr;
        }
    }
    if(cube.measures) {
        attr = _.find_by_name(cube.measures, name);
        if(attr) {
            return attr;
        }
    }
    if(cube.details) {
        attr = _.find_by_name(cube.details, name);
        if(attr) {
            return attr;
        }
    }
    return null;
};

CM.dimension_attribute = function(dim, name) {
    // Return cube attribute
    // TODO: this is same as Cube.attribute()
    //
    if(!dim.levels) {
        return null;
    }

    for(i in dim.levels) {
        level = dim.levels[i];

        attr = _.find_by_name(level.attributes, name);
        if(attr) {
            return attr;
        }
    }

    return null;
};

CM.collect_attribute_mappings = function(attr_list) {
    // Removes mappings from attributes and returns an array of mappings that
    // have non-empty keys
    // WARNING: use this on a cube copy before save
    var mappings = []
    for(var i in attr_list){
        attr = attr_list[i];
        if(attr.mapping && !_.hasEmptyValues(attr.mapping.value)) {
            mapping = attr.mapping;
            mapping.key = attr.name;
            mappings.push(attr.mapping);
            delete attr["mapping"]
        }
    }
    return mappings;
}
