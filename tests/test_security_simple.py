import unittest
from pathlib import Path

class TestSecurityTraversal(unittest.TestCase):
    def test_path_name_behavior_pdf(self):
        # Basic verification of the fix principle
        malicious = "../../../etc/passwd.pdf"
        safe = Path(malicious).name
        self.assertEqual(safe, "passwd.pdf")

        malicious2 = "some/path/traversal/file.pdf"
        safe2 = Path(malicious2).name
        self.assertEqual(safe2, "file.pdf")

    def test_path_name_behavior_normal(self):
        normal = "documento.pdf"
        safe = Path(normal).name
        self.assertEqual(safe, "documento.pdf")

if __name__ == "__main__":
    unittest.main()
