#!/usr/bin/env python3
"""Query errors must fail verification even when the CLI exits zero."""
import contextlib
import io
from pathlib import Path
import runpy
import unittest

check = runpy.run_path(str(Path(__file__).with_name("check-geode-response.py")))["check"]
statements = runpy.run_path(str(Path(__file__).with_name("gql-batch.py")))["statements"]


class QueryResponseTest(unittest.TestCase):
    def test_response_status(self):
        cases = [
            ('{"status_class":"00000","rows":[]}\n', 0),
            ('{"status_class":"01000"}\n', 0),
            ('{"status_class":"02000"}\n', 0),
            ('Executing from file: /tmp/query.gql\n{"status_class":"00000"}\n', 0),
            ('{"status_class":"0A000","error":"unsupported"}\n', 1),
            ('usage only\n', 1),
            ('{broken\n', 1),
            ('{"status_class":"00000"}\n{"status_class":"42000","error":"invalid"}\n', 1),
        ]
        for response, expected in cases:
            with self.subTest(response=response), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(check(io.StringIO(response)), expected)

    def test_batch_preserves_query_boundaries(self):
        source = "-- heading\nBEGIN; RETURN 'semi;colon'; /* note */ ROLLBACK;"
        self.assertEqual(list(statements(source)), ["BEGIN", "RETURN 'semi;colon'", "ROLLBACK"])
        source = "RETURN 'it''s -- text' AS x; RETURN {x: 1, y: '/*literal*/'};"
        self.assertEqual(list(statements(source)), ["RETURN 'it''s -- text' AS x", "RETURN {x: 1, y: '/*literal*/'}"])
        self.assertEqual(list(statements("RETURN\n1 /* inline */ + 2; // tail")), ["RETURN 1   + 2"])
        self.assertEqual(list(statements("FOR x IN [1] { CREATE (:N); };")), ["FOR x IN [1] { CREATE (:N); }"])

    def test_batch_rejects_incomplete_input(self):
        for source in ["RETURN 'unfinished;", "RETURN 1", "/* no end", "RETURN {x: 1;", "RETURN }; "]:
            with self.subTest(source=source), self.assertRaises(ValueError):
                list(statements(source))


if __name__ == "__main__":
    unittest.main()
