# -*- coding: utf-8 -*-
"""
DL-Web CP - 网站视频下载器
支持: 哔哩哔哩(B站)等主流视频网站视频下载
纯 Python 实现，无需 ffmpeg，双击即可运行
"""

import os
import sys
import re
import time
import json
import threading
from urllib.parse import urlparse, urljoin, unquote
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

VERSION = "V1.0"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


def _have(mod):
    try:
        __import__(mod)
        return True
    except Exception:
        return False


def _msg_box(message, title="提示", style=0x40):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, str(message), str(title), style)
    except Exception:
        print(f"\n[{title}] {message}\n")


def ensure_deps():
    frozen = getattr(sys, "frozen", False)
    needed = []
    if not frozen:
        if not _have("requests"):
            needed.append("requests")
    if needed:
        print(f"[依赖] 检测到缺失: {', '.join(needed)}，正在自动安装 ...")
        import subprocess
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", *needed, "-q"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            print("[依赖] 安装完成。")
        except Exception as e:
            print(f"[依赖] 自动安装失败: {e}")
            print(f"请手动运行: pip install {' '.join(needed)}")
            sys.exit(1)
    else:
        print("[依赖] 基础依赖已就绪。")
    print("-" * 60)


ensure_deps()
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ===================== 工具函数 =====================

def log(msg, level="INFO"):
    print(f"[{level}] {msg}", flush=True)


def safe_name(s):
    s = unquote(s)
    s = re.sub(r'[\\/:*?"<>|]', "_", s)
    return s[:80].strip(" .") or "video"


def fmt_size(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f}{u}"
        n /= 1024
    return f"{n:.1f}PB"


def fmt_time(s):
    s = int(s)
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m{s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m"


# ===================== 进度条 =====================

class DownloadProgress:
    def __init__(self):
        self.lock = threading.Lock()
        self.downloaded = 0
        self.total = 0
        self.start = time.time()
        self.last_render = 0
        self.current = ""

    def set_total(self, n):
        with self.lock:
            self.total = n

    def add_downloaded(self, n):
        with self.lock:
            self.downloaded += n
            self._render()

    def set_current(self, desc):
        with self.lock:
            self.current = desc[:40]

    def _render(self):
        now = time.time()
        if now - self.last_render < 0.1 and self.downloaded < self.total:
            return
        self.last_render = now
        elapsed = now - self.start
        total = max(self.total, self.downloaded)
        pct = self.downloaded / total if total else 0
        bw = 30
        bar = "#" * int(bw * pct) + "-" * (bw - int(bw * pct))
        if elapsed > 0:
            speed = self.downloaded / elapsed
            eta = max(0, (total - self.downloaded) / speed)
        else:
            speed = 0
            eta = 0
        sys.stdout.write(
            f"\r下载 {bar} {pct:5.1%} | {fmt_size(self.downloaded)}/{fmt_size(total)} "
            f"| {fmt_size(speed)}/s | 剩余{fmt_time(eta)} | {self.current}"
        )
        sys.stdout.flush()

    def finish(self):
        with self.lock:
            self.downloaded = self.total = max(self.downloaded, self.total)
            self._render()
        sys.stdout.write("\n\n")
        sys.stdout.flush()


PROGRESS = DownloadProgress()


# ===================== 下载会话 =====================

def build_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    retry = Retry(total=5, backoff_factor=0.5,
                  status_forcelist=(500, 502, 503, 504),
                  allowed_methods=frozenset(["GET"]))
    ad = HTTPAdapter(pool_connections=16, pool_maxsize=32, max_retries=retry)
    s.mount("http://", ad)
    s.mount("https://", ad)
    return s


# ===================== 各平台下载器 =====================

class BilibiliDownloader:
    """哔哩哔哩视频下载器 - 纯Python实现，无需ffmpeg"""

    NAME = "哔哩哔哩"

    def __init__(self):
        self.session = build_session()
        self.api_session = build_session()
        self.api_session.headers.update({
            "Referer": "https://www.bilibili.com/",
            "Origin": "https://www.bilibili.com",
        })

    @staticmethod
    def match(url):
        return ("bilibili.com/video" in url or "b23.tv" in url
                or re.search(r"BV[0-9A-Za-z]{10}", url) is not None)

    @staticmethod
    def extract_bvid(url):
        m = re.search(r"(BV[0-9A-Za-z]{10})", url)
        if m:
            return m.group(1)
        return None

    def _resolve_short_link(self, url):
        try:
            r = self.session.head(url, allow_redirects=True, timeout=10)
            return r.url
        except Exception:
            return url

    def get_video_info(self, bvid):
        api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        try:
            resp = self.api_session.get(api_url, timeout=10)
            data = resp.json()
            if data["code"] != 0:
                log(f"获取视频信息失败: {data.get('message', '未知错误')}", "ERROR")
                return None
            return data["data"]
        except Exception as e:
            log(f"获取视频信息异常: {e}", "ERROR")
            return None

    def get_play_url(self, bvid, cid, qn=64):
        """
        获取播放地址
        qn: 清晰度 16=360P, 32=480P, 64=720P, 80=1080P, 112=1080P+, 120=4K
        fnval=0 返回 durl 格式（音视频合一，flv/mp4）
        """
        play_api = (
            f"https://api.bilibili.com/x/player/playurl"
            f"?bvid={bvid}&cid={cid}&qn={qn}&fnval=0&fourk=1"
        )
        try:
            resp = self.api_session.get(play_api, timeout=10)
            data = resp.json()
            if data["code"] != 0:
                log(f"获取播放地址失败: {data.get('message', '未知错误')}", "ERROR")
                return None
            return data["data"]
        except Exception as e:
            log(f"获取播放地址异常: {e}", "ERROR")
            return None

    def _download_segment(self, url, save_path, seg_idx, total_segs, headers):
        """下载单个分段，带进度更新"""
        try:
            r = self.api_session.get(url, headers=headers, stream=True, timeout=30)
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(save_path, "ab") as f:
                for chunk in r.iter_content(chunk_size=512 * 1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        PROGRESS.add_downloaded(len(chunk))
            return downloaded
        except Exception as e:
            log(f"分段 {seg_idx}/{total_segs} 下载失败: {e}", "ERROR")
            return 0

    def download(self, url, save_dir, quality="720P"):
        """
        下载B站视频
        quality: 360P / 480P / 720P / 1080P / 4K
        返回: (保存路径, 文件大小, 是否成功)
        """
        if "b23.tv" in url:
            url = self._resolve_short_link(url)

        bvid = self.extract_bvid(url)
        if not bvid:
            log("无法提取 BVID", "ERROR")
            return None, 0, False

        log(f"解析视频: {bvid}")
        info = self.get_video_info(bvid)
        if not info:
            return None, 0, False

        title = info.get("title", bvid)
        cid = info.get("cid")
        pic = info.get("pic", "")
        duration = info.get("duration", 0)
        owner = info.get("owner", {}).get("name", "")

        log(f"标题: {title}")
        log(f"UP主: {owner}")
        log(f"时长: {fmt_time(duration)}")

        if not cid:
            log("缺少 cid", "ERROR")
            return None, 0, False

        qn_map = {
            "360P": 16,
            "480P": 32,
            "720P": 64,
            "1080P": 80,
            "4K": 120,
        }
        qn = qn_map.get(quality, 64)

        play_data = self.get_play_url(bvid, cid, qn)
        if not play_data:
            log("尝试降低清晰度到 480P ...", "WARN")
            play_data = self.get_play_url(bvid, cid, 32)
            if not play_data:
                log("尝试最低清晰度 360P ...", "WARN")
                play_data = self.get_play_url(bvid, cid, 16)
                if not play_data:
                    return None, 0, False

        durl_list = play_data.get("durl", [])
        if not durl_list:
            log("未找到视频流地址", "ERROR")
            return None, 0, False

        total_size = sum(d.get("size", 0) for d in durl_list)
        PROGRESS.set_total(total_size)

        safe_title = safe_name(title)
        save_path = Path(save_dir) / f"{safe_title}.mp4"
        save_path.parent.mkdir(parents=True, exist_ok=True)

        if save_path.exists():
            existing_size = save_path.stat().st_size
            if existing_size >= total_size * 0.95:
                log(f"文件已存在，跳过下载: {save_path.name}")
                return str(save_path), existing_size, True

        if save_path.exists():
            save_path.unlink()

        seg_headers = {
            **self.api_session.headers,
            "Referer": f"https://www.bilibili.com/video/{bvid}/",
        }

        total_downloaded = 0
        for idx, seg in enumerate(durl_list, 1):
            seg_url = seg["url"]
            seg_size = seg.get("size", 0)
            PROGRESS.set_current(f"分段 {idx}/{len(durl_list)}")
            log(f"下载分段 {idx}/{len(durl_list)} ({fmt_size(seg_size)})")

            dl_size = self._download_segment(seg_url, save_path, idx, len(durl_list), seg_headers)
            if dl_size == 0:
                log(f"分段 {idx} 下载失败，尝试备用地址 ...", "WARN")
                backup_urls = seg.get("backup_url", [])
                for bu in backup_urls:
                    dl_size = self._download_segment(bu, save_path, idx, len(durl_list), seg_headers)
                    if dl_size > 0:
                        break
            total_downloaded += dl_size

        if total_downloaded == 0:
            if save_path.exists():
                save_path.unlink()
            log("视频下载失败", "ERROR")
            return None, 0, False

        PROGRESS.finish()
        final_size = save_path.stat().st_size
        log(f"下载完成: {save_path.name} ({fmt_size(final_size)})", "SUCCESS")
        return str(save_path), final_size, True


# ===================== 通用视频下载器 =====================

class GenericVideoDownloader:
    """通用视频下载器 - 直接下载视频文件URL"""

    NAME = "通用直链"

    def __init__(self):
        self.session = build_session()

    @staticmethod
    def match(url):
        path = urlparse(url).path.lower()
        return any(path.endswith(ext) for ext in (".mp4", ".webm", ".m3u8", ".mkv", ".flv", ".avi"))

    def download(self, url, save_dir, quality=None):
        filename = safe_name(Path(urlparse(url).path).name) or "video.mp4"
        if not filename.endswith(".mp4"):
            filename += ".mp4"
        save_path = Path(save_dir) / filename
        save_path.parent.mkdir(parents=True, exist_ok=True)

        log(f"下载: {filename}")
        PROGRESS.set_current(filename)

        try:
            r = self.session.get(url, stream=True, timeout=30)
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0))
            PROGRESS.set_total(total_size)

            downloaded = 0
            with open(save_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=512 * 1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        PROGRESS.add_downloaded(len(chunk))

            PROGRESS.finish()
            final_size = save_path.stat().st_size
            log(f"下载完成: {save_path.name} ({fmt_size(final_size)})", "SUCCESS")
            return str(save_path), final_size, True
        except Exception as e:
            log(f"下载失败: {e}", "ERROR")
            if save_path.exists():
                save_path.unlink()
            return None, 0, False


# ===================== 下载器管理器 =====================

DOWNLOADERS = [
    BilibiliDownloader,
]


def get_downloader(url):
    """根据URL自动匹配下载器"""
    for dl_cls in DOWNLOADERS:
        if dl_cls.match(url):
            return dl_cls()
    if GenericVideoDownloader.match(url):
        return GenericVideoDownloader()
    return None


# ===================== 批量下载 =====================

def batch_download(urls, save_dir, quality="720P"):
    """批量下载多个视频"""
    save_dir = Path(save_dir).resolve()
    save_dir.mkdir(parents=True, exist_ok=True)

    success = 0
    fail = 0
    total_size = 0
    results = []

    for i, url in enumerate(urls, 1):
        url = url.strip()
        if not url:
            continue
        print(f"\n{'='*60}")
        print(f"[{i}/{len(urls)}] 处理: {url[:80]}")
        print(f"{'='*60}")

        downloader = get_downloader(url)
        if not downloader:
            log(f"不支持的视频链接: {url[:60]}", "WARN")
            fail += 1
            results.append((url, "不支持", None, 0))
            continue

        try:
            path, size, ok = downloader.download(url, save_dir, quality)
            if ok:
                success += 1
                total_size += size
                results.append((url, "成功", path, size))
            else:
                fail += 1
                results.append((url, "失败", None, 0))
        except Exception as e:
            log(f"下载异常: {e}", "ERROR")
            fail += 1
            results.append((url, f"异常: {e}", None, 0))

    print(f"\n{'='*60}")
    print(f"下载完成统计:")
    print(f"  成功: {success} 个")
    print(f"  失败: {fail} 个")
    print(f"  总大小: {fmt_size(total_size)}")
    print(f"  保存目录: {save_dir}")
    print(f"{'='*60}\n")

    return results


# ===================== 交互式界面 =====================

def main():
    print(f"""
╔══════════════════════════════════════════════════════╗
║          DL-Web CP - 网站视频下载器 {VERSION}             ║
║          支持: 哔哩哔哩 等主流视频平台                   ║
║          纯Python实现 | 无需ffmpeg | 绿色免安装          ║
╚══════════════════════════════════════════════════════╝
""")

    while True:
        print("""
请选择操作:
  [1] 单个视频下载
  [2] 批量视频下载（URL列表）
  [0] 退出
""")
        try:
            choice = input("请输入选项: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if choice == "0":
            print("再见！")
            break

        elif choice == "1":
            url = input("请输入视频URL: ").strip()
            if not url:
                print("URL不能为空")
                continue

            print("\n请选择清晰度:")
            print("  [1] 360P")
            print("  [2] 480P")
            print("  [3] 720P (推荐)")
            print("  [4] 1080P")
            print("  [5] 4K")
            q_choice = input("请选择 (默认3): ").strip() or "3"
            q_map = {"1": "360P", "2": "480P", "3": "720P", "4": "1080P", "5": "4K"}
            quality = q_map.get(q_choice, "720P")

            save_dir = input("请输入保存目录 (默认 ./downloads): ").strip() or "./downloads"

            print()
            downloader = get_downloader(url)
            if not downloader:
                log(f"未识别的视频来源: {url[:60]}", "WARN")
                log("尝试以通用直链方式下载 ...", "INFO")
                downloader = GenericVideoDownloader()

            log(f"使用下载器: {downloader.NAME}")
            path, size, ok = downloader.download(url, save_dir, quality)

            if ok:
                _msg_box(
                    f"下载成功！\n\n文件: {Path(path).name}\n大小: {fmt_size(size)}\n路径: {path}",
                    "下载完成"
                )
            else:
                _msg_box("下载失败，请检查URL或网络连接。", "下载失败", 0x10)

        elif choice == "2":
            print("\n请输入视频URL列表，每行一个，输入空行结束:")
            urls = []
            while True:
                line = input()
                if not line.strip():
                    break
                urls.append(line.strip())

            if not urls:
                print("未输入任何URL")
                continue

            print(f"\n共 {len(urls)} 个视频")

            print("\n请选择清晰度:")
            print("  [1] 360P")
            print("  [2] 480P")
            print("  [3] 720P (推荐)")
            print("  [4] 1080P")
            print("  [5] 4K")
            q_choice = input("请选择 (默认3): ").strip() or "3"
            q_map = {"1": "360P", "2": "480P", "3": "720P", "4": "1080P", "5": "4K"}
            quality = q_map.get(q_choice, "720P")

            save_dir = input("请输入保存目录 (默认 ./downloads): ").strip() or "./downloads"

            print()
            results = batch_download(urls, save_dir, quality)

            success_count = sum(1 for _, status, _, _ in results if status == "成功")
            total_size = sum(s for _, _, _, s in results)
            _msg_box(
                f"批量下载完成！\n\n成功: {success_count}/{len(results)}\n总大小: {fmt_size(total_size)}\n保存目录: {Path(save_dir).resolve()}",
                "批量下载完成"
            )

        else:
            print("无效选项，请重新输入")

        print()
        try:
            input("按回车键继续...")
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断，退出。")
    except Exception as e:
        import traceback
        traceback.print_exc()
        _msg_box(f"程序出错: {e}", "错误", 0x10)
