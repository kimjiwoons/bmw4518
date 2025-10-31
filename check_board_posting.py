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
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

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
    timestamp: datetime = field(default_factory=datetime.utcnow)

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


async def check_target(playwright: Playwright, target: Target, timeout: float) -> Result:
    """Execute the write-form test for a single target."""

    browser = await playwright.chromium.launch(headless=True)
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
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Config JSON must be a list of target objects")
    for entry in payload:
        if not isinstance(entry, dict):
            raise ValueError("Each target entry must be a JSON object")
        yield Target.from_dict(entry)


async def run_checks(config_path: Path, timeout: float) -> List[Result]:
    async with async_playwright() as playwright:
        results: List[Result] = []
        for target in iter_targets(config_path):
            logging.info("Checking %s", target.url)
            try:
                result = await check_target(playwright, target, timeout)
            except Exception as err:  # pylint: disable=broad-except
                logging.exception("Unhandled error for %s", target.url)
                result = Result(target.url, "fail", f"Unhandled error: {err}")
            results.append(result)
        return results


def write_results(results: Sequence[Result], output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "url", "status", "message"])
        for result in results:
            writer.writerow(result.as_row())


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "config",
        type=Path,
        help="Path to JSON file containing target configuration.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results.csv"),
        help="Destination CSV path for the aggregated results.",
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
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        results = asyncio.run(run_checks(args.config, args.timeout))
    except FileNotFoundError:
        logging.error("Config file not found: %s", args.config)
        return 1
    except json.JSONDecodeError as err:
        logging.error("Invalid JSON in %s: %s", args.config, err)
        return 1

    write_results(results, args.output)
    logging.info("Wrote %d result rows to %s", len(results), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
