var ModelerControllers = angular.module('ModelerControllers', []);

ModelerControllers.controller('ModelController', ['$scope', '$http', '$q',
    function ($scope, $http, $q) {
        var cubes = $http.get('cubes');
        var dimensions = $http.get('dimensions');

        $q.all([cubes, dimensions]).then(function(results){
            $scope.cubes = results[0].data;
            $scope.dimensions = results[1].data;

            $scope.dims_by_id = {}

            for(i in $scope.dimensions){
                dim = $scope.dimensions[i]
                $scope.dims_by_id[dim.id] = dim
            }    
        });

        $scope.modelObject = null;

        $scope.functions = [
            {"name": "count", "label": "Record Count"}, 
            {"name": "count_nonempty", "label": "Count of Non-empty Values"},
            {"name": "sum", "label": "Sum"},
            {"name": "min", "label": "Min"},
            {"name": "max", "label": "Max"},
            {"name": "avg", "label": "Average"},
            {"name": "stddev", "label": "Standard Deviation"},
            {"name": "variance", "label": "Variance"},
            {"name": "sma", "label": "Simple Moving Average"},
            {"name": "wma", "label": "Weighted Moving Average"},
            {"name": null, "label": "Other/Native"},
        ];
    }
]);

ModelerControllers.controller('CubeListController', ['$scope', '$http',

    function ($scope, $http) {
        $http.get('cubes').success(function(data) {
            $scope.cubes = data;
        });
        
        $scope.idSequence = 1;

        $scope.selectCube = function(id) {
            alert(id)
            cube = _.filter($scope.cubes, function(cube) { return cube.id === id });
            $scope.currentCube = cube
        };

        $scope.addCube = function() {
            cube = {
                id: $scope.idSequence,
                name:"new_cube",
                label: "New Cube",
                measures: [],
                aggregates: [],
                details: []
            };
            $scope.idSequence += 1;
            $scope.cubes.push(cube);
        };

    }
]);

ModelerControllers.controller('CubeController', ['$scope', '$routeParams', '$http',
    function ($scope, $routeParams, $http) {
        id = $routeParams.cubeId

        $http.get('cube/' + id).success(function(cube) {
            $scope.cube = cube;
            $scope.cube_dimensions = []
            names = cube.dimensions || []
            for(var i in names) {
                var name = names[i]
                var dim = _.find($scope.dimensions,
                                 function(d) {return d.name == name});

                if (dim) {
                    $scope.cube_dimensions.push(dim);
                }
                else {
                    dim = { name: name, label: name + " (unknown)"}
                    $scope.cube_dimensions.push(dim)
                }   
            };

            $scope.available_dimensions = _.filter($scope.dimensions, function(d) {
                return names.indexOf(d.name) === -1;
            });

            $scope.$broadcast('cubeLoaded');
        });

        $scope.active_tab = $routeParams.activeTab || "info";
        $scope.cubeId = id;

        $scope.includeDimension = function(dim_id) {
            var dim = $scope.dims_by_id[dim_id];
             
            // We just need dimension name
            $scope.cube.dimensions.push(dim.name);
            
            // This is for Angular view refresh
            $scope.cube_dimensions.push(dim);
            index = $scope.available_dimensions.indexOf(dim);
            if(index != -1){
                $scope.available_dimensions.splice(index, 1)
            };
        };   
        $scope.removeDimension = function(dim_id) {
            var dim = $scope.dims_by_id[dim_id];
             
            // We just need dimension name
            index = $scope.cube.dimensions.indexOf(dim.name);
            if(index != -1){
                $scope.cube.dimensions.splice(index, 1)
                $scope.cube_dimensions.splice(index, 1);
            };
            
            // This is for Angular view refresh
            // ???
            $scope.available_dimensions = _.filter($scope.dimensions, function(d) {
                return $scope.cube.dimensions.indexOf(d.name) === -1;
            });
        };

        $scope.save = function(){
            $http.put("cube/" + $scope.cubeId, $scope.cube);
        }

    }
]);

function AttributeListController(type, label){
    return function($scope, modelObject) {
        $scope.attributeType = type;
        $scope.attributeLabel = label;

        $scope.loadAttributes = function() {
            type = $scope.attributeType;
            if(type == "measure"){
                $scope.attributes = $scope.cube.measures;
            }
            else if(type == "aggregate"){
                $scope.attributes = $scope.cube.aggregates;
            }
            else if(type == "detail"){
                $scope.attributes = $scope.cube.details;
            }
            else if(type == "level_attribute"){
                $scope.attributes = $scope.level.attributes;
            };

            // Set attribute selection, if there are any attributes
            if($scope.attributes.length >= 1){
                $scope.selectedAttribute = $scope.attributes[0];
            }
            else {
                $scope.selectedAttribute = null;
            };       
        };   

        if($scope.cube) {
            $scope.loadAttributes();
        }

        $scope.$on('cubeLoaded', $scope.loadAttributes);

        $scope.selectAttribute = function(attribute) {
            $scope.selectedAttribute = attribute;
        };

        $scope.removeAttribute = function(index) {
            $scope.attributes.splice(index, 1);
        }; 

        $scope.addAttribute = function() {
            attribute = {"name": "new_"+type}
            $scope.selectedAttribute = attribute;
            $scope.attributes.push(attribute)
        };
    };      
};

ModelerControllers.controller('CubeMeasureListController', ['$scope',
                              AttributeListController("measure", "Measure")]);

ModelerControllers.controller('CubeAggregateListController', ['$scope',
                              AttributeListController("aggregate", "Aggregate")]);
