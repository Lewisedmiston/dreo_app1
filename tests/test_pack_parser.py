from common.etl import parse_packsize, compute_case_totals

def test_parse_packsize():
    assert parse_packsize("6/5 lb") == (6, 5.0, "lb")
    assert parse_packsize("12/32 oz") == (12, 32.0, "oz")
    assert parse_packsize("200 ct") == (200, 1.0, "each") or parse_packsize("200 ct")[2] == "each"

def test_case_totals():
    pack, qty, uom = 6, 5.0, "lb"
    oz, each = compute_case_totals(pack, qty, uom)
    assert round(oz,2) == 6*5*16
    assert each is None
