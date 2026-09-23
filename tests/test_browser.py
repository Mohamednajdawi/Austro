"""Browser-to-action flow, with real inference when explicitly requested."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

from acg_agent_platform.services.store import Store


def test_browser_draft_review_execute(tmp_path: Path) -> None:
    store = Store(tmp_path / "browser.sqlite3")
    store.initialize()
    store.seed_demo()
    store.seed_business_examples()
    alice_token = store.issue_session("alice", 3600)
    reviewer_token = store.issue_session("reviewer", 3600)
    finance_token = store.issue_session("bob", 3600)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    environment = os.environ.copy()
    environment.update(
        DATABASE_PATH=str(store.path),
        PORT=str(port),
        MODEL_PROVIDER="ollama"
        if os.environ.get("ACG_TEST_REAL_MODEL") == "1"
        else "fake",
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "acg_agent_platform", "serve"],
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                with urlopen(base + "/health", timeout=0.5):
                    break
            except URLError:
                time.sleep(0.1)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(base)
            page.get_by_label("Session token", exact=True).fill(alice_token)
            page.get_by_role("button", name="Connect", exact=True).click()
            expect(page.locator("#secured")).to_be_visible()
            page.get_by_role("button", name="IT-001 · VPN support").click()
            page.get_by_role("button", name="Generate source-backed draft").click()
            expect(page.locator("#runPanel")).to_be_visible(timeout=240000)
            expect(page.locator("#runMeta")).to_contain_text("awaiting_review")
            draft = page.locator("#draft").inner_text()
            assert len(draft) > 30
            if environment["MODEL_PROVIDER"] == "ollama":
                expect(page.locator("#runMeta")).to_contain_text("ollama/")
                assert "Synthetic draft" not in draft
            page.get_by_role("button", name="Send exact note for approval").click()
            expect(page.locator(".proposal")).to_have_count(1)
            expect(
                page.get_by_role("button", name="Approve exact action")
            ).to_have_count(0)
            page.get_by_role("button", name="Disconnect", exact=True).click()
            page.get_by_label("Session token", exact=True).fill(reviewer_token)
            page.get_by_role("button", name="Connect", exact=True).click()
            expect(page.locator("#secured")).to_be_visible()
            page.get_by_role("button", name="Review queue", exact=True).click()
            page.get_by_role("button", name="Approve exact action").click()
            expect(page.locator(".badge")).to_contain_text("approved")
            page.on("dialog", lambda dialog: dialog.accept())
            page.get_by_role("button", name="Execute approved sandbox note").click()
            expect(page.locator(".badge")).to_contain_text("executed")
            assert store.ticket(store.principal("alice"), "IT-001").notes == (draft,)
            page.get_by_role("button", name="My run monitoring").click()
            expect(page.locator("#catalog")).to_contain_text("own latest 100 runs")
            page.get_by_text("Infrastructure / Infrastruktur", exact=True).click()
            page.get_by_role("button", name="Analyze dependencies").click()
            expect(page.locator("#runMeta")).to_contain_text(
                "deterministic/business-tools-v1"
            )
            expect(page.locator("#draft")).to_contain_text("ASSET-APP")
            expect(page.locator("#draft")).to_contain_text("No production change")
            page.get_by_role("button", name="Disconnect", exact=True).click()
            page.get_by_label("Session token", exact=True).fill(finance_token)
            page.get_by_role("button", name="Connect", exact=True).click()
            expect(page.locator("#secured")).to_be_visible()
            page.get_by_text("Invoice review / Rechnungsprüfung", exact=True).click()
            page.get_by_role("button", name="Prepare invoice review").click()
            expect(page.locator("#draft")).to_contain_text("2400.00")
            expect(page.locator("#draft")).to_contain_text("No payment")
            page.locator("#language").select_option("de")
            expect(page.locator("h1")).to_have_text(
                "Arbeitsbereich für Unternehmensagenten"
            )
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate(
                "document.documentElement.scrollWidth <= window.innerWidth"
            )
            assert page.evaluate("localStorage.length + sessionStorage.length") == 0
            assert errors == []
            browser.close()
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
