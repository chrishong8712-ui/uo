import tempfile
import unittest
from pathlib import Path

from core.workflow import validate_output, write_new_script


class WriteNewScriptTests(unittest.TestCase):
    def test_writes_new_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "out.razor"
            validate_output(path)
            write_new_script(path, "setvar! A 1\n")
            self.assertEqual(path.read_text(encoding="utf-8"), "setvar! A 1\n")

    def test_existing_file_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "out.razor"
            path.write_text("keep", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                validate_output(path)
            with self.assertRaises(FileExistsError):
                write_new_script(path, "new")
            self.assertEqual(path.read_text(encoding="utf-8"), "keep")

    def test_missing_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileNotFoundError):
                validate_output(Path(folder) / "missing" / "out.razor")


if __name__ == "__main__":
    unittest.main()
