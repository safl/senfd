from senfd.utils import pascal_to_snake, snake_to_pascal

PASCAL = [
    "Foo",
    "FooBar",
    "SomeVeryLongName",
]


def test_conversions():

    for pascal in PASCAL:
        assert snake_to_pascal(pascal_to_snake(pascal)) == pascal
