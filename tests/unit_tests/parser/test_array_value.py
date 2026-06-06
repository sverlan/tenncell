from nnc.parser.ast.value import ArrayValue


class TestArrayValue:
    def test_init(self):
        v = ArrayValue(int, [1, 2, 3])
        assert v.value == [1, 2, 3]
        assert v.base_type == int

    def test_str(self):
        v = ArrayValue(int, [1, 2, 3])
        assert str(v) == "[1,2,3]"

    def test_repr(self):
        v = ArrayValue(int, [1, 2, 3])
        assert repr(v) == "ArrayValue(<class 'int'>,[1, 2, 3])"

    def test_getitem(self):
        v = ArrayValue(int, [1, 2, 3])
        assert v[0] == 1
        assert v[1] == 2
        assert v[2] == 3

    def test_setitem(self):
        v = ArrayValue(int, [1, 2, 3])
        v[0] = 4
        assert v[0] == 4
        v[1] = 5
        assert v[1] == 5
        v[2] = 6
        assert v[2] == 6

    def test_append(self):
        v = ArrayValue(int, [1, 2, 3])
        v.append(4)
        assert v[3] == 4
        v.append(5)
        assert v[4] == 5
        v.append(6)
        assert v[5] == 6

    def test_len(self):
        v = ArrayValue(int, [1, 2, 3])
        assert len(v) == 3
        v.append(4)
        assert len(v) == 4
        v.append(5)
        assert len(v) == 5
        v.append(6)
        assert len(v) == 6

    def test_iter(self):
        v = ArrayValue(int, [1, 2, 3])
        assert list(v) == [1, 2, 3]
        v.append(4)
        assert list(v) == [1, 2, 3, 4]
        v.append(5)
        assert list(v) == [1, 2, 3, 4, 5]
        v.append(6)
        assert list(v) == [1, 2, 3, 4, 5, 6]

    def test_contains(self):
        v = ArrayValue(int, [1, 2, 3])
        assert 1 in v
        assert 2 in v
        assert 3 in v
        assert 4 not in v
        assert 5 not in v
        assert 6 not in v
        v.append(4)
        assert 1 in v
        assert 2 in v
        assert 3 in v
        assert 4 in v
        assert 5 not in v
        assert 6 not in v
        v.append(5)
        assert 1 in v
        assert 2 in v
        assert 3 in v
        assert 4 in v
        assert 5 in v
        assert 6 not in v
        v.append(6)
        assert 1 in v
        assert 2 in v
        assert 3 in v
        assert 4 in v
        assert 5 in v
        assert 6 in v

    def test_eq(self):
        v1 = ArrayValue(int, [1, 2, 3])
        v2 = ArrayValue(int, [1, 2, 3])
        assert v1 == v2
        v1.append(4)
        assert v1 != v2
        v2.append(4)
        assert v1 == v2
        v1.append(5)
        assert v1 != v2
        assert not (v1 == 4)
        v2.append(5)
        assert v1 == v2
        v1.append(6)
        assert v1 != v2
        v2.append(6)
        assert v1 == v2


if __name__ == "__main__":
    pytest.main()  # pragma: no cover
