from pathlib import Path
import tempfile
import unittest
from file_lookup import find_matches, query_name

class LookupTests(unittest.TestCase):
    def test_name_extraction(self):
        self.assertEqual(query_name('读取我文档里three feet under中的故事背景大概讲了什么'),'three feet under')

    def test_names_spaces_and_skipped_folders(self):
        with tempfile.TemporaryDirectory() as base:
            root=Path(base);project=root/'Three-Feet_Under';project.mkdir()
            (project/'story.txt').write_text('story')
            hidden=root/'node_modules';hidden.mkdir();(hidden/'three feet under.md').touch()
            self.assertEqual(find_matches('three feet under',[root]),[project.resolve()])
            (root/'three feet under draft.txt').touch()
            self.assertEqual(len(find_matches('three feet under',[root])),2)

    def test_empty_and_missing_names_do_not_return_unrelated_files(self):
        with tempfile.TemporaryDirectory() as base:
            (Path(base)/'README.md').touch()
            self.assertEqual(find_matches('',[base]),[])
            self.assertEqual(find_matches('unrelated project',[base]),[])

if __name__=='__main__': unittest.main()
