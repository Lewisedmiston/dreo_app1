from common.costing import to_oz

def test_to_oz_basic():
    assert to_oz(1, "lb") == 16.0
    assert round(to_oz(1, "kg"), 5) == 35.27396
    assert round(to_oz(1, "L"), 3) == 33.814
    assert to_oz(32, "oz") == 32
