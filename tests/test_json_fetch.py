from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'AION2-Event-Overlay'))
from server_data import fetch_snapshot,DATA_URL,FETCH_INTERVAL_SECONDS

class FetchTests(unittest.TestCase):
    def test_only_one_json_request_when_403_or_timeout(self):
        for exc,expected in [(HTTPError(DATA_URL,403,'Forbidden',{},None),'HTTP 403'),(TimeoutError('read timeout'),'15秒')]:
            with patch('server_data.urllib.request.urlopen',side_effect=exc) as request:
                with self.assertRaisesRegex(RuntimeError,expected): fetch_snapshot()
                self.assertEqual(request.call_count,1)
                self.assertEqual(request.call_args.args[0].full_url,DATA_URL)

    def test_no_html_fallback_when_server_returns_html(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,*args): return b'<html>access denied</html>'
        with patch('server_data.urllib.request.urlopen',return_value=Response()) as request:
            with self.assertRaisesRegex(RuntimeError,'JSONではない'): fetch_snapshot()
            self.assertEqual(request.call_count,1)
        self.assertEqual(FETCH_INTERVAL_SECONDS,900)

if __name__=='__main__': unittest.main()
