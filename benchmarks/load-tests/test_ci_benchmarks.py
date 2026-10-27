"""Regression checks for the clients used by the native CI benchmarks."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from read_only import GeodeShellClient, run_worker
from vector_distance import GeodeVectorClient, distance_query


class BenchmarkClientTest(unittest.TestCase):
    def test_compose_runner_rejects_server_errors_and_preserves_query(self):
        # Exercise the real shell runner without starting a host container.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docker = root / "docker"
            docker.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "from pathlib import Path\n"
                "Path(os.environ['CAPTURE']).write_text(json.dumps(sys.argv[1:]))\n"
                "print(os.environ['RESPONSE'])\n"
            )
            docker.chmod(0o700)
            capture = root / "args.json"
            query = "RETURN 'literal $(touch should-not-exist);'"
            env = {"PATH": str(root) + os.pathsep + os.environ["PATH"], "CAPTURE": str(capture)}
            with patch.dict(os.environ, env):
                for response, expected in [
                    ('{"status_class":"00000","rows":[{"value":1}]}', True),
                    ('{"status_class":"42000","error":"invalid"}', False),
                    ('{"status_class":"00000","error_code":"failure"}', False),
                    ("usage only", False),
                    ("{broken", False),
                ]:
                    with self.subTest(response=response), patch.dict(os.environ, {"RESPONSE": response}):
                        self.assertEqual(GeodeShellClient().execute(query)[0], expected)
                args = json.loads(capture.read_text())
                self.assertEqual(args[-1], query)
                self.assertIn('--ca-cert /data/server.crt', args[6])
                self.assertIn('"$GEODE_ADMIN_PASSWORD"', args[6])
                self.assertFalse((root / "should-not-exist").exists())

    def test_direct_client_also_requires_successful_server_status(self):
        response = subprocess.CompletedProcess([], 0, '{"status_class":"42000","error":"bad query"}', '')
        with patch("read_only.subprocess.run", return_value=response):
            self.assertFalse(GeodeShellClient(use_docker=False).execute("RETURN 1")[0])

    def test_vector_result_requires_a_finite_number(self):
        client = GeodeVectorClient()
        for value, expected in [(None, False), (True, False), ("NaN", False), ("Infinity", False), ("oops", False), (0, True), ("1.414214", True)]:
            with self.subTest(value=value):
                response = json.dumps({"status_class": "00000", "rows": [{"distance": value}]})
                self.assertEqual(client.valid_response(response), expected)
        self.assertFalse(client.valid_response('{"status_class":"00000","rows":[]}'))

    def test_all_vector_modes_use_supported_functions(self):
        for kind, function in [("euclidean", "vector_l2"), ("cosine", "vector_cosine"), ("manhattan", "manhattan"), ("dot_product", "vector_dot")]:
            with self.subTest(kind=kind):
                self.assertEqual(distance_query(kind, [1.0], [2.0]), f"RETURN {function}(vectorf32([1.0]), vectorf32([2.0])) AS distance")

    def test_read_workers_overlap_instead_of_blocking_the_event_loop(self):
        barrier = threading.Barrier(2, timeout=2)

        def execute(_client, _query):
            barrier.wait()
            time.sleep(0.02)
            return True, 20.0

        async def run():
            results = []
            await asyncio.gather(*(run_worker(i, "RETURN 1", 0.01, results, True) for i in range(2)))
            return results

        with patch.object(GeodeShellClient, "execute", execute):
            self.assertEqual(asyncio.run(run()), [(True, 20.0), (True, 20.0)])


if __name__ == "__main__":
    unittest.main()
