import unittest

from jevbench import composite as c


class CompositeTest(unittest.TestCase):
    def test_anchor_points(self):
        self.assertAlmostEqual(c.speed(0.1, 0.1), 100)
        self.assertAlmostEqual(c.speed(1, 1), 50)
        self.assertAlmostEqual(c.speed(10, 10), 0)
        self.assertAlmostEqual(c.cost(0.001), 100)
        self.assertAlmostEqual(c.cost(0.01), 75)
        self.assertAlmostEqual(c.cost(1), 25)
        self.assertAlmostEqual(c.cost(10), 0)

    def test_clipping_and_unknowns(self):
        self.assertEqual(c.speed(0.01, 0.05), 100)
        self.assertEqual(c.cost(50), 0)
        self.assertIsNone(c.cost(None))
        self.assertIsNone(c.capability([0.9, None, 0.8]))
        self.assertIsNone(c.main_score(90, None, 50))

    def test_capability_weights_tiers_equally(self):
        # 72 easy, 96 standard, 146 judge: tier size must not change the weight
        self.assertAlmostEqual(c.capability([1.0, 0.5, 0.0]), 50)

    def test_main_score(self):
        self.assertAlmostEqual(c.main_score(100, 50, 0), 50)  # balanced 33:33:33 is the default
        self.assertAlmostEqual(c.main_score(100, 50, 0, c.SENSITIVITY["60/20/20 accuracy emphasis"]), 70)
        self.assertAlmostEqual(c.main_score(100, 100, 100, c.SENSITIVITY["33/33/33 geometric"]), 100)

    def test_cost_does_not_saturate_for_different_prices(self):
        # DeBERTa-class encoder vs Needle-class tiny generator: different prices, different scores
        self.assertGreater(c.cost(0.0045), c.cost(0.0162))
        self.assertLess(c.cost(0.0045), 100)


if __name__ == "__main__":
    unittest.main()
