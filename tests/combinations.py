import unittest
import cubes
import os

from common import DATA_PATH

@unittest.skip        
class CombinationsTestCase(unittest.TestCase):
	
    def setUp(self):
        self.nodea = ('a', (1,2,3))
        self.nodeb = ('b', (99,88))
        self.nodec = ('c',('x','y'))
        self.noded = ('d', ('m'))

    def test_levels(self):
        combos = cubes.common.combine_nodes([self.nodea])
        self.assertEqual(len(combos), 3)

        combos = cubes.common.combine_nodes([self.nodeb])
        self.assertEqual(len(combos), 2)

        combos = cubes.common.combine_nodes([self.noded])
        self.assertEqual(len(combos), 1)

    def test_combos(self):
        combos = cubes.common.combine_nodes([self.nodea, self.nodeb])
        self.assertEqual(len(combos), 11)

        combos = cubes.common.combine_nodes([self.nodea, self.nodeb, self.nodec])
        self.assertEqual(len(combos), 35)
	
    def test_required_one(self):
        nodes = [self.nodea, self.nodeb, self.nodec]
        required = [self.nodea]
        combos = cubes.common.combine_nodes(nodes, required)
        self.assertEqual(len(combos), 27)
        for combo in combos:
            flag = False
            for item in combo:
                if tuple(item[0]) == self.nodea:
                    flag = True
                    break
            self.assertTrue(flag, "All combinations should contain required node")

    def test_required_more(self):
        nodes = [self.nodea, self.nodeb, self.nodec, self.noded]
        required = [self.nodea, self.nodeb]
        combos = cubes.common.combine_nodes(nodes, required)
        self.assertEqual(len(combos), 36)
        for combo in combos:
            flag = False
            for item in combo:
                if tuple(item[0]) == self.nodea or tuple(item[0]) == self.nodeb:
                    flag = True
                    break
            self.assertTrue(flag, "All combinations should contain both required nodes")

@unittest.skip        
class CuboidsTestCase(unittest.TestCase):
    def setUp(self):
        self.model_path = os.path.join(DATA_PATH, 'model.json')
        self.model = cubes.model_from_path(self.model_path)
        self.cube = self.model.cubes.get("contracts")

    def test_combine_dimensions(self):
        dims = self.cube.dimensions
        results = cubes.common.all_cuboids(dims)
        # for r in results:
        #     print "=== COMBO:"
        #     for c in r:
        #         print "---     %s: %s" % (c[0][0].name, c[1])

        self.assertEqual(len(results), 863)

        dim = self.cube.dimension("date")
        results = cubes.common.all_cuboids(dims, [dim])
        self.assertEqual(len(results), 648)

    def test_should_not_accept_unknown_dimension(self):
        foo_desc = { "name": "foo", "levels": {"level": {"key": "boo"}}}
        foo_dim = cubes.create_dimension(foo_desc)

        self.assertRaises(AttributeError, cubes.common.all_cuboids,
                                          self.cube.dimensions, [foo_dim])

def test_suite():
    suite = unittest.TestSuite()

    suite.addTest(unittest.makeSuite(CombinationsTestCase))
    suite.addTest(unittest.makeSuite(CuboidsTestCase))

    return suite

