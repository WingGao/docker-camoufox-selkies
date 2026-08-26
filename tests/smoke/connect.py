#!/usr/bin/env python3
"""Connect to a running Camoufox BrowserServer and perform a basic navigation."""

from __future__ import annotations

import argparse
import asyncio

from playwright.async_api import async_playwright


async def smoke_test(endpoint: str, url: str) -> None:
    async with async_playwright() as playwright:
        browser = await playwright.firefox.connect(endpoint)
        if not browser.contexts:
            raise RuntimeError("Shared Selkies browser context is not visible")
        context = browser.contexts[0]
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        title = await page.title()
        await page.set_content('<button id="smoke">Click me</button>')
        await page.locator("#smoke").click()
        print(f"url={page.url}")
        print(f"title={title}")
        await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("endpoint", help="Full ws:// endpoint from docker compose logs")
    parser.add_argument("--url", default="https://example.com")
    args = parser.parse_args()
    asyncio.run(smoke_test(args.endpoint, args.url))


if __name__ == "__main__":
    main()
