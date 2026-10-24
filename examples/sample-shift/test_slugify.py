import unittest

from slugify import slugify


class TestSlugify(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_collapses_separators(self):
        self.assertEqual(slugify("a   b---c"), "a-b-c")

    def test_strips_punctuation(self):
        self.assertEqual(slugify("  Rust & Python!  "), "rust-python")

    def test_keeps_unicode_letters(self):
        self.assertEqual(slugify("Zink-Iod Akku"), "zink-iod-akku")
        self.assertEqual(slugify("锌碘电池"), "锌碘电池")

    def test_empty(self):
        self.assertEqual(slugify("   "), "")


if __name__ == "__main__":
    unittest.main()
