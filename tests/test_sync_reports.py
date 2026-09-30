import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from scripts.sync_reports import discover, validate_url
from scripts.build_data import extract_pages, paragraphs_by_page, report_date


class ReportImportTests(unittest.TestCase):
    def test_ssc_column_deduplicates_and_excludes_future(self):
        row = '<tr><td>2025</td><td><a href="c.pdf">Council June</a></td><td>AP</td><td><a href="https://files.npfmc.org/ssc.pdf">SSC June</a></td></tr>'
        future = row.replace('2025', '2027')
        reports = discover('<table>' + row + row + future + '</table>', 2000, date(2026, 9, 30))
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]['month'], 'June')
        self.assertTrue(reports[0]['official_report_url'].endswith('/ssc.pdf'))

    def test_empty_archive_fails(self):
        with self.assertRaises(ValueError):
            discover('<html>Unavailable</html>', 2000, date(2026, 9, 30))

    def test_source_host_allowlist(self):
        for url in ['https://npfmc.org.evil.com/a.pdf', 'file:///a.pdf', 'http://files.npfmc.org/a.pdf']:
            with self.assertRaises(ValueError):
                validate_url(url)

    def test_physical_pages_keep_blank_pages(self):
        with patch('scripts.build_data.subprocess.run', return_value=SimpleNamespace(stdout='First paragraph long enough to be indexed.\f\fThird paragraph long enough to be indexed.\f')):
            pages = extract_pages(Path('example.pdf'))
        self.assertEqual(len(pages), 3)
        self.assertEqual([r['page'] for r in paragraphs_by_page(pages)], [1, 3])

    def test_filename_dates(self):
        for name, expected in [('SSC February 2026', ('2026', 'February')),
                               ('SSCOct2019', ('2019', 'Oct')),
                               ('SSC_DRAFT_Sept16_Minutes_NOV2016BB', ('2016', 'Sept'))]:
            self.assertEqual(report_date(name, ''), expected)


if __name__ == '__main__':
    unittest.main()
