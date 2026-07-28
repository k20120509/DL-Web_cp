# DL-Web CP - Enhanced Video Downloader V2.5

> One-click video downloader for multiple platforms | Stable proxy pool | Resume download | Concurrent download | Portable

---

## ⚠️ Important Notice

This program uses a **Windows self-signed certificate** (CN=Web CP Tools, O=k20120509) for code signing.

Since it's a developer self-signed certificate, first-time downloads may trigger:
- Windows SmartScreen warnings
- Antivirus software (360, Windows Defender, etc.) false positives

### Solutions (Choose One)

1. **Install the signing certificate (Recommended)**: Extract → Double-click `webcp_signing.cer` → "Install Certificate" → Select "Trusted Root Certification Authorities" → Done
2. **Add to whitelist**: Add `video_downloader.exe` to your antivirus trust list
3. **Temporarily disable antivirus**: Disable antivirus before running

---

## Table of Contents

- [Quick Start](#quick-start)
- [Detailed Tutorial](#detailed-tutorial)
- [Features](#features)
- [Supported Platforms](#supported-platforms)
- [FAQ](#faq)
- [Changelog](#changelog)
- [Support](#support)

---

## Quick Start

### Step 1: Download and Extract

1. Visit [GitHub Releases](https://github.com/k20120509/DL-Web_cp/releases/tag/V2.5)
2. Download `video_downloader_v2.5.exe`
3. Place it in any folder (e.g., `D:\Tools\DL-Web_cp\`)

### Step 2: Install Signing Certificate (Required)

1. Double-click `webcp_signing.cer`
2. Click "Install Certificate"
3. Select "Local Machine" → Next
4. Select "Place all certificates in the following store" → "Trusted Root Certification Authorities"
5. Click Next → Finish
6. Restart your computer (or refresh system cache)

### Step 3: Run the Program

1. Double-click `video_downloader_v2.5.exe`
2. Read the welcome screen
3. Type `y` to confirm you've read the documentation
4. Start using!

---

## Detailed Tutorial

### 3.1 Initialize Proxy Pool (First Use Required)

The proxy pool is used to accelerate downloads from foreign websites (like YouTube). **We recommend initializing it even if you only download Bilibili videos**.

```
Select an option:
  [1] Single video download
  [2] Batch video download
  [3] Initialize proxy pool <- Select this!
  [4] View proxies
  [0] Exit

Enter your choice: 3
```

The program will automatically:
1. Fetch proxy lists from multiple online sources
2. Test 80 proxies concurrently for availability
3. Filter out working proxies
4. Sort by latency and select the best proxy

**This takes about 20-40 seconds. Please be patient.**

### 3.2 Download a Single Video

```
Select an option: 1
Enter video URL: https://www.bilibili.com/video/BV1xx411c7mu

Select quality:
  [1] 360P
  [2] 480P
  [3] 720P (Recommended)
  [4] 1080P
  [5] 4K
Select (default 3): 3

Enter save directory (default ./downloads): D:\Videos\

Download successful!
File: xxx.mp4
Size: 49.6MB
Path: D:\Videos\xxx.mp4
```

**Supported URL formats:**
- Bilibili video page: `https://www.bilibili.com/video/BV1xx411c7mu`
- Bilibili BV number: `BV1xx411c7mu`
- Bilibili short link: `https://b23.tv/xxxxx`
- YouTube link: `https://www.youtube.com/watch?v=xxxxx`
- YouTube short link: `https://youtu.be/xxxxx`
- Direct video link: `https://example.com/video.mp4`

### 3.3 Batch Download Multiple Videos

```
Select an option: 2
Enter video URLs (one per line, blank line to finish):
> https://www.bilibili.com/video/BV1xx411c7mu
> https://www.bilibili.com/video/BV1yy411c7nv
> https://www.youtube.com/watch?v=xxxxx
> (blank line to finish)

Total: 3 videos
...
Download Statistics:
  Success: 3
  Failed: 0
  Total Size: 125.3MB
  Save Directory: D:\Videos
```

**Batch download supports 3 concurrent downloads** for faster speed.

### 3.4 View Proxy Pool Status

```
Select an option: 4

Available Proxies (5):
--------------------------------------------------
  ✅ 1. 1.2.3.4:8080 (Latency: 0.52s, Success: 15)
  ✅ 2. 5.6.7.8:8080 (Latency: 1.23s, Success: 8)
  ...
--------------------------------------------------
🏆 Best: 1.2.3.4:8080
```

---

## Features

### 1. Stable Proxy Pool (V2.5 Core Feature)

- **Multi-source fetching**: Automatically fetches from 8+ well-known free proxy sources
- **Strict testing**: Each proxy goes through 3 layers of validation
  - Proxy connectivity test
  - Target website accessibility test
  - Response latency measurement
- **Dynamic switching**: Automatically switches to the next proxy on failure
- **Priority management**: Successful proxies get higher priority, failed ones get lower
- **Auto-cleanup**: Proxies that fail 3 times are automatically removed

### 2. Resume Download

- Automatically saves progress when download is interrupted
- Progress saved to `%TEMP%\dl_web_cp\` directory
- Auto-resumes from the last checkpoint on next download
- Supports recovery from network interruptions and program crashes

### 3. Smart File Management

- **Auto-cleanup**: Incomplete temporary files are automatically deleted on exit
- **Auto-locate**: Opens folder and selects file after successful download
- **Progress persistence**: Download progress saved periodically to prevent loss

### 4. Concurrent Batch Download

- Supports downloading 3 videos simultaneously
- Real-time download status for each video
- Failure of one video doesn't affect others

### 5. Multi-platform Support

- Bilibili: Full functionality
- YouTube: Supported via proxy pool
- Direct links: Supports mp4/webm/flv/mkv, etc.

### 6. Multiple Quality Options

- 360P (SD)
- 480P (ED)
- 720P (HD, Recommended)
- 1080P (FHD)
- 4K (UHD)
- Auto-degradation: Automatically tries lower quality if high quality fails

---

## Supported Platforms

| Platform | Status | Notes |
|----------|--------|-------|
| **Bilibili** | ✅ Full Support | BV number, short links, multiple qualities |
| **YouTube** | ✅ Supported | Proxy pool must be initialized first |
| **Direct Links** | ✅ Supported | mp4/webm/flv/mkv/avi |
| Douyin | 🚧 In Development | Coming soon |
| Kuaishou | 🚧 In Development | Coming soon |
| Twitter/X | 🚧 In Development | Coming soon |

---

## FAQ

### Q1: Double-clicking the exe does nothing?

**A**: Antivirus software might be blocking it. Please:
1. Check your antivirus quarantine area
2. Temporarily disable antivirus and try again
3. Or install the signing certificate (see "Important Notice" section)

### Q2: Bilibili video download fails?

**A**: Possible reasons:
1. Video deleted or has regional restrictions
2. Unstable network
3. Quality too high (4K may fail for non-premium accounts)

**Solutions:**
1. Try lower quality (720P or 480P)
2. Check if the URL is correct
3. Try again later

### Q3: YouTube video download fails?

**A**: You MUST initialize the proxy pool first!
1. Run the program
2. Select [3] to initialize proxy pool
3. Wait for initialization to complete
4. Then download YouTube videos

If it still fails after initialization:
- Your network environment may block foreign access
- All available proxies may be unable to access YouTube

### Q4: Download interrupted?

**A**: This program supports resume download!
1. Re-run the program
2. Enter the same URL and save path
3. The program will automatically resume from where it left off

### Q5: Where are downloaded files?

**A**: 
1. The folder opens automatically and selects the file after successful download
2. If you closed the dialog, the path is shown in the program
3. Default save path is `./downloads/` (relative to exe location)

### Q6: How to uninstall/clean up?

**A**: 
1. Delete `video_downloader_v2.5.exe`
2. Delete the downloaded video folder
3. Delete temporary files: `%TEMP%\dl_web_cp\`
4. To remove the certificate:
   - Open Run → `certmgr.msc`
   - Find "Trusted Root Certification Authorities"
   - Delete the `Web CP Tools` certificate

### Q7: Are the proxies working?

**A**: 
- Proxy pool fetches proxies from multiple well-known sources
- Proxies go through strict testing (connectivity, latency, availability)
- Only working proxies are retained
- However, free proxies may become unavailable over time. Re-initialize periodically.

---

## Changelog

### V2.5 (2026-07-28)

**Major Update:**

1. **Rewrote proxy pool system**
   - Uses 8+ online proxy sources
   - Tests 80 proxies concurrently
   - Multi-layer validation
   - Dynamic switching and priority management

2. **Fixed proxy pool unavailability**
   - Added more proxy sources
   - Added domestic backup proxies
   - Improved testing algorithm

3. **Added "Read README" confirmation**
   - Prompts user to read documentation on first run
   - Bilingual prompts (Chinese/English)

4. **Added proxy pool viewer** (Menu [4])
   - Shows all available proxies
   - Shows latency and success rate
   - Highlights best proxy

5. **Optimized batch download**
   - Changed to 3 concurrent downloads
   - Improved batch download speed

6. **Enhanced user interface**
   - More friendly interaction
   - Clearer status display

### V2.0 (Deprecated)

- Initial proxy pool implementation
- Basic resume download
- Automatic file cleanup

### V1.0

- Basic Bilibili video download
- Direct link download
- Batch download

---

## Support

If you encounter issues, please:

1. Check the "FAQ" section in this README
2. Check GitHub Issues: [https://github.com/k20120509/DL-Web_cp/issues](https://github.com/k20120509/DL-Web_cp/issues)
3. Submit a new Issue describing your problem

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

**Thank you for using DL-Web CP V2.5!**