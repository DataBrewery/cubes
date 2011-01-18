import unittest
import os
import cubes
import cubes.tests

class CombinationsTestCase(unittest.TestCase):
	
    def setUp(self):
        self.nodea = ('a', (1,2,3))
        self.nodeb = ('b', (99,88))
        self.nodec = ('c',('x','y'))
        self.noded = ('d', ('m'))

    def test_levels(self):
        combos = cubes.util.combine_nodes([self.nodea])
        self.assertEqual(len(combos), 3)

        combos = cubes.util.combine_nodes([self.nodeb])
        self.assertEqual(len(combos), 2)

        combos = cubes.util.combine_nodes([self.noded])
        self.assertEqual(len(combos), 1)

    def test_combos(self):
        combos = cubes.util.combine_nodes([self.nodea, self.nodeb])
        self.assertEqual(len(combos), 11)

        combos = cubes.util.combine_nodes([self.nodea, self.nodeb, self.nodec])
        self.assertEqual(len(combos), 35)
	
    def test_required_one(self):
        nodes = [self.nodea, self.nodeb, self.nodec]
        required = [self.nodea]
        combos = cubes.util.combine_nodes(nodes, required)
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
        combos = cubes.util.combine_nodes(nodes, required)
        self.assertEqual(len(combos), 36)
        for combo in combos:
            flag = False
            for item in combo:
                if tuple(item[0]) == self.nodea or tuple(item[0]) == self.nodeb:
                    flag = True
                    break
            self.assertTrue(flag, "All combinations should contain both required nodes")

if __name__ == '__main__':
    unittest.main()

