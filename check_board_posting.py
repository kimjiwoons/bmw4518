"""Board posting capability checker.

This script automates a browser using Playwright to determine whether a user
can open a post creation form on a bulletin board style web page.  It accepts
an input JSON file describing the target URLs and optional selectors for
locating the write button, the expected form fields, and any custom modal
containers.  For each URL the script records a result entry that includes a
status (``success`` when the form opens, otherwise ``fail``) and the detected
message that explains the failure reason.  The aggregated results are written
to a CSV file so they can be reviewed or imported into other systems.

Example usage::

    python check_board_posting.py targets.json --output results.csv

See the module level ``DEFAULT_CONFIG`` constant for the heuristics that are
used when a target does not provide explicit selectors.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import queue
import threading
import tkinter as tk
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from playwright.async_api import Dialog, Error, Page, Playwright, async_playwright


DEFAULT_WRITE_SELECTORS: Sequence[str] = (
    "button:has-text(\"글쓰기\")",
    "a:has-text(\"글쓰기\")",
    "button:has-text(\"새 글\")",
    "a:has-text(\"새 글\")",
    "button:has-text(\"Write\")",
    "a:has-text(\"Write\")",
)


DEFAULT_FORM_SELECTORS: Sequence[str] = (
    "form textarea",
    "form input[type='text']",
    "form [contenteditable='true']",
    "iframe[title*='editor']",
)


DEFAULT_MODAL_SELECTORS: Sequence[str] = (
    "div.modal",
    "div[role='dialog']",
    "div.popup",
    "div.layer_pop",
)


@dataclass
class Target:
    """Target configuration describing how to test a single board page."""

    url: str
    write_selectors: Sequence[str] = field(default_factory=lambda: DEFAULT_WRITE_SELECTORS)
    form_selectors: Sequence[str] = field(default_factory=lambda: DEFAULT_FORM_SELECTORS)
    modal_selectors: Sequence[str] = field(default_factory=lambda: DEFAULT_MODAL_SELECTORS)

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "Target":
        url = str(payload["url"])
        write_selectors = tuple(payload.get("write_selectors", DEFAULT_WRITE_SELECTORS))
        form_selectors = tuple(payload.get("form_selectors", DEFAULT_FORM_SELECTORS))
        modal_selectors = tuple(payload.get("modal_selectors", DEFAULT_MODAL_SELECTORS))
        return cls(url, write_selectors, form_selectors, modal_selectors)


@dataclass
class Result:
    """Outcome of a posting capability attempt for a single target."""

    url: str
    status: str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def as_row(self) -> List[str]:
        return [self.timestamp.isoformat(), self.url, self.status, self.message]


async def _click_write_button(page: Page, target: Target, timeout: float) -> Optional[str]:
    """Attempt to click a write button using available selectors.

    Returns an explanatory message if no button could be located.
    """

    for selector in target.write_selectors:
        try:
            locator = page.locator(selector)
            if await locator.count() == 0:
                continue
            await locator.first.click(timeout=timeout)
            logging.debug("Clicked write selector %s for %s", selector, target.url)
            return None
        except Error as err:  # Playwright error (timeout, detached element, etc.)
            logging.debug("Write selector %s failed: %s", selector, err)
            continue
    return "Write button not found"


async def _wait_for_form(page: Page, selectors: Sequence[str], timeout: float) -> bool:
    """Wait for a form-like element to appear after clicking write."""

    for selector in selectors:
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            logging.debug("Form selector %s found", selector)
            return True
        except Error:
            continue
    return False


async def _capture_modal_message(page: Page, selectors: Sequence[str]) -> Optional[str]:
    """Extract text from modal-like containers if they exist."""

    for selector in selectors:
        locator = page.locator(selector)
        try:
            if await locator.count() == 0:
                continue
            text = await locator.first.inner_text()
            text = text.strip()
            if text:
                logging.debug("Modal selector %s produced message: %s", selector, text)
                return text
        except Error:
            continue
    return None


async def check_target(
    playwright: Playwright,
    target: Target,
    timeout: float,
    *,
    headless: bool = True,
) -> Result:
    """Execute the write-form test for a single target."""

    try:
        browser = await playwright.chromium.launch(headless=headless)
    except Error as err:
        message = str(err)
        if "playwright install" in message.lower() or "executable doesn't exist" in message.lower():
            hint = "Playwright browsers are missing. Run `playwright install` once and retry."
        else:
            hint = f"Browser launch error: {err}"
        return Result(target.url, "fail", hint)

    page = await browser.new_page()

    dialog_messages: List[str] = []

    async def handle_dialog(dialog: Dialog) -> None:
        logging.debug("Dialog detected on %s: %s", target.url, dialog.message)
        dialog_messages.append(dialog.message)
        await dialog.dismiss()

    page.on("dialog", handle_dialog)

    try:
        await page.goto(target.url, wait_until="domcontentloaded", timeout=timeout)
        await page.wait_for_load_state("networkidle", timeout=timeout)
    except Error as err:
        await browser.close()
        return Result(target.url, "fail", f"Page load error: {err}")

    missing_button_message = await _click_write_button(page, target, timeout)
    if missing_button_message:
        await browser.close()
        modal_message = await _capture_modal_message(page, target.modal_selectors)
        if dialog_messages:
            message = dialog_messages[-1]
        elif modal_message:
            message = modal_message
        else:
            message = missing_button_message
        return Result(target.url, "fail", message)

    form_found = await _wait_for_form(page, target.form_selectors, timeout)

    modal_message = await _capture_modal_message(page, target.modal_selectors)
    await browser.close()

    if dialog_messages:
        message = dialog_messages[-1]
        return Result(target.url, "fail", message)

    if modal_message:
        return Result(target.url, "fail", modal_message)

    if form_found:
        return Result(target.url, "success", "Form opened")

    return Result(target.url, "fail", "Write form not detected")


def iter_targets(config_path: Path) -> Iterable[Target]:
    """Load :class:`Target` definitions from JSON or plaintext files."""

    suffix = config_path.suffix.lower()
    if suffix in {".txt", ".list", ""}:
        for line_number, raw_line in enumerate(
            config_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "\t" in line or " " in line:
                logging.debug(
                    "Ignoring extra data on line %d in %s: %s",
                    line_number,
                    config_path,
                    raw_line,
                )
                line = line.split()[0]
            yield Target(url=line)
        return

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Config JSON must be a list of target objects")
    for entry in payload:
        if not isinstance(entry, dict):
            raise ValueError("Each target entry must be a JSON object")
        yield Target.from_dict(entry)


async def run_checks(
    config_path: Path,
    timeout: float,
    *,
    headless: bool = True,
    progress_callback: Optional[Callable[[Result], None]] = None,
) -> List[Result]:
    async with async_playwright() as playwright:
        results: List[Result] = []
        for target in iter_targets(config_path):
            logging.info("Checking %s", target.url)
            try:
                result = await check_target(
                    playwright,
                    target,
                    timeout,
                    headless=headless,
                )
            except Exception as err:  # pylint: disable=broad-except
                logging.exception("Unhandled error for %s", target.url)
                result = Result(target.url, "fail", f"Unhandled error: {err}")
            results.append(result)
            if progress_callback:
                progress_callback(result)
        return results


def write_results(results: Sequence[Result], output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "url", "status", "message"])
        for result in results:
            writer.writerow(result.as_row())


def write_failure_log(results: Sequence[Result], output_path: Path) -> None:
    """Persist a plaintext mapping of failed URLs to their messages."""

    failure_lines = [f"{result.url} -> {result.message}" for result in results if result.status != "success"]
    output = "\n".join(failure_lines) if failure_lines else "(no failures)"
    output_path.write_text(output, encoding="utf-8")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to a JSON configuration file with custom selectors.",
    )
    parser.add_argument(
        "--urls",
        type=Path,
        help="Path to a plaintext file containing one board URL per line.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results.csv"),
        help="Destination CSV path for the aggregated results.",
    )
    parser.add_argument(
        "--failure-log",
        type=Path,
        default=Path("failures.txt"),
        help="Plaintext output mapping failing URLs to their popup messages.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15000,
        help="Timeout (in milliseconds) for page operations.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging.",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the graphical interface instead of running via CLI.",
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Show the browser window while running checks.",
    )
    return parser.parse_args(argv)


class CheckerGUI:
    """Tkinter-based GUI for running board posting checks."""

    def __init__(self, root: tk.Tk, *, default_timeout: float, headless: bool = True):
        self.root = root
        self.root.title("Board Posting Checker")

        self.config_var = tk.StringVar()
        self.timeout_var = tk.StringVar(value=str(int(default_timeout)))
        self.headless_var = tk.BooleanVar(value=headless)
        self.status_var = tk.StringVar(value="Idle")

        self.results: List[Result] = []
        self._progress_queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self._worker_thread: Optional[threading.Thread] = None

        self._build_layout()

    def _build_layout(self) -> None:
        padding = {"padx": 8, "pady": 4}

        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        config_frame = ttk.Frame(main_frame)
        config_frame.pack(fill=tk.X, **padding)

        ttk.Label(config_frame, text="Config/URL file:").pack(side=tk.LEFT)
        self.config_entry = ttk.Entry(config_frame, textvariable=self.config_var, width=60)
        self.config_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 4))
        self.browse_button = ttk.Button(config_frame, text="Browse", command=self._browse_config)
        self.browse_button.pack(side=tk.LEFT)

        options_frame = ttk.Frame(main_frame)
        options_frame.pack(fill=tk.X, **padding)

        ttk.Label(options_frame, text="Timeout (ms):").pack(side=tk.LEFT)
        ttk.Entry(options_frame, textvariable=self.timeout_var, width=10).pack(
            side=tk.LEFT, padx=(8, 16)
        )

        self.headless_check = ttk.Checkbutton(
            options_frame,
            text="Run headless",
            variable=self.headless_var,
        )
        self.headless_check.pack(side=tk.LEFT)

        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, **padding)

        self.run_button = ttk.Button(buttons_frame, text="Run Check", command=self._start_check)
        self.run_button.pack(side=tk.LEFT)

        self.save_button = ttk.Button(buttons_frame, text="Save Results", command=self._save_results)
        self.save_button.pack(side=tk.LEFT, padx=(8, 0))
        self.save_button.state(["disabled"])

        self.clear_button = ttk.Button(buttons_frame, text="Clear", command=self._clear_results)
        self.clear_button.pack(side=tk.LEFT, padx=(8, 0))

        ttk.Label(main_frame, textvariable=self.status_var).pack(anchor=tk.W, **padding)

        columns = ("url", "status", "message")
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=12)
        self.tree.heading("url", text="URL")
        self.tree.heading("status", text="Status")
        self.tree.heading("message", text="Message")
        self.tree.column("url", width=260)
        self.tree.column("status", width=80, anchor=tk.CENTER)
        self.tree.column("message", width=360)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _browse_config(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select target list",
            filetypes=(
                ("JSON files", "*.json"),
                ("Text files", "*.txt"),
                ("All files", "*.*"),
            ),
        )
        if file_path:
            self.config_var.set(file_path)

    def _set_running_state(self, running: bool) -> None:
        state = "disabled" if running else "!disabled"
        for widget in (
            self.run_button,
            self.clear_button,
            self.browse_button,
        ):
            widget.state([state])
        self.config_entry.state([state])
        self.headless_check.state([state])
        if running:
            self.save_button.state(["disabled"])

    def _start_check(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            messagebox.showinfo("Checker", "A check is already running.")
            return

        try:
            timeout_value = float(self.timeout_var.get())
        except ValueError:
            messagebox.showerror("Checker", "Timeout must be a numeric value (milliseconds).")
            return

        if timeout_value <= 0:
            messagebox.showerror("Checker", "Timeout must be greater than zero.")
            return

        config_text = self.config_var.get().strip()
        if not config_text:
            messagebox.showerror("Checker", "Please choose a valid config or URL list file.")
            return

        config_path = Path(config_text).expanduser()
        if not config_path.exists():
            messagebox.showerror("Checker", "Please choose a valid config or URL list file.")
            return

        self.results.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.status_var.set("Running...")
        self._set_running_state(True)

        headless = self.headless_var.get()

        self._progress_queue = queue.Queue()

        def worker() -> None:
            try:
                def _progress(result: Result) -> None:
                    self._progress_queue.put(("progress", result))

                results = asyncio.run(
                    run_checks(
                        config_path,
                        timeout_value,
                        headless=headless,
                        progress_callback=_progress,
                    )
                )
                self._progress_queue.put(("complete", results))
            except FileNotFoundError as err:
                self._progress_queue.put(("error", f"Config not found: {err}"))
            except json.JSONDecodeError as err:
                self._progress_queue.put(("error", f"Invalid JSON: {err}"))
            except Exception as err:  # pylint: disable=broad-except
                logging.exception("Worker thread error")
                self._progress_queue.put(("error", str(err)))

        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()
        self.root.after(100, self._poll_queue)

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self._progress_queue.get_nowait()
                if kind == "progress":
                    result = payload  # type: ignore[assignment]
                    self.results.append(result)
                    self.tree.insert(
                        "",
                        tk.END,
                        values=(result.url, result.status, result.message),
                    )
                    self.status_var.set(f"Last checked: {result.url}")
                elif kind == "complete":
                    self.results = list(payload)  # type: ignore[assignment]
                    self.status_var.set("Completed")
                    self._set_running_state(False)
                    self.save_button.state(["!disabled"])
                elif kind == "error":
                    messagebox.showerror("Checker", str(payload))
                    self.status_var.set("Error")
                    self._set_running_state(False)
                    self.save_button.state(["disabled"])
        except queue.Empty:
            pass

        if self._worker_thread and self._worker_thread.is_alive():
            self.root.after(100, self._poll_queue)

    def _save_results(self) -> None:
        if not self.results:
            messagebox.showinfo("Checker", "No results to save yet.")
            return

        default_name = f"results_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
        file_path = filedialog.asksaveasfilename(
            title="Save results",
            initialfile=default_name,
            defaultextension=".csv",
            filetypes=(("CSV", "*.csv"), ("All files", "*.*")),
        )
        if not file_path:
            return

        try:
            destination = Path(file_path)
            write_results(self.results, destination)
            failure_path = destination.with_name(f"{destination.stem}_failures.txt")
            write_failure_log(self.results, failure_path)
            messagebox.showinfo(
                "Checker",
                "Saved results to:\n"
                f"- {destination}\n"
                f"- {failure_path}",
            )
        except OSError as err:
            messagebox.showerror("Checker", f"Failed to save results: {err}")

    def _clear_results(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            messagebox.showinfo("Checker", "Cannot clear while a check is running.")
            return

        self.results.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.status_var.set("Cleared")
        self.save_button.state(["disabled"])


def launch_gui(default_timeout: float, *, headless: bool = True) -> None:
    root = tk.Tk()
    CheckerGUI(root, default_timeout=default_timeout, headless=headless)
    root.mainloop()


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.gui:
        launch_gui(args.timeout, headless=not args.headful)
        return 0

    if args.config and args.urls:
        logging.error("Please supply only one of --config or --urls (not both).")
        return 1

    input_path = args.config or args.urls
    if input_path is None:
        logging.error("Provide --config for JSON input, --urls for a text list, or use --gui.")
        return 1

    try:
        results = asyncio.run(
            run_checks(
                input_path,
                args.timeout,
                headless=not args.headful,
            )
        )
    except FileNotFoundError:
        logging.error("Input file not found: %s", input_path)
        return 1
    except json.JSONDecodeError as err:
        logging.error("Invalid JSON in %s: %s", input_path, err)
        return 1

    write_results(results, args.output)
    if args.failure_log:
        write_failure_log(results, args.failure_log)
    logging.info("Wrote %d result rows to %s", len(results), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
