# Board posting capability checker

This repository contains a Playwright-based automation toolkit that verifies
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
* Includes a simple Tkinter GUI so non-technical users can run checks, monitor
  progress, and export the results.

## Getting the project onto your computer

There are two convenient ways to bring the project files to your PC:

1. **Clone the repository (recommended when Git is available).**
   ```bash
   git clone https://github.com/<your-account>/<repo-name>.git
   cd <repo-name>
   ```
   Replace `<your-account>/<repo-name>` with the path of your GitHub fork. Git
   preserves the full history and lets you keep up with future changes via
   `git pull`.

2. **Download a ZIP archive from GitHub.** On the repository page click
   **Code → Download ZIP**, unzip it on your computer, and open the folder in a
   terminal. This approach works even when Git is not installed—just remember to
   download a fresh copy whenever the repository changes.

If you prefer to copy the files manually (for example, by using the clipboard),
create the four files listed in this repository—`check_board_posting.py`,
`example_targets.json`, `requirements.txt`, and `README.md`—and paste the
corresponding contents into each file. Using Git clone or the ZIP download is
less error-prone because it guarantees all files and directories match the
original structure.

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

### Graphical interface

Launch the GUI directly (with no arguments) or by passing the `--gui` flag. Use
the “Browse” button to choose your configuration JSON, adjust the timeout if
necessary, and click **Run Check**. Once the scan finishes you can export the
table to CSV.

```bash
python check_board_posting.py
# or
python check_board_posting.py --gui
```

To visually observe browser activity, uncheck **Run headless** inside the GUI
before starting the scan.

### Command line

Run the checker and provide the configuration JSON.  By default the results are
written to `results.csv` in the current directory.

```bash
python check_board_posting.py --config targets.json --output board_results.csv --verbose
```

To watch the browser while running through the command line, pass `--headful`.

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
