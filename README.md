# WiseBillow - 微博多模态数据爬虫

微博搜索数据爬虫，支持按关键词和时间窗口爬取微博文本、图片、视频等多模态数据。

## 项目结构

```
WiseBillow/
├── crawler_wb/                 # 爬虫核心模块
│   ├── weibo_crawler.py        # 爬虫主程序（入口）
│   ├── config.py               # 配置管理模块
│   ├── cookie_manager.py       # Cookie轮换与失效管理
│   ├── data_extractor.py       # 数据提取模块（HTML解析）
│   ├── data_cleaner.py         # 数据清洗模块
│   ├── media_downloader.py     # 媒体下载模块
│   ├── utils.py                # 工具函数模块
│   └── test_crawler.py         # 测试脚本
│
├── data/                       # 数据存储目录
│   ├── text/                   # 文本数据（JSON格式）
│   ├── images/                 # 图片数据（分层存储）
│   └── videos/                 # 视频数据（分层存储）
│
├── logs/                       # 日志目录
│   ├── crawler_*.log           # 运行日志
│   ├── progress.json           # 成功进度记录
│   └── failed_pages.json       # 失败页面记录
│
├── config_wb.yaml              # 配置文件
├── cookies_wb.txt              # Cookie存储文件
├── keywords.txt                # 关键词列表文件
└── README.md                   # 说明文档
```

## 功能特性

- **关键词搜索**：支持多关键词爬取，关键词存放在独立文件中
- **时间窗口控制**：小时级别时间窗口，精确控制爬取时间范围
- **多模态数据**：支持爬取文本、图片、视频，可配置保存哪些模态
- **Cookie轮换**：支持多Cookie轮换，自动检测失效并标记
- **进度追踪**：页面级别进度记录，支持断点续爬和失败重试
- **分层存储**：按关键词→时间窗口→推文ID分层存储媒体文件

## 快速开始

### 1. 安装依赖

```bash
pip install requests beautifulsoup4
```

### 2. 配置Cookie

编辑 `cookies_wb.txt` 文件，添加微博Cookie（每行一个）：

```
# 微博Cookie列表（每行一个Cookie）
# 获取方法：登录weibo.com后从浏览器开发者工具中复制
# 失效Cookie会自动添加【ERROR】标记，可手动删除或更新

你的Cookie内容1
你的Cookie内容2
```

**Cookie获取方法**：
1. 打开浏览器，登录 https://weibo.com
2. 按 F12 打开开发者工具
3. 切换到 Network 标签
4. 刷新页面
5. 点击任意请求，在 Headers 中找到 Cookie 字段
6. 复制完整的 Cookie 值粘贴到 `cookies_wb.txt`

### 3. 配置关键词

编辑 `keywords.txt` 文件，添加搜索关键词（每行一个）：

```
# 微博爬虫关键词列表
# 每行一个关键词，以#开头的行会被忽略

洪水
暴雨
台风
...
```

### 4. 配置参数

编辑 `config_wb.yaml` 文件，设置爬取参数：

```yaml
# 时间配置
time:
  start_date: "2024-07-01 00:00"  # 开始时间
  end_date: "2024-07-01 23:59"    # 结束时间

# 模态数据保存配置
modalities:
  save_text: true      # 是否保存文本
  save_images: true    # 是否保存图片
  save_videos: false   # 是否保存视频
  image_quality: "large"  # 图片质量
  video_quality: "480p"   # 视频质量

# 爬虫配置
crawler:
  request_delay_min: 20.0  # 最小请求间隔（秒）
  request_delay_max: 50.0  # 最大请求间隔（秒）
```

### 5. 运行爬虫

```bash
# 使用默认配置运行
python crawler_wb/weibo_crawler.py

# 指定配置文件
python crawler_wb/weibo_crawler.py --config config_wb.yaml

# 指定时间范围（覆盖配置文件）
python crawler_wb/weibo_crawler.py --start "2024-07-01 00:00" --end "2024-07-02 23:59"
```

## 数据存储格式

### 文本数据

存储在 `data/text/` 目录，JSON格式：

```
data/text/
├── 洪水_2024-07-01-0_2024-07-01-1.json
├── 洪水_2024-07-01-1_2024-07-01-2.json
├── 暴雨_2024-07-01-0_2024-07-01-1.json
└── ...
```

文件命名格式：`{关键词}_{开始时间}_{结束时间}.json`

每条微博数据结构：
```json
{
  "weibo_id": "5051129438406439",
  "author": "用户名",
  "author_id": "用户ID",
  "content": "微博正文内容",
  "publish_time": "发布时间",
  "reposts_count": "转发数",
  "comments_count": "评论数",
  "likes_count": "点赞数",
  "has_images": true,
  "has_video": false,
  "images": ["图片路径列表"],
  "video": "视频路径",
  "crawl_time": "爬取时间"
}
```

### 图片数据

分层存储在 `data/images/` 目录：

```
data/images/
├── 洪水/                          # 关键词
│   ├── 2024-07-01-0_2024-07-01-1/  # 时间窗口
│   │   ├── 5051129438406439/       # 推文ID
│   │   │   ├── 0.jpg
│   │   │   └── 1.jpg
│   │   └── 5051129438406440/
│   │       └── 0.jpg
│   └── 2024-07-01-1_2024-07-01-2/
│       └── ...
└── 暴雨/
    └── ...
```

### 视频数据

分层存储在 `data/videos/` 目录，结构与图片类似：

```
data/videos/
├── 洪水/
│   ├── 2024-07-01-0_2024-07-01-1/
│   │   └── 5051129438406439/
│   │       └── 480p.mp4
│   └── ...
└── ...
```

## 进度管理

### 成功进度 (`logs/progress.json`)

记录已成功爬取的页面：

```json
{
  "洪水": {
    "洪水_2024-07-01-0_2024-07-01-1": [1, 2, 3, 4, 5],
    "洪水_2024-07-01-1_2024-07-01-2": [1, 2]
  },
  "暴雨": {
    "暴雨_2024-07-01-0_2024-07-01-1": [1]
  }
}
```

格式：`{关键词: {时间窗口标识: [已完成页码列表]}}`

### 失败进度 (`logs/failed_pages.json`)

记录失败的页面及其详情：

```json
{
  "洪水": {
    "洪水_2024-07-01-0_2024-07-01-1": {
      "3": {
        "fail_count": 2,
        "first_fail_time": "2024-07-01 10:30:00",
        "last_fail_time": "2024-07-01 10:45:00",
        "errors": [
          {"error_type": "fetch_failed", "message": "获取页面失败"},
          {"error_type": "cookie_invalid", "message": "Cookie无效"}
        ]
      }
    }
  }
}
```

## Cookie管理

### 失效检测

当Cookie连续失败超过阈值（默认10次），会自动标记为失效：

```
# cookies_wb.txt
【ERROR】失效的Cookie内容
正常的Cookie内容
```

失效Cookie会被添加 `【ERROR】` 前缀，下次加载时自动跳过。

### Cookie轮换

- 每次请求随机选择一个有效Cookie
- 成功请求后重置失败计数
- 失败请求后增加失败计数
- 失败次数超限后标记为失效

## 配置参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `keyword_file` | 关键词文件路径 | `keywords.txt` |
| `cookie_file` | Cookie文件路径 | `cookies_wb.txt` |
| `max_fail_count` | Cookie最大失败次数 | `10` |
| `start_date` | 开始时间 | `2024-07-01 00:00` |
| `end_date` | 结束时间 | `2024-07-01 23:59` |
| `request_delay_min` | 最小请求间隔（秒） | `20.0` |
| `request_delay_max` | 最大请求间隔（秒） | `50.0` |
| `timeout` | 请求超时时间（秒） | `60` |
| `save_text` | 是否保存文本 | `true` |
| `save_images` | 是否保存图片 | `true` |
| `save_videos` | 是否保存视频 | `false` |
| `image_quality` | 图片质量 | `large` |
| `video_quality` | 视频质量 | `480p` |

### 图片质量选项

- `large`：高清原图
- `mw690`：中等尺寸
- `thumbnail`：缩略图

### 视频质量选项

- `720p`：高清
- `480p`：标清
- `360p`：流畅

## 爬取流程

1. 加载配置、关键词、Cookie
2. 生成小时级别时间窗口列表
3. 遍历每个关键词的每个时间窗口：
   - 检查进度，跳过已完成窗口
   - 从起始页开始爬取
   - 获取总页数，循环爬取所有页面（最多10页）
   - 每页完成后立即保存数据并记录进度
   - 失败页面记录到失败日志
4. 输出统计信息

## 注意事项

1. **请求频率**：建议设置合理的请求间隔（20-50秒），避免触发反爬
2. **Cookie有效期**：微博Cookie有效期有限，需定期更新
3. **数据量**：大量关键词和时间窗口会产生大量数据，注意存储空间
4. **断点续爬**：中断后重新运行会自动跳过已完成部分
5. **失败重试**：失败页面会记录，下次运行时优先重试

## 常见问题

### Q: Cookie失效怎么办？

A: 重新登录微博获取新Cookie，更新 `cookies_wb.txt` 文件。失效Cookie会自动标记 `【ERROR】`，可手动删除或更新。

### Q: 如何只爬取文本不下载图片？

A: 在配置文件中设置：
```yaml
modalities:
  save_text: true
  save_images: false
  save_videos: false
```

### Q: 如何扩大时间范围？

A: 修改配置文件中的 `start_date` 和 `end_date`，或使用命令行参数：
```bash
python crawler_wb/weibo_crawler.py --start "2024-07-01 00:00" --end "2024-07-31 23:59"
```

### Q: 爬取中断后如何继续？

A: 直接重新运行，脚本会自动读取进度文件，跳过已完成的时间窗口和页面。

## 许可证

本项目仅供学术研究使用，请遵守微博平台相关规定。
