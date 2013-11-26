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
    }
]);

ModelerControllers.controller('CubeListController', ['$scope', '$http',

    function ($scope, $http) {
        $http.get('cubes').success(function(data) {
            $scope.___cubes = data;
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
                label: "New Cube"
            };
            $scope.idSequence += 1;
            $scope.cubes.push(cube);
        };

    }
]);

ModelerControllers.controller('CubeController', ['$scope', '$routeParams', '$http',
    function ($scope, $routeParams, $http) {
        id = $routeParams.cubeId

        $http.get('cube/' + id).success(function(data) {
            $scope.cube = data;

            $scope.cube_dimensions = []
            names = $scope.cube.dimensions || []
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
        }   
    }
]);
