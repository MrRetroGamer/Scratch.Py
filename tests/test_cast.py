import math

from scratch_py.util import jscompat as cast


class TestNumberFormatting:
    def test_integers(self):
        assert cast.num_to_string(5) == "5"
        assert cast.num_to_string(5.0) == "5"
        assert cast.num_to_string(-12.0) == "-12"

    def test_fixed_range(self):
        assert cast.num_to_string(0.000001) == "0.000001"
        assert cast.num_to_string(123.456) == "123.456"
        assert cast.num_to_string(1e20) == "100000000000000000000"

    def test_exponential(self):
        assert cast.num_to_string(1e21) == "1e+21"
        assert cast.num_to_string(1e-7) == "1e-7"
        assert cast.num_to_string(1.5e22) == "1.5e+22"

    def test_specials(self):
        assert cast.num_to_string(float("nan")) == "NaN"
        assert cast.num_to_string(float("inf")) == "Infinity"
        assert cast.num_to_string(float("-inf")) == "-Infinity"
        assert cast.num_to_string(-0.0) == "0"


class TestStringToNumber:
    def test_basic(self):
        assert cast.to_number("42") == 42
        assert cast.to_number(" -3.5 ") == -3.5
        assert cast.to_number("") == 0
        assert cast.to_number("   ") == 0

    def test_invalid_is_nan(self):
        assert math.isnan(cast.to_number("abc"))
        assert math.isnan(cast.to_number("1_0"))

    def test_hex(self):
        assert cast.to_number("0x10") == 16
        assert cast.to_number("Infinity") == float("inf")


class TestBoolean:
    def test_strings(self):
        assert cast.to_bool("") is False
        assert cast.to_bool("0") is False
        assert cast.to_bool("FALSE") is False
        assert cast.to_bool("false") is False
        assert cast.to_bool("00") is True
        assert cast.to_bool("hello") is True

    def test_numbers(self):
        assert cast.to_bool(0) is False
        assert cast.to_bool(0.0) is False
        assert math.isnan(float("nan"))
        assert cast.to_bool(7) is True


class TestCompareEquals:
    def test_numeric_compare(self):
        assert cast.compare(2, 10) == -1
        assert cast.compare("10", "9") == 1
        assert cast.compare("abc", "abd") == -1

    def test_case_insensitive_equality(self):
        assert cast.equals("Apple", "apple") is True
        assert cast.equals("a", "A") is True

    def test_mixed(self):
        assert cast.equals(0, "") is False
        assert cast.equals("", "0") is False
        assert cast.equals("1", 1) is True


class TestJsMath:
    def test_mod_sign_follows_dividend(self):
        assert cast.js_mod(-7, 3) == -1
        assert cast.js_mod(7, -3) == 1
        assert cast.js_mod(7, 3) == 1
        assert math.isnan(cast.js_mod(5, 0))

    def test_round_half_up(self):
        assert cast.js_round(2.5) == 3
        assert cast.js_round(-2.5) == -2
        assert cast.js_round(0.5) == 1
        assert cast.js_round(-0.5) == 0

    def test_math_op_degrees(self):
        assert abs(cast.math_op("sin", "90") - 1) < 1e-9
        assert abs(cast.math_op("cos", "180") + 1) < 1e-9
        assert cast.math_op("sqrt", 9) == 3
        assert math.isnan(cast.math_op("sqrt", -1))

    def test_division_by_zero(self):
        assert cast.js_divide(1, 0) == float("inf")
        assert cast.js_divide(-1, 0) == float("-inf")


class TestListsAndStrings:
    def test_letter_of(self):
        assert cast.letter_of(1, "abc") == "a"
        assert cast.letter_of(3, "abc") == "c"
        assert cast.letter_of(4, "abc") == ""
        assert cast.letter_of(0, "abc") == ""

    def test_contains(self):
        assert cast.contains("Hello World", "WORLD") is True
        assert cast.contains("abc", "z") is False

    def test_list_index(self):
        assert cast.to_list_index(2, 3) == 2
        assert cast.to_list_index(0, 3) is None
        assert cast.to_list_index(4, 3) is None
        assert cast.to_list_index(1.5, 3) is None
        assert cast.to_list_index("last", 3) is None


class TestPickRandom:
    def test_whole_numbers(self):
        for _ in range(30):
            value = cast.pick_random(1, 5)
            assert isinstance(value, int)
            assert 1 <= value <= 5

    def test_floats(self):
        value = cast.pick_random(0.5, 2.5)
        assert 0.5 <= value <= 2.5

    def test_reversed_bounds(self):
        for _ in range(20):
            value = cast.pick_random(5, 1)
            assert 1 <= value <= 5
