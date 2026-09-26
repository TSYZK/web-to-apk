# -*- coding: utf-8 -*-
"""网页可用性检测：HTTP 探测 + 标题提取，不依赖第三方库。"""
import re
import time
import urllib.request
import urllib.error
import ssl
from dataclasses import dataclass


USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


@dataclass
class CheckResult:
    ok: bool
    url: str
    final_url: str = ""
    status: int = 0
    elapsed_ms: int = 0
    title: str = ""
    content_type: str = ""
    message: str = ""


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return url
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", url):
        url = "https://" + url
    return url


def _extract_title(chunk: bytes, encoding: str) -> str:
    try:
        html = chunk.decode(encoding or "utf-8", errors="ignore")
    except (LookupError, TypeError):
        html = chunk.decode("utf-8", errors="ignore")
    m = re.search(
        r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if not m:
        return ""
    title = re.sub(r"\s+", " ", m.group(1)).strip()
    return title[:100]


def check_website(raw_url: str, timeout: float = 12.0) -> CheckResult:
    url = normalize_url(raw_url)
    if not url:
        return CheckResult(False, url, message="网址为空")

    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })

    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            status = resp.getcode()
            final_url = resp.geturl()
            content_type = resp.headers.get("Content-Type", "")
            chunk = resp.read(512 * 1024)
            encoding = resp.headers.get_content_charset()
            elapsed = int((time.monotonic() - start) * 1000)
            title = _extract_title(chunk, encoding) if chunk else ""
            ok = 200 <= status < 400
            return CheckResult(
                ok=ok, url=url, final_url=final_url, status=status,
                elapsed_ms=elapsed, title=title, content_type=content_type,
                message="可以正常打开" if ok else f"HTTP {status}")
    except urllib.error.HTTPError as e:
        elapsed = int((time.monotonic() - start) * 1000)
        return CheckResult(
            ok=False, url=url, final_url=e.geturl() if hasattr(e, "geturl") else url,
            status=e.code, elapsed_ms=elapsed,
            message=f"服务器返回错误：HTTP {e.code} {e.reason}")
    except urllib.error.URLError as e:
        elapsed = int((time.monotonic() - start) * 1000)
        reason = getattr(e, "reason", e)
        # HTTPS 失败时自动回退尝试 HTTP（部分内网/旧站点只支持 http）
        if url.startswith("https://"):
            http_url = "http://" + url[len("https://"):]
            try:
                req2 = urllib.request.Request(http_url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req2, timeout=timeout) as resp:
                    chunk = resp.read(512 * 1024)
                    title = _extract_title(chunk, resp.headers.get_content_charset())
                    return CheckResult(
                        ok=True, url=url, final_url=resp.geturl(),
                        status=resp.getcode(),
                        elapsed_ms=int((time.monotonic() - start) * 1000),
                        title=title,
                        content_type=resp.headers.get("Content-Type", ""),
                        message="HTTPS 不可用，但 HTTP 可以正常打开（已自动回退）")
            except Exception:
                pass
        return CheckResult(
            ok=False, url=url, elapsed_ms=elapsed,
            message=f"无法连接：{reason}")
    except Exception as e:
        return CheckResult(ok=False, url=url, message=f"检测失败：{e}")
