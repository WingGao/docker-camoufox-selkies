#!/usr/bin/env python3
"""Fetch only the official Camoufox browser bundle during image builds."""

from camoufox.pkgman import CamoufoxFetcher


def main() -> int:
    fetcher = CamoufoxFetcher()
    fetcher.install()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
