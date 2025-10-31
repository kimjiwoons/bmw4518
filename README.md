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
* Accepts either a JSON configuration or a plain text list of URLs (one per
  line) so you can quickly check large batches without preparing selectors.
* Generates a companion failure log where each popup message is stored as
  `URL -> message` for easy review.

## Installation

### Bringing the project to your PC

Choose whichever transfer method is easiest for you:

* **Clone from GitHub (권장).**
  1. 이 작업물을 GitHub 저장소에 올리거나(fork/푸시) 준비합니다.
  2. 로컬 PC에서 터미널(CMD/PowerShell/macOS Terminal 등)을 열고 아래
     명령을 실행합니다.
     ```bash
     git clone https://github.com/<your-account>/<your-repo>.git
     cd <your-repo>
     ```
  3. 이어서 아래 가상환경/설치 단계를 진행합니다.

* **GitHub에 새 저장소를 만들고 업로드.**
  1. <https://github.com/new> 에서 빈 저장소를 생성합니다. (예: `board-checker`)
  2. 로컬 PC에서 이 프로젝트 폴더로 이동한 뒤 Git을 초기화하고 첫 커밋을 만듭니다.
     ```bash
     git init
     git add .
     git commit -m "Add board posting checker"
     git branch -M main
     ```
  3. 새 저장소 주소를 원격(origin)으로 연결한 후 업로드합니다.
     ```bash
     git remote add origin https://github.com/<your-account>/board-checker.git
     git push -u origin main
     ```
  4. GitHub 저장소 페이지를 새로고침하면 코드가 업로드된 것을 확인할 수 있습니다.

* **클립보드/ZIP으로 직접 복사.**
  1. 이 환경에서 필요한 파일(`check_board_posting.py`,
     `example_targets.json`, `requirements.txt`, `README.md`)을 열어 내용을
     복사합니다.
  2. 로컬 PC에서 새 폴더를 만들고 동일한 파일 이름으로 저장합니다. 또는
     GitHub 웹 UI에서 **Add file → Upload files**를 사용해 한 번에 올린 후,
     “Download ZIP”으로 내려받아도 됩니다.
  3. 파일 구성이 모두 준비되면 아래 설치 단계를 실행합니다.

### Python 의존성 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install
```

## Configuration

You can describe targets in two different formats depending on how much control
you need.

### 1. Plain text list (quick start)

Create a `.txt` file where each line contains a single board URL:

```
https://www.bilie.kr/bbs/board.php?bo_table=n_notice&wr_id=6
https://www.hanbangbiofair.org/bbs/board.php?bo_table=w2_c&wr_id=5
https://www.gmsenior.or.kr/bbs/board.php?bo_table=0406
```

Blank lines and lines starting with `#` are ignored. This format uses the
script's default selectors (`글쓰기`, `새 글`, etc.) and is perfect when all you
need is a quick success/failure scan based on whether a popup appears.

### 2. JSON configuration (advanced control)

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
the “Browse” button to choose either a JSON configuration or a text file of
URLs, adjust the timeout if necessary, and click **Run Check**. Once the scan
finishes you can export the table to CSV. The GUI will also create a
`*_failures.txt` file next to your CSV, containing one `URL -> message` line per
failure.

```bash
python check_board_posting.py
# or
python check_board_posting.py --gui
```

To visually observe browser activity, uncheck **Run headless** inside the GUI
before starting the scan.

### Command line

Run the checker and provide either a JSON configuration (`--config`) or a text
list of URLs (`--urls`).  By default the results are written to `results.csv`
and a failure log is written to `failures.txt` in the current directory.

```bash
python check_board_posting.py --urls board_urls.txt --output board_results.csv --verbose
```

To watch the browser while running through the command line, pass `--headful`.

The failure log lists every popup or modal message that caused a failure using
the format `https://example.com -> 회원가입후 글쓰기`. Successful rows are still
available in the CSV output.

The CSV file contains the following columns:

1. `timestamp`: UTC time when the check finished.
2. `url`: Target URL from the configuration file.
3. `status`: Either `success` or `fail`.
4. `message`: Captured popup text or a diagnostic note explaining why the
   attempt failed.

## Troubleshooting

- **`BrowserType.launch: Executable doesn't exist … playwright install`** –
  Playwright manages its own browsers. Run `playwright install` once inside the
  environment where you installed the dependencies so Chromium/Firefox/WebKit
  can be downloaded.

## Limitations

* Sites that require authentication must be configured with additional steps
  (e.g., logging in) before running the checker.
* Single-page applications might use dynamic selectors; update the target
  configuration accordingly when the defaults are insufficient.
* The script does not submit any content to the boards—it only checks whether
  the writing interface becomes available.
