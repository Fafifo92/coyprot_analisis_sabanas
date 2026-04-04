import unittest
from pathlib import Path

class TestPathSanitization(unittest.TestCase):
    def test_path_sanitization(self):
        filename = "../../etc/passwd.pdf"
        safe_filename = Path(filename).name
        self.assertEqual(safe_filename, "passwd.pdf")

if __name__ == "__main__":
    unittest.main()
