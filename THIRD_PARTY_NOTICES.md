# Third-party notices

Every file or snippet copied into Scout from another project is listed here with its source and license. Only MIT, Apache 2.0, and BSD code is ever copied. AGPL, GPL, and unlicensed projects are read for ideas only and Scout writes its own code.

Candidates identified in the reference report are listed in `docs/reference-report.md`; each one is re-checked against its upstream LICENSE file at the moment it is copied, and a row is added here in the same commit.

| Scout file | Borrowed from | License | Notes |
|---|---|---|---|
| `scout/dedupe.py` (`slugify`, `_cap`, `make_key`) | [MadsLorentzen/ai-job-search, tools/job_key.py](https://github.com/MadsLorentzen/ai-job-search/blob/main/tools/job_key.py) | MIT, Copyright (c) 2025 Mads Lorentzen | Adapted 2026-10-14: kept the length-capped slug plus hash idea, dropped the non-Latin-script and audit code. License text below. |

## MIT License (ai-job-search)

Copyright (c) 2025 Mads Lorentzen

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
