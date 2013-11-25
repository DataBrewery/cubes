var ModelerControllers = angular.module('ModelerControllers', []);

ModelerControllers.controller('CubeListController', ['$scope', '$http',

    function ($scope, $http) {
        $http.get('cubes').success(function(data) {
            $scope.cubes = data;
            var i;

            for(i; i < $scope.cubes.length; i++) {
                $scope.cubes[i].id = i + 1;
            };
            $scope.idSequence = i; 
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
        });

        $scope.active_tab = $routeParams.activeTab || "info";
        $scope.cubeId = id;
    }
]);
