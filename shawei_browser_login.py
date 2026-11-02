"""Open the crawler's persistent browser profile for one-time manual login."""
from __future__ import annotations

import argparse
import asyncio

from shawei.fetch.browser import browser_profile_dir


async def _login(url: str) -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            str(browser_profile_dir()),
            headless=False,
            viewport={"width": 1280, "height": 900},
        )
        page = context.pages[0] if context.pages else await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception as exc:
            print(f"自动打开页面失败，请在浏览器地址栏重试: {type(exc).__name__}: {exc}")
        print("请在弹出的爬虫浏览器中登录；完成后回到此窗口按 Enter 保存登录状态。")
        await asyncio.to_thread(input)
        await context.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="登录并保存爬虫浏览器会话。")
    parser.add_argument(
        "--url",
        default="https://wwlhc.com/thread-87037-1-1.html",
        help="登录入口页面",
    )
    args = parser.parse_args()
    asyncio.run(_login(args.url))
    print(f"登录状态已保存到: {browser_profile_dir()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
