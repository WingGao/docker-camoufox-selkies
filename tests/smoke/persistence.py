#!/usr/bin/env python3
"""Write or verify browser state in the shared persistent context."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright


async def run(endpoint: str, mode: str) -> None:
    async with async_playwright() as playwright:
        browser = await playwright.firefox.connect(endpoint)
        if not browser.contexts:
            raise RuntimeError("Shared persistent browser context is not visible")
        context = browser.contexts[0]
        page = await context.new_page()
        await page.goto("https://example.com/")
        if mode == "write":
            result = await page.evaluate(
                """() => {
                    document.cookie = 'camoufox_persist=verified; Max-Age=3600; Path=/'
                    localStorage.setItem('camoufox_persist', 'verified')
                    return [document.cookie, localStorage.getItem('camoufox_persist')]
                }"""
            )
        else:
            result = await page.evaluate(
                "() => [document.cookie, localStorage.getItem('camoufox_persist')]"
            )
            if "camoufox_persist=verified" not in result[0] or result[1] != "verified":
                raise RuntimeError(f"Persistent browser state was not restored: {result!r}")
        print(f"mode={mode} state={result}")
        await page.close()
        await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("write", "verify"))
    parser.add_argument("endpoint")
    args = parser.parse_args()
    endpoint = args.endpoint
    if endpoint.startswith("file://"):
        endpoint = Path(endpoint.removeprefix("file://")).read_text(encoding="utf-8").strip()
    endpoint = endpoint.replace("0.0.0.0", "127.0.0.1")
    asyncio.run(run(endpoint, args.mode))


if __name__ == "__main__":
    main()
