# DL-Web CP - 网站视频下载器

> 一键下载各平台视频 | 纯Python实现 | 无需ffmpeg | 绿色免安装

[![Version](https://img.shields.io/badge/version-V1.0-00d4ff?style=flat-square&logo=github)](https://github.com/k20120509/DL-Web_cp)
[![Python](https://img.shields.io/badge/python-3.8+-3776ab?style=flat-square&logo=python&logoColor=white)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-00d4ff?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows-0078d6?style=flat-square)]()

---

## 支持平台

| 平台 | 状态 | 说明 |
|------|------|------|
| **哔哩哔哩 (B站)** | ✅ 支持 | 支持 BVID 链接、b23.tv 短链接、多清晰度选择 |
| **通用直链** | ✅ 支持 | mp4/webm/flv 等视频文件直链直接下载 |
| 更多平台 | 🚧 开发中 | 持续更新中... |

---

## 核心特性

- **零依赖** - EXE 版本双击即可运行，无需安装 Python 或 ffmpeg
- **多清晰度** - 支持 360P / 480P / 720P / 1080P / 4K 多种清晰度
- **批量下载** - 支持 URL 列表批量下载，一次处理多个视频
- **智能识别** - 自动识别视频平台，选择对应下载策略
- **进度显示** - 实时显示下载进度、速度、剩余时间
- **断点续传** - 已下载文件自动跳过，节省时间
- **备用地址** - 下载失败自动尝试备用 CDN 地址

---

## 快速开始

### 方式一：EXE 版本（推荐 Windows 用户）

下载 `video_downloader.exe`，双击运行，按提示操作即可。

### 方式二：源码运行

```bash
# 安装依赖
pip install requests

# 运行
python video_downloader.py
```

---

## 使用说明

### 单个视频下载

1. 运行程序，选择 `[1] 单个视频下载`
2. 粘贴视频 URL（如 `https://www.bilibili.com/video/BV1xx411c7mD`）
3. 选择清晰度（推荐 720P）
4. 输入保存目录（默认 `./downloads`）
5. 等待下载完成

### 批量视频下载

1. 运行程序，选择 `[2] 批量视频下载`
2. 粘贴多个视频 URL，每行一个，空行结束
3. 选择清晰度和保存目录
4. 自动批量下载，完成后显示统计

### 支持的 URL 格式

**哔哩哔哩:**
```
https://www.bilibili.com/video/BV1xx411c7mD
https://b23.tv/xxxxxx
BV1xx411c7mD
```

**通用直链:**
```
https://example.com/video.mp4
https://example.com/video.webm
```

---

## B站下载技术说明

### API 调用流程

```
输入 BVID
   |
   v
[获取视频信息] /x/web-interface/view
   |  - 标题、UP主、时长、封面
   |  - CID（视频分P标识）
   v
[获取播放地址] /x/player/playurl
   |  - fnval=0 (durl格式，音视频合一)
   |  - 多清晰度选择 (qn参数)
   v
[分段下载]
   |  - 支持多CDN备用地址
   |  - 流式下载，实时进度
   v
输出 MP4 文件
```

### 清晰度对照表

| qn 值 | 清晰度 | 说明 |
|-------|--------|------|
| 16 | 360P | 流畅 |
| 32 | 480P | 清晰 |
| 64 | 720P | 高清（推荐） |
| 80 | 1080P | 超清 |
| 120 | 4K | 蓝光（需要大会员） |

> **注意**：高清晰度（1080P+）可能需要登录 Cookie 才能下载。当前版本使用未登录模式，默认最高 720P。

---

## 输出结构

```
downloads/
├── 视频标题1.mp4
├── 视频标题2.mp4
└── ...
```

---

## 常见问题

### Q: 下载失败怎么办？

A: 
1. 检查网络连接是否正常
2. 尝试降低清晰度（如 720P 降到 480P）
3. 确认视频链接是否有效，可在浏览器中打开测试

### Q: 为什么最高只能下 720P？

A: B 站 1080P 及以上清晰度需要登录账号。当前版本为匿名访问模式，默认最高 720P。

### Q: 下载速度慢？

A: 
- B 站视频下载速度受限于 CDN 和网络环境
- 可以尝试更换网络环境
- 程序已内置多 CDN 备用地址自动切换

### Q: 支持下载番剧/电影吗？

A: 当前版本主要支持 UP 主投稿视频。番剧、电影等版权内容受 DRM 保护，无法直接下载。

---

## 相关仓库

- **[web-cp](https://github.com/k20120509/web-cp)** - 网站克隆器，全站克隆 + 视频下载一体化

---

## 免责声明

1. 本工具仅供学习交流使用
2. 请勿用于商业用途
3. 下载的视频版权归原作者所有
4. 使用本工具产生的任何问题由使用者自行承担

---

## 许可证

MIT License

---

*Download everything. Pure Python, zero dependencies.*
