"""Regression for a real, incorrect high-confidence desktop OCR reading."""
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock
from scripts.desktop import command
from scripts.ocr import read_lines


@unittest.skipUnless(shutil.which('tesseract') and shutil.which('magick'), 'OCR dependencies required')
class DisplayOCRTests(unittest.TestCase):
    def test_large_digits_are_read_from_pixels_without_expected_value_hint(self):
        image = Path(__file__).parent/'fixtures/calculator-display.png'
        with tempfile.TemporaryDirectory() as scratch:
            lines = read_lines(image, scratch, command)
        display = [line['text'] for line in lines if line['bounds'][1] < 300]
        self.assertEqual(display, ['883'])

    def test_literal_quote_does_not_swallow_following_tsv_rows(self):
        header='level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n'
        data=header+'5\t1\t1\t1\t1\t1\t10\t10\t20\t20\t90\t"\n'+'5\t1\t2\t1\t1\t1\t10\t50\t100\t20\t90\tFollowing\n'
        runner=Mock(side_effect=lambda args,**kwargs:data if args[0]=='tesseract' else '')
        with tempfile.TemporaryDirectory() as scratch:
            lines=read_lines('unused.png',scratch,runner)
        self.assertEqual([line['text'] for line in lines],['"','Following'])


if __name__ == '__main__':
    unittest.main()
