Run python generate_report.py
Traceback (most recent call last):
Fetching news...
  File "/home/runner/work/cartera-reporte/cartera-reporte/generate_report.py", line 129, in <module>
    data = json.loads(raw)
           ^^^^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.11.15/x64/lib/python3.11/json/__init__.py", line 346, in loads
  TSLA: 3 items
  HIMS: 3 items
  DUOL: 3 items
  BMNR: 3 items
  LODE: 3 items
  HGRAF: 3 items
  HBFG: 3 items
  ABX: 3 items
  3350.T: 3 items
  BILD: 2 items
  LIB: 3 items
  TTT: 3 items
Calling Claude API for stock analysis...
    return _default_decoder.decode(s)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.11.15/x64/lib/python3.11/json/decoder.py", line 337, in decode
    obj, end = self.raw_decode(s, idx=_w(s, 0).end())
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.11.15/x64/lib/python3.11/json/decoder.py", line 353, in raw_decode
    obj, end = self.scan_once(s, idx)
               ^^^^^^^^^^^^^^^^^^^^^^
json.decoder.JSONDecodeError: Unterminated string starting at: line 218 column 18 (char 12912)
Error: Process completed with exit code 1.
