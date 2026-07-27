from app.web.router import _category, _level


def test_product_categories_for_map_filters():
    assert _category("CB LITE ORD") == "Beer"
    assert _category("WURKZ") == "Beverage"
    assert _category("CAMBODIA WATER 500mL") == "Water"


def test_movement_map_uses_three_business_bands():
    assert _level(0)[0] == "Very Low"
    assert _level(4)[0] == "Very Low"
    assert _level(5)[0] == "Medium"
    assert _level(8)[0] == "Medium"
    assert _level(9)[0] == "Very Strong"
    assert _level(10)[0] == "Very Strong"
