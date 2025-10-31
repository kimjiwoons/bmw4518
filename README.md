# Board posting capability checker

This repository contains a Playwright-based automation script that verifies
whether a bulletin board allows visitors to open the post creation form.  It
is useful when you maintain a list of community boards and need to
programmatically confirm that posting is possible without manual inspection.

## Features

* Navigates to each target URL and attempts to trigger the write action using a
  configurable list of selectors (defaulting to common Korean bulletin board
  labels such as `글쓰기`).
* Detects browser dialogs and in-page modal windows to capture the failure
  message shown when posting is restricted (e.g., requires membership).
* Records the outcome for every board (`success` when the form loads, `fail`
  otherwise) in a CSV file along with the detected message.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install
```

## Configuration

Create a JSON file containing a list of targets.  Each entry must include the
`url` and can optionally override the selectors that the script will use:

```json
[
  {
    "url": "https://example.com/board",
    "write_selectors": ["button:has-text(\"글쓰기\")"],
    "form_selectors": ["form textarea"],
    "modal_selectors": ["div.modal"]
  }
]
```

Every field is optional except `url`.  When omitted, the script falls back to a
set of heuristic selectors that work for many boards.

## Usage

Run the checker and provide the configuration JSON.  By default the results are
written to `results.csv` in the current directory.

```bash
python check_board_posting.py targets.json --output board_results.csv --verbose
```

The CSV file contains the following columns:

1. `timestamp`: UTC time when the check finished.
2. `url`: Target URL from the configuration file.
3. `status`: Either `success` or `fail`.
4. `message`: Captured popup text or a diagnostic note explaining why the
   attempt failed.

## Limitations

* Sites that require authentication must be configured with additional steps
  (e.g., logging in) before running the checker.
* Single-page applications might use dynamic selectors; update the target
  configuration accordingly when the defaults are insufficient.
* The script does not submit any content to the boards—it only checks whether
  the writing interface becomes available.
