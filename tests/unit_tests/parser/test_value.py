import pytest
from nnc.parser.ast.value import FloatValue


class TestValue:
    def test_init_float(self):
        v = FloatValue(1.23)
        assert v.value == 1.23

    def test_init_int(self):
        v = FloatValue(5)
        assert v.value == 5.0

    def test_init_str(self):
        v = FloatValue("3.14")
        assert v.value == 3.14

    def test_str(self):
        v = FloatValue(2.71)
        assert str(v) == "2.71"

    def test_repr(self):
        v = FloatValue(1.23)
        assert repr(v) == "FloatValue(1.23)"

    def test_float(self):
        v = FloatValue(3.14)
        assert float(v) == 3.14

    def test_add(self):
        v1 = FloatValue(1.23)
        v2 = FloatValue(2.34)
        result = v1 + v2
        assert result.value == 3.57

    def test_sub(self):
        v1 = FloatValue(2.35)
        v2 = FloatValue(1.23)
        result = v1 - v2
        assert result.value == 1.12

    def test_mul(self):
        v1 = FloatValue(2)
        v2 = FloatValue(3)
        result = v1 * v2
        assert result.value == 6

    def test_floordiv(self):
        v1 = FloatValue(7)
        v2 = FloatValue(3)
        result = v1 // v2
        assert result.value == 2

    def test_truediv(self):
        v1 = FloatValue(7)
        v2 = FloatValue(3)
        result = v1 / v2
        assert result.value == 7 / 3

    def test_mod(self):
        v1 = FloatValue(7)
        v2 = FloatValue(3)
        result = v1 % v2
        assert result.value == 1

    def test_pow(self):
        v1 = FloatValue(2)
        v2 = FloatValue(3)
        result = v1**v2
        assert result.value == 8

    def test_lt(self):
        v1 = FloatValue(1)
        v2 = FloatValue(2)
        assert (v1 < v2) == True

    def test_gt(self):
        v1 = FloatValue(2)
        v2 = FloatValue(1)
        assert (v1 > v2) == True

    def test_le(self):
        v1 = FloatValue(2)
        v2 = FloatValue(2)
        assert (v1 <= v2) == True

    def test_eq(self):
        v1 = FloatValue(2)
        v2 = FloatValue(2)
        assert (v1 == v2) == True

    def test_ne(self):
        v1 = FloatValue(2)
        v2 = FloatValue(3)
        assert (v1 != v2) == True

    def test_ge(self):
        v1 = FloatValue(2)
        v2 = FloatValue(2)
        v3 = FloatValue(3)
        assert (v1 >= v2) == True
        assert (v3 >= v2) == True

    def test_init_error(self):
        with pytest.raises(ValueError):
            v = FloatValue([])

    def test_type(self):
        v = FloatValue(1.23)
        assert isinstance(v.value, float) == True


if __name__ == "__main__":
    pytest.main()  # pragma: no cover
