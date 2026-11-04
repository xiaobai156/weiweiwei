"""打开可见的爬虫浏览器窗口，供人工登录；关窗后自动保存会话。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from playwright.sync_api import sync_playwright

from shawei.fetch.browser import browser_profile_dir

URL = "https://wwlhc.com/thread-87037-1-1.html"


def main() -> int:
    profile = browser_profile_dir()
    print(f"使用会话目录: {profile}", flush=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(profile),
            headless=False,
            viewport={"width": 1280, "height": 900},
            ignore_https_errors=True,
            locale="zh-CN",
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        except Exception as exc:  # noqa: BLE001
            print(f"自动打开页面失败，请在窗口地址栏手动输入: {type(exc).__name__}: {exc}", flush=True)
        print("READY 浏览器窗口已打开，请登录；登录完成后关闭该窗口即可保存会话。", flush=True)

        deadline = time.time() + 3600
        last_hint = ""
        while time.time() < deadline:
            try:
                if not ctx.pages:
                    print("窗口已关闭，正在保存会话…", flush=True)
                    break
            except Exception:  # noqa: BLE001
                break
            try:
                text = ctx.pages[0].inner_text("body")
                hint = "已登录" if ("退出" in text or "我的" in text and "设置" in text) else "游客"
                if hint != last_hint:
                    print(f"登录状态: {hint}", flush=True)
                    last_hint = hint
            except Exception:  # noqa: BLE001
                pass
            time.sleep(3)
        else:
            print("等待超时，按当前状态保存。", flush=True)

        try:
            ctx.close()
            print("会话已保存。", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"保存会话时出错: {type(exc).__name__}: {exc}", flush=True)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
