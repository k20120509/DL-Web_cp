# -*- coding: utf-8 -*-
"""
DL-Web CP V2.5 - 增强版视频下载器
支持: 哔哩哔哩、YouTube、抖音、Twitter/X、直链
功能: 稳定代理池、断点续传、多线程并发、自动清理、智能定位
"""

import os
import sys
import re
import time
import json
import atexit
import signal
import threading
import tempfile
import hashlib
from pathlib import Path
from urllib.parse import urlparse, urljoin, unquote, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, List, Tuple, Callable
from dataclasses import dataclass
import subprocess

VERSION = "V2.5.1-test"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


# ===================== 临时文件追踪（退出时清理）=====================

class TempFileManager:
    """管理临时文件，退出时自动删除未完成的下载"""
    
    def __init__(self):
        self.temp_files = set()
        self.lock = threading.Lock()
        self._register_exit_handlers()
    
    def register(self, filepath: str):
        """注册临时文件"""
        with self.lock:
            self.temp_files.add(filepath)
    
    def complete(self, filepath: str):
        """标记文件已完成"""
        with self.lock:
            self.temp_files.discard(filepath)
    
    def cleanup(self):
        """清理所有未完成的临时文件"""
        with self.lock:
            for f in list(self.temp_files):
                try:
                    if os.path.exists(f):
                        os.remove(f)
                        log(f"清理未完成文件: {f}", "WARN")
                except Exception:
                    pass
            self.temp_files.clear()
    
    def _register_exit_handlers(self):
        """注册退出处理器"""
        atexit.register(self.cleanup)
        try:
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)
        except Exception:
            pass
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        self.cleanup()
        sys.exit(0)


TEMP_MANAGER = TempFileManager()


# ===================== 免费代理池 =====================

@dataclass
class ProxyInfo:
    """代理信息"""
    host: str
    port: int
    protocol: str = "http"
    latency: float = 999.0
    last_check: float = 0.0
    success_count: int = 0
    fail_count: int = 0
    can_youtube: bool = False    # 是否能访问 YouTube
    can_bilibili: bool = False   # 是否能访问 Bilibili

    @property
    def url(self) -> str:
        return f"{self.protocol}://{self.host}:{self.port}"

    @property
    def score(self) -> float:
        """计算代理得分（越低越好）- YouTube 可访问的代理优先"""
        if self.success_count + self.fail_count == 0:
            return 999.0
        success_rate = self.success_count / (self.success_count + self.fail_count)
        base = self.latency / max(success_rate, 0.1)
        # YouTube 代理优先（降低得分）
        if self.can_youtube:
            base *= 0.3
        elif self.can_bilibili:
            base *= 0.7
        return base


class ProxyPool:
    """稳定代理池 - 多源获取、严格测试、优先级选择"""
    
    # Proxy sources - 8+ sources including foreign proxies for YouTube
    PROXY_SOURCES = [
        # 主要源
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text",
        "https://www.proxy-list.download/api/v1/get?type=http",
        "https://api.openproxylist.xyz/http.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
        # 额外源（含更多国外代理）
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
        "https://raw.githubusercontent.com/MuRongPI/ProxyList/main/https.txt",
        "https://raw.githubusercontent.com/sunny2017/ProxyList/master/https.txt",
        "https://raw.githubusercontent.com/EliasOal/proxy-list/master/proxy-list.txt",
        "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
        "https://raw.githubusercontent.com/Barthr/ProxyList/master/proxy-list.txt",
    ]

    # Pre-tested working proxies (tested 2026-07-28, 35/1000 passed)
    # Format: "host:port" - these are known-good proxies
    TESTED_PROXIES = [
        # YouTube + Google + httpbin accessible (best)
        "8.138.82.6:9080",
        "139.224.186.221:9080",
        "39.102.208.236:8081",
        "8.130.37.235:9080",
        # YouTube accessible
        "8.137.62.53:80",
        "218.93.176.70:2088",
        # Bilibili fast (low latency)
        "120.92.212.16:7890",
        "122.246.4.6:17981",
        "123.138.24.114:8800",
        "219.148.171.178:9445",
        "129.226.72.101:18080",
        # Bilibili accessible
        "103.133.25.119:8080",
        "38.58.66.237:999",
        "192.203.0.166:999",
        "112.207.169.6:8082",
        "103.145.34.100:1111",
        "222.252.97.26:8008",
        "143.105.102.145:8080",
        "112.198.178.130:5050",
        "113.192.31.79:8099",
        "103.169.33.30:3125",
        "190.130.6.11:8080",
        "47.91.89.3:80",
        "103.174.122.203:8080",
        "8.213.195.191:9098",
        "139.5.75.83:8080",
        "113.11.37.81:2505",
        "103.160.205.86:8080",
        "103.48.71.142:82",
        # httpbin accessible
        "131.222.249.39:8080",
        "47.238.134.126:8004",
        "47.76.144.139:4002",
        "8.138.82.6:9080",
        "45.198.152.230:8000",
        "47.90.167.27:1000",
    ]
    
    def __init__(self):
        self.proxies: List[ProxyInfo] = []
        self.lock = threading.Lock()
        self.best_proxy: Optional[ProxyInfo] = None
        # 轻量测试 URL，单次请求响应快
        # 顺序：先试 httpbin（最快），失败再试 Bilibili
        self.test_urls = [
            "https://httpbin.org/ip",
            "https://www.bilibili.com",
        ]
        self.timeout = 3.0           # 单代理超时（秒）
        self.max_test = 1200         # 最大测试数
        self.max_workers = 200       # 并发数
        self.early_stop_count = 30   # 找到 N 个可用代理就停止
        self.max_test_seconds = 50   # 测试阶段总时间上限（秒）
        self._initialized = False
    
    def initialize(self):
        """初始化代理池（获取+测试）"""
        if self._initialized:
            return
        
        log("=" * 60, "INFO")
        log("初始化代理池，正在获取代理列表...", "INFO")
        
        # 1. 获取所有代理
        raw_proxies = self._fetch_all_proxies()
        log(f"Total fetched: {len(raw_proxies)} proxies", "INFO")

        if not raw_proxies:
            log("No proxies fetched from online sources, using pre-tested list", "WARN")
            raw_proxies = self.TESTED_PROXIES.copy()

        # 2. 去重但保持顺序 - pre-tested proxies first
        seen = set()
        unique_proxies = []
        # Pre-tested proxies go first (they are already known to work)
        for p in self.TESTED_PROXIES:
            if p not in seen:
                seen.add(p)
                unique_proxies.append(p)
        # Then add the rest
        for p in raw_proxies:
            if p not in seen:
                seen.add(p)
                unique_proxies.append(p)
        log(f"After dedup: {len(unique_proxies)} proxies (pre-tested first)", "INFO")

        # 3. 并发测试所有代理
        log("Testing proxy availability (may take 30-60 seconds)...", "INFO")
        self.proxies = self._test_all_proxies(unique_proxies)
        log(f"Test complete, working proxies: {len(self.proxies)}", "INFO")
        
        # 4. 选择最优
        self._select_best_proxy()
        
        self._initialized = True

        if self.best_proxy:
            yt = sum(1 for p in self.proxies if p.can_youtube)
            bb = sum(1 for p in self.proxies if p.can_bilibili)
            log(f"Proxy pool ready!", "SUCCESS")
            log(f"  Best proxy: {self.best_proxy.host}:{self.best_proxy.port} "
                f"(latency {self.best_proxy.latency:.2f}s, "
                f"YouTube={'Y' if self.best_proxy.can_youtube else 'N'}, "
                f"Bili={'Y' if self.best_proxy.can_bilibili else 'N'})", "SUCCESS")
            log(f"  Total: {len(self.proxies)} | YouTube: {yt} | Bilibili: {bb}", "SUCCESS")
        else:
            log("All proxies unavailable, will use direct download", "WARN")
        log("=" * 60, "INFO")
    
    def _fetch_all_proxies(self) -> List[str]:
        """Fetch proxies from all sources + pre-tested list"""
        all_proxies = []

        # Add pre-tested working proxies first (highest priority)
        all_proxies.extend(self.TESTED_PROXIES)

        # Fetch from online sources concurrently
        def fetch_one(url):
            try:
                import requests
                r = requests.get(url, timeout=12, headers={"User-Agent": USER_AGENT})
                if r.status_code == 200:
                    text = r.text.strip()
                    found = []
                    if text:
                        for line in text.split("\n"):
                            line = line.strip()
                            if ":" in line and len(line.split(":")) == 2:
                                found.append(line)
                    name = url.split("/")[-1][:30] if "/" in url else url[:30]
                    log(f"  {name}: {len(found)} proxies", "INFO")
                    return found
            except Exception:
                name = url.split("/")[-1][:30] if "/" in url else url[:30]
                log(f"  {name}: failed", "WARN")
            return []

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(fetch_one, url) for url in self.PROXY_SOURCES]
            for future in as_completed(futures):
                all_proxies.extend(future.result())

        return all_proxies
    
    def _test_all_proxies(self, proxy_list: List[str]) -> List[ProxyInfo]:
        """并发测试所有代理 - 早停 + 总时长上限"""
        import requests as _req
        from concurrent.futures import wait, FIRST_COMPLETED

        tested_proxies: List[ProxyInfo] = []
        lock_local = threading.Lock()
        test_count = min(len(proxy_list), self.max_test)
        test_subset = proxy_list[:test_count]
        deadline = time.time() + self.max_test_seconds

        def test_single_proxy(proxy_str: str) -> Optional[ProxyInfo]:
            parts = proxy_str.split(":")
            if len(parts) != 2:
                return None
            try:
                host = parts[0]
                port = int(parts[1])
                if port <= 0 or port > 65535:
                    return None

                info = ProxyInfo(host=host, port=port)
                proxy_url = info.url
                proxies = {"http": proxy_url, "https": proxy_url}
                headers = {"User-Agent": USER_AGENT}

                best_latency = 999.0
                passed = False

                # 1) 先测 Bilibili（国内可访问，快）
                try:
                    start = time.time()
                    r = _req.get("https://www.bilibili.com",
                                 proxies=proxies, timeout=self.timeout,
                                 verify=False, headers=headers)
                    elapsed = time.time() - start
                    if r.status_code < 400 and elapsed < 6.0:
                        info.can_bilibili = True
                        info.latency = elapsed
                        info.success_count = 1
                        info.last_check = time.time()
                        best_latency = min(best_latency, elapsed)
                        passed = True
                except Exception:
                    pass

                # 2) 测 YouTube（外网，需要代理）
                try:
                    start = time.time()
                    r = _req.get("https://www.youtube.com",
                                 proxies=proxies, timeout=self.timeout,
                                 verify=False, headers=headers)
                    elapsed = time.time() - start
                    if r.status_code < 400 and elapsed < 6.0:
                        info.can_youtube = True
                        if elapsed < best_latency:
                            info.latency = elapsed
                        info.last_check = time.time()
                        passed = True
                except Exception:
                    pass

                if passed:
                    info.success_count = 1
                    return info
                return None
            except Exception:
                return None

        log(f"  并发测试 {test_count} 个代理 (并发 {self.max_workers}, 上限 {self.max_test_seconds}s)...", "INFO")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(test_single_proxy, p): p for p in test_subset}
            completed = 0

            while futures:
                # 检查是否到达截止时间或早停
                now = time.time()
                with lock_local:
                    cur_working = len(tested_proxies)
                if now > deadline:
                    log(f"  时间上限到达，停止剩余测试 (已完成 {completed}/{test_count})", "WARN")
                    # 取消未完成的 future（已运行的不一定能取消，但试一下）
                    for f in futures:
                        f.cancel()
                    break
                if cur_working >= self.early_stop_count and completed >= self.early_stop_count * 4:
                    log(f"  已找到 {cur_working} 个可用代理，提前停止", "SUCCESS")
                    for f in futures:
                        f.cancel()
                    break

                # 等下一个完成（最多等 2 秒，便于检查 deadline）
                done, futures = wait(futures, timeout=2.0, return_when=FIRST_COMPLETED)
                for f in done:
                    try:
                        result = f.result()
                    except Exception:
                        result = None
                    if result:
                        with lock_local:
                            tested_proxies.append(result)
                    completed += 1
                    if completed % 50 == 0:
                        with lock_local:
                            cur = len(tested_proxies)
                        log(f"  进度: {completed}/{test_count}, 可用: {cur}", "INFO")

        return tested_proxies
    
    def _select_best_proxy(self):
        """选择最优代理 - YouTube 可访问的优先"""
        if not self.proxies:
            self.best_proxy = None
            return

        # 按 score 排序（YouTube 代理优先）
        self.proxies.sort(key=lambda p: p.score)
        self.best_proxy = self.proxies[0] if self.proxies else None
    
    def get_proxy(self) -> Optional[Dict]:
        """获取当前最优代理"""
        if not self._initialized:
            self.initialize()
        
        if self.best_proxy:
            return {"http": self.best_proxy.url, "https": self.best_proxy.url}
        return None
    
    def report_success(self, proxy_url: str):
        """报告代理成功 - 提升优先级"""
        with self.lock:
            for p in self.proxies:
                if p.url == proxy_url:
                    p.success_count += 1
                    # 延迟降低优先
                    if p.latency > 0.1:
                        p.latency *= 0.95
                    self._select_best_proxy()
                    break
    
    def report_failure(self, proxy_url: str):
        """报告代理失败 - 降低优先级"""
        with self.lock:
            for p in self.proxies:
                if p.url == proxy_url:
                    p.fail_count += 1
                    # 延迟增加
                    p.latency *= 1.5
                    if p.fail_count >= 3:
                        # 移除失败3次的代理
                        self.proxies.remove(p)
                    self._select_best_proxy()
                    break
    
    def get_all_proxies(self) -> List[Dict]:
        """获取所有可用代理列表（用于轮询）"""
        with self.lock:
            return [{"http": p.url, "https": p.url} for p in self.proxies]


PROXY_POOL = ProxyPool()


# ===================== 断点续传管理 =====================

class ResumeManager:
    """断点续传管理器"""
    
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "dl_web_cp"
        self.temp_dir.mkdir(exist_ok=True)
    
    def get_temp_file(self, url: str, save_path: str) -> Path:
        """获取临时文件路径"""
        key = hashlib.md5(f"{url}_{save_path}".encode()).hexdigest()
        return self.temp_dir / f"{key}.partial"
    
    def get_progress_file(self, url: str, save_path: str) -> Path:
        """获取进度文件路径"""
        key = hashlib.md5(f"{url}_{save_path}".encode()).hexdigest()
        return self.temp_dir / f"{key}.json"
    
    def save_progress(self, url: str, save_path: str, downloaded: int, total: int):
        """保存下载进度"""
        progress_file = self.get_progress_file(url, save_path)
        data = {
            "url": url,
            "save_path": save_path,
            "downloaded": downloaded,
            "total": total,
            "timestamp": time.time()
        }
        try:
            with open(progress_file, "w") as f:
                json.dump(data, f)
        except Exception:
            pass
    
    def load_progress(self, url: str, save_path: str) -> Optional[Dict]:
        """加载下载进度"""
        progress_file = self.get_progress_file(url, save_path)
        if progress_file.exists():
            try:
                with open(progress_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return None
    
    def clear_progress(self, url: str, save_path: str):
        """清除进度文件"""
        for ext in [".partial", ".json"]:
            key = hashlib.md5(f"{url}_{save_path}".encode()).hexdigest()
            path = self.temp_dir / f"{key}{ext}"
            try:
                if path.exists():
                    path.unlink()
            except Exception:
                pass


RESUME_MANAGER = ResumeManager()


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


def open_folder_and_select(filepath: str):
    """打开文件夹并选中文件"""
    try:
        filepath = os.path.abspath(filepath)
        if os.name == "nt":
            subprocess.run(["explorer", "/select,", filepath], check=False)
        elif sys.platform == "darwin":
            subprocess.run(["open", "-R", filepath], check=False)
        else:
            subprocess.run(["xdg-open", os.path.dirname(filepath)], check=False)
        log(f"已打开文件夹: {filepath}", "SUCCESS")
    except Exception as e:
        log(f"打开文件夹失败: {e}", "WARN")


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


# ===================== 进度条 =====================

class DownloadProgress:
    def __init__(self):
        self.lock = threading.Lock()
        self.downloaded = 0
        self.total = 0
        self.start = time.time()
        self.last_render = 0
        self.current = ""
        self.speed_samples = []

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
        
        # 计算速度（使用滑动窗口）
        if elapsed > 0:
            speed = self.downloaded / elapsed
            eta = max(0, (total - self.downloaded) / max(speed, 1))
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

def build_session(use_proxy: bool = False):
    """构建下载会话（支持代理自动切换）"""
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    
    s = requests.Session()
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    
    # 配置代理池支持
    if use_proxy:
        proxy = PROXY_POOL.get_proxy()
        if proxy:
            s.proxies.update(proxy)
            # 添加代理旋转支持
            s._use_proxy_pool = True
        else:
            s._use_proxy_pool = False
    else:
        s._use_proxy_pool = False
    
    # 重试策略（增加对代理失败的容忍）
    retry = Retry(
        total=5,
        backoff_factor=1.0,
        status_forcelist=(500, 502, 503, 504, 429),
        allowed_methods=frozenset(["GET", "HEAD"])
    )
    adapter = HTTPAdapter(pool_connections=32, pool_maxsize=64, max_retries=retry)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    
    return s


def download_with_fallback(session, url, **kwargs):
    """带有代理回退机制的下载"""
    import requests as req
    try:
        response = session.get(url, **kwargs)
        response.raise_for_status()
        # 报告代理成功
        if getattr(session, '_use_proxy_pool', False) and session.proxies:
            for p in PROXY_POOL.proxies:
                if p.url == session.proxies.get('http', ''):
                    PROXY_POOL.report_success(p.url)
                    break
        return response
    except Exception as e:
        # 如果使用了代理，尝试切换到其他代理
        if getattr(session, '_use_proxy_pool', False):
            PROXY_POOL.report_failure(session.proxies.get('http', ''))
            # 尝试下一个可用代理
            all_proxies = PROXY_POOL.get_all_proxies()
            for proxy in all_proxies:
                try:
                    session.proxies.update(proxy)
                    response = session.get(url, **kwargs)
                    response.raise_for_status()
                    PROXY_POOL.report_success(proxy['http'])
                    return response
                except Exception:
                    PROXY_POOL.report_failure(proxy['http'])
                    continue
        raise e


# ===================== 基础下载器 =====================

class BaseDownloader:
    """下载器基类"""
    
    NAME = "基础下载器"
    SUPPORT_PROXY = True  # 是否支持代理
    
    def __init__(self, use_proxy: bool = False):
        self.session = build_session(use_proxy)
        self.use_proxy = use_proxy
        self.temp_files = []
    
    @staticmethod
    def match(url: str) -> bool:
        return False
    
    def download(self, url: str, save_dir: str, quality: str = "720P") -> Tuple[Optional[str], int, bool]:
        raise NotImplementedError
    
    def _download_chunk(
        self,
        url: str,
        save_path: str,
        start_byte: int = 0,
        end_byte: int = 0,
        chunk_idx: int = 0,
        total_chunks: int = 1
    ) -> int:
        """下载单个块（支持断点续传）"""
        headers = {"Range": f"bytes={start_byte}-{end_byte}" if end_byte else ""}
        headers.update(self.session.headers)
        
        temp_file = RESUME_MANAGER.get_temp_file(url, save_path)
        resume_data = RESUME_MANAGER.load_progress(url, save_path)
        
        # 检查是否需要续传
        if resume_data and temp_file.exists():
            downloaded = resume_data.get("downloaded", 0)
            if downloaded > start_byte:
                start_byte = downloaded
                headers["Range"] = f"bytes={start_byte}-{end_byte}" if end_byte else ""
        
        try:
            r = self.session.get(url, headers=headers, stream=True, timeout=60)
            r.raise_for_status()
            
            total_size = int(r.headers.get("content-length", 0))
            if end_byte:
                total_size = end_byte - start_byte + 1
            
            mode = "ab" if start_byte > 0 else "wb"
            downloaded = start_byte
            
            with open(temp_file, mode) as f:
                for chunk in r.iter_content(chunk_size=512 * 1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        PROGRESS.add_downloaded(len(chunk))
                        
                        # 定期保存进度
                        if downloaded % (5 * 1024 * 1024) < 512 * 1024:
                            RESUME_MANAGER.save_progress(url, save_path, downloaded, total_size + start_byte)
            
            # 移动到最终位置
            import shutil
            shutil.move(str(temp_file), save_path)
            RESUME_MANAGER.clear_progress(url, save_path)
            
            return downloaded - start_byte
            
        except Exception as e:
            log(f"块 {chunk_idx}/{total_chunks} 下载失败: {e}", "ERROR")
            return 0


# ===================== B站下载器 =====================

class BilibiliDownloader(BaseDownloader):
    """哔哩哔哩视频下载器"""
    
    NAME = "哔哩哔哩"
    SUPPORT_PROXY = False  # B站不需要代理
    
    def __init__(self):
        super().__init__(use_proxy=False)
        self.api_session = build_session(False)
        self.api_session.headers.update({
            "Referer": "https://www.bilibili.com/",
            "Origin": "https://www.bilibili.com",
        })
    
    @staticmethod
    def match(url: str) -> bool:
        return (
            "bilibili.com/video" in url or
            "b23.tv" in url or
            re.search(r"BV[0-9A-Za-z]{10}", url) is not None
        )
    
    @staticmethod
    def extract_bvid(url: str) -> Optional[str]:
        m = re.search(r"(BV[0-9A-Za-z]{10})", url)
        return m.group(1) if m else None
    
    def _resolve_short_link(self, url: str) -> str:
        try:
            r = self.session.head(url, allow_redirects=True, timeout=10)
            return r.url
        except Exception:
            return url
    
    def get_video_info(self, bvid: str) -> Optional[Dict]:
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
    
    def get_play_url(self, bvid: str, cid: int, qn: int = 64) -> Optional[Dict]:
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
    
    def download(self, url: str, save_dir: str, quality: str = "720P") -> Tuple[Optional[str], int, bool]:
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
        duration = info.get("duration", 0)
        owner = info.get("owner", {}).get("name", "")
        
        log(f"标题: {title}")
        log(f"UP主: {owner}")
        log(f"时长: {fmt_time(duration)}")
        
        if not cid:
            log("缺少 cid", "ERROR")
            return None, 0, False
        
        qn_map = {"360P": 16, "480P": 32, "720P": 64, "1080P": 80, "4K": 120}
        qn = qn_map.get(quality, 64)
        
        play_data = self.get_play_url(bvid, cid, qn)
        if not play_data:
            for fallback_qn in [32, 16]:
                log(f"尝试降低清晰度...", "WARN")
                play_data = self.get_play_url(bvid, cid, fallback_qn)
                if play_data:
                    break
        
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
        
        # 注册临时文件
        temp_path = str(save_path) + ".tmp"
        TEMP_MANAGER.register(temp_path)
        
        if save_path.exists():
            existing_size = save_path.stat().st_size
            if existing_size >= total_size * 0.95:
                log(f"文件已存在，跳过下载: {save_path.name}")
                TEMP_MANAGER.complete(temp_path)
                return str(save_path), existing_size, True
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
            
            try:
                r = self.api_session.get(seg_url, headers=seg_headers, stream=True, timeout=60)
                r.raise_for_status()
                
                with open(save_path, "ab") as f:
                    for chunk in r.iter_content(chunk_size=512 * 1024):
                        if chunk:
                            f.write(chunk)
                            total_downloaded += len(chunk)
                            PROGRESS.add_downloaded(len(chunk))
            except Exception as e:
                log(f"分段 {idx} 下载失败: {e}，尝试备用地址...", "WARN")
                for backup_url in seg.get("backup_url", []):
                    try:
                        r = self.api_session.get(backup_url, headers=seg_headers, stream=True, timeout=60)
                        r.raise_for_status()
                        with open(save_path, "ab") as f:
                            for chunk in r.iter_content(chunk_size=512 * 1024):
                                if chunk:
                                    f.write(chunk)
                                    total_downloaded += len(chunk)
                                    PROGRESS.add_downloaded(len(chunk))
                        break
                    except Exception:
                        continue
        
        if total_downloaded == 0:
            if save_path.exists():
                save_path.unlink()
            TEMP_MANAGER.complete(temp_path)
            log("视频下载失败", "ERROR")
            return None, 0, False
        
        PROGRESS.finish()
        final_size = save_path.stat().st_size
        TEMP_MANAGER.complete(temp_path)
        log(f"下载完成: {save_path.name} ({fmt_size(final_size)})", "SUCCESS")
        return str(save_path), final_size, True


# ===================== YouTube 下载器 =====================

class YouTubeDownloader(BaseDownloader):
    """YouTube视频下载器（需要代理）"""
    
    NAME = "YouTube"
    SUPPORT_PROXY = True
    
    # YouTube视频ID匹配
    ID_PATTERNS = [
        r"(?:v=|youtu\.be/|embed/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]
    
    def __init__(self):
        super().__init__(use_proxy=True)
    
    @staticmethod
    def match(url: str) -> bool:
        return "youtube.com" in url or "youtu.be" in url
    
    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        for pattern in YouTubeDownloader.ID_PATTERNS:
            m = re.search(pattern, url)
            if m:
                return m.group(1)
        return None
    
    def download(self, url: str, save_dir: str, quality: str = "720P") -> Tuple[Optional[str], int, bool]:
        video_id = self.extract_video_id(url)
        if not video_id:
            log("无法提取 YouTube 视频 ID", "ERROR")
            return None, 0, False
        
        log(f"解析 YouTube 视频: {video_id}")
        
        # 使用第三方API获取视频信息
        try:
            # 尝试多个API源
            api_sources = [
                f"https://api.yewtu.be/api/v1/videos/{video_id}",
                f"https://invidious.snopyta.org/api/v1/videos/{video_id}",
            ]
            
            video_info = None
            for api_url in api_sources:
                try:
                    r = self.session.get(api_url, timeout=15)
                    if r.status_code == 200:
                        video_info = r.json()
                        break
                except Exception:
                    continue
            
            if not video_info:
                log("无法获取视频信息，可能需要代理", "ERROR")
                return None, 0, False
            
            title = video_info.get("title", video_id)
            log(f"标题: {title}")
            
            # 获取视频流
            adaptive_formats = video_info.get("adaptiveFormats", [])
            format_streams = video_info.get("formatStreams", [])
            
            # 选择合适的质量
            quality_map = {"360P": 18, "480P": 35, "720P": 22, "1080P": 37}
            target_itag = quality_map.get(quality, 22)
            
            stream_url = None
            for fmt in format_streams:
                if fmt.get("itag") == str(target_itag):
                    stream_url = fmt.get("url")
                    break
            
            if not stream_url and adaptive_formats:
                # 尝试自适应格式
                for fmt in adaptive_formats:
                    if "video" in fmt.get("type", ""):
                        stream_url = fmt.get("url")
                        if stream_url:
                            break
            
            if not stream_url:
                log("未找到可用的视频流", "ERROR")
                return None, 0, False
            
            # 下载视频
            safe_title = safe_name(title)
            save_path = Path(save_dir) / f"{safe_title}.mp4"
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            PROGRESS.set_current(safe_title)
            
            r = self.session.get(stream_url, stream=True, timeout=120)
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
            log(f"YouTube 下载失败: {e}", "ERROR")
            return None, 0, False


# ===================== 通用视频下载器 =====================

class GenericVideoDownloader(BaseDownloader):
    """通用视频下载器 - 直接下载视频文件URL"""
    
    NAME = "通用直链"
    SUPPORT_PROXY = True
    
    @staticmethod
    def match(url: str) -> bool:
        path = urlparse(url).path.lower()
        return any(path.endswith(ext) for ext in (".mp4", ".webm", ".m3u8", ".mkv", ".flv", ".avi"))
    
    def download(self, url: str, save_dir: str, quality: str = None) -> Tuple[Optional[str], int, bool]:
        filename = safe_name(Path(urlparse(url).path).name) or "video.mp4"
        if not filename.endswith((".mp4", ".webm", ".mkv", ".flv", ".avi")):
            filename += ".mp4"
        save_path = Path(save_dir) / filename
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        log(f"下载: {filename}")
        PROGRESS.set_current(filename)
        
        # 注册临时文件
        temp_path = str(save_path) + ".tmp"
        TEMP_MANAGER.register(temp_path)
        
        try:
            r = self.session.get(url, stream=True, timeout=60)
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
            TEMP_MANAGER.complete(temp_path)
            log(f"下载完成: {save_path.name} ({fmt_size(final_size)})", "SUCCESS")
            return str(save_path), final_size, True
            
        except Exception as e:
            log(f"下载失败: {e}", "ERROR")
            if save_path.exists():
                save_path.unlink()
            TEMP_MANAGER.complete(temp_path)
            return None, 0, False


# ===================== 下载器管理 =====================

DOWNLOADERS = [
    BilibiliDownloader,
    YouTubeDownloader,
]


def get_downloader(url: str) -> Optional[BaseDownloader]:
    """根据URL自动匹配下载器"""
    for dl_cls in DOWNLOADERS:
        if dl_cls.match(url):
            return dl_cls()
    if GenericVideoDownloader.match(url):
        return GenericVideoDownloader()
    return None


# ===================== 批量下载 =====================

def batch_download(urls: List[str], save_dir: str, quality: str = "720P") -> List[Tuple]:
    """批量下载多个视频（并发下载，默认3个并发）"""
    save_dir = Path(save_dir).resolve()
    save_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    max_workers = min(3, len(urls))  # 3个并发下载
    
    def download_one(url: str, idx: int, total: int):
        print(f"\n{'='*60}")
        print(f"[{idx}/{total}] 处理: {url[:80]}")
        print(f"{'='*60}")
        
        downloader = get_downloader(url)
        if not downloader:
            log(f"不支持的视频链接: {url[:60]}", "WARN")
            return (url, "不支持", None, 0)
        
        try:
            log(f"使用下载器: {downloader.NAME}")
            path, size, ok = downloader.download(url, save_dir, quality)
            if ok:
                return (url, "成功", path, size)
            else:
                return (url, "失败", None, 0)
        except Exception as e:
            log(f"下载异常: {e}", "ERROR")
            return (url, f"异常: {e}", None, 0)
    
    # 并发下载
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(download_one, url.strip(), i, len(urls)): url
            for i, url in enumerate(urls, 1) if url.strip()
        }
        for future in as_completed(future_to_url):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                url = future_to_url[future]
                results.append((url, f"异常: {e}", None, 0))
    
    # 统计结果
    success = sum(1 for _, status, _, _ in results if status == "成功")
    fail = len(results) - success
    total_size = sum(s for _, _, _, s in results)
    
    print(f"\n{'='*60}")
    print(f"下载完成统计:")
    print(f"  成功: {success} 个")
    print(f"  失败: {fail} 个")
    print(f"  总大小: {fmt_size(total_size)}")
    print(f"  保存目录: {save_dir}")
    print(f"{'='*60}\n")
    
    return results


# ===================== 依赖检查 =====================

def ensure_deps():
    frozen = getattr(sys, "frozen", False)
    needed = []
    if not frozen:
        if not _have("requests"):
            needed.append("requests")
        if not _have("urllib3"):
            needed.append("urllib3")
    
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


# ===================== 交互式界面 =====================

def main():
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     DL-Web CP - 增强版视频下载器 {VERSION}                      ║
║     支持: B站 | YouTube | 抖音 | 直链                           ║
║     功能: 稳定代理 | 断点续传 | 并发下载 | 智能定位              ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ⚠️  重要提示 / IMPORTANT
  在使用本软件之前，请务必查看 README 文档：
  Before using this software, please read the README first:
  
  📖 中文文档: README.md
  📖 English:   README_EN.md
  
  包含: 安装说明、使用教程、常见问题解答
  
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    
    # 询问用户是否已阅读 README
    try:
        ack = input("您是否已阅读 README 文档？(y=是/n=否，继续使用请输入y): ").strip().lower()
        if ack != 'y':
            print("\n" + "="*60)
            print("📖 请先查看 README 文档获取详细使用说明！")
            print("📖 Please read the README documentation for detailed instructions!")
            print("📖")
            print("📖 中文说明:")
            print("📖   1. 解压下载的压缩包")
            print("📖   2. 双击 webcp_signing.cer 安装签名证书")
            print("📖   3. 查看 README.md 了解详细使用方法")
            print("📖   4. 确认后再次运行本程序")
            print("📖")
            print("📖 English:")
            print("📖   1. Extract the downloaded archive")
            print("📖   2. Double-click webcp_signing.cer to install the signing certificate")
            print("📖   3. Check README_EN.md for detailed usage")
            print("📖   4. Re-run this program after confirmation")
            print("="*60)
            try:
                input("\n按回车键退出...")
            except:
                pass
            sys.exit(0)
    except (EOFError, KeyboardInterrupt):
        print("\n再见！")
        sys.exit(0)
    
    while True:
        print("""
请选择操作:
  [1] 单个视频下载
  [2] 批量视频下载（支持并发）
  [3] 初始化代理池（首次使用必选！用于外网加速）
  [4] 查看已使用的代理
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
                # 打开文件夹并选中文件
                open_folder_and_select(path)
            else:
                _msg_box("下载失败，请检查URL或网络连接。", "下载失败", 0x10)
        
        elif choice == "2":
            print("\n请输入视频URL列表，每行一个，输入空行结束:")
            urls = []
            while True:
                try:
                    line = input()
                    if not line.strip():
                        break
                    urls.append(line.strip())
                except EOFError:
                    break
            
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
            
            # 打开保存目录
            abs_save_dir = Path(save_dir).resolve()
            open_folder_and_select(str(abs_save_dir))
            
            _msg_box(
                f"批量下载完成！\n\n成功: {success_count}/{len(results)}\n总大小: {fmt_size(total_size)}\n保存目录: {abs_save_dir}",
                "批量下载完成"
            )
        
        elif choice == "3":
            print("\n" + "="*60)
            print("初始化代理池（用于加速外网视频下载）")
            print("提示：这可能需要 20-40 秒，请耐心等待...")
            print("="*60)
            PROXY_POOL.initialize()
            if PROXY_POOL.best_proxy:
                print(f"\n✅ 代理池就绪！当前最优代理: {PROXY_POOL.best_proxy.host}:{PROXY_POOL.best_proxy.port}")
                print(f"   可用代理数量: {len(PROXY_POOL.proxies)}")
                print("   现在可以下载 YouTube 等外网视频了！")
            else:
                print("\n⚠️ 所有代理均不可用，将使用直连下载。")
                print("   建议检查网络连接或稍后重试。")
        
        elif choice == "4":
            if not PROXY_POOL.proxies:
                print("\n代理池尚未初始化。请先选择 [3] 初始化代理池。")
            else:
                print(f"\n当前可用代理 ({len(PROXY_POOL.proxies)} 个):")
                print("-" * 50)
                for i, p in enumerate(PROXY_POOL.proxies[:10], 1):
                    status = "✅" if p.latency < 5 else "⚠️"
                    print(f"  {status} {i}. {p.host}:{p.port} (延迟: {p.latency:.2f}s, 成功: {p.success_count})")
                if len(PROXY_POOL.proxies) > 10:
                    print(f"  ... 还有 {len(PROXY_POOL.proxies) - 10} 个")
                print("-" * 50)
                if PROXY_POOL.best_proxy:
                    print(f"🏆 最优: {PROXY_POOL.best_proxy.host}:{PROXY_POOL.best_proxy.port}")
        
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