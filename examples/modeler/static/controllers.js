var ModelerControllers = angular.module('ModelerControllers', []);

ModelerControllers.controller('ModelController', ['$scope', '$http', '$q',
    function ($scope, $http, $q) {
        var cubes = $http.get('cubes');
        var dimensions = $http.get('dimensions');

        $q.all([cubes, dimensions]).then(function(results){
            $scope.cubes = results[0].data;
            $scope.dimensions = results[1].data;
            $scope.foobar = "hello there";
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
                dim = _.find($scope.dimensions,
                             function(d) {d.name == name});

                if (dim) {
                    $scope.cube_dimensions.push(dim);
                }
                else {
                    dim = { name: name, label: "Unknown " + name }
                    $scope.cube_dimensions.push(dim)
                }   
            }
        });

        $scope.active_tab = $routeParams.activeTab || "info";
        $scope.cubeId = id;
    }
]);
