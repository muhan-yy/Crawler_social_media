# -*- coding: utf-8 -*-
"""
工具函数模块
提供通用的工具函数
"""

import os
import re
import json
import random
import logging
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict, Any
from urllib.parse import quote


def setup_logger(name: str, log_file: str = None, level: int = logging.INFO) -> logging.Logger:
    """
    设置日志记录器

    Args:
        name: 日志记录器名称
        log_file: 日志文件路径（可选）
        level: 日志级别

    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)

    # 格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def generate_time_windows(start_date: str, end_date: str) -> List[Tuple[datetime, datetime]]:
    """
    生成小时级别的时间窗口列表

    Args:
        start_date: 开始时间，格式 "2024-06-13 00:00"
        end_date: 结束时间，格式 "2024-06-14 23:59"

    Returns:
        时间窗口列表，每个元素为 (start_datetime, end_datetime)
    """
    start = datetime.strptime(start_date, '%Y-%m-%d %H:%M')
    end = datetime.strptime(end_date, '%Y-%m-%d %H:%M')

    windows = []
    current = start

    while current < end:
        # 小时级别窗口：当前时间到下一个小时
        next_hour = current.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        window_end = min(next_hour, end)
        windows.append((current, window_end))
        current = window_end

    return windows


def format_time_for_url(dt: datetime) -> str:
    """
    将datetime格式化为微博URL所需的时间格式（小时级别）

    Args:
        dt: datetime对象

    Returns:
        格式化的时间字符串，如 "2024-06-13-8" (年-月-日-小时)
    """
    return dt.strftime('%Y-%m-%d-%-H')


def format_time_for_display(dt: datetime) -> str:
    """
    将datetime格式化为可读的时间格式

    Args:
        dt: datetime对象

    Returns:
        格式化的时间字符串，如 "2024-06-13 08:00:00"
    """
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def build_search_url(keyword: str, start_time: datetime, end_time: datetime, page: int = 1) -> str:
    """
    构建微博搜索URL

    Args:
        keyword: 搜索关键词
        start_time: 开始时间
        end_time: 结束时间
        page: 页码

    Returns:
        完整的搜索URL
    """
    base_url = "https://s.weibo.com/weibo"
    encoded_keyword = quote(keyword)
    # 使用新格式: custom:2024-07-01-0:2024-07-01-1
    time_scope = f"custom:{format_time_for_url(start_time)}:{format_time_for_url(end_time)}"

    # 添加额外参数提高搜索效果
    url = f"{base_url}?q={encoded_keyword}&typeall=1&suball=1&timescope={time_scope}&Refer=g"
    if page > 1:
        url += f"&page={page}"

    return url


def get_random_delay(min_delay: float, max_delay: float) -> float:
    """
    获取随机延迟时间

    Args:
        min_delay: 最小延迟（秒）
        max_delay: 最大延迟（秒）

    Returns:
        随机延迟时间
    """
    return random.uniform(min_delay, max_delay)


def get_random_user_agent() -> str:
    """
    获取随机User-Agent

    Returns:
        User-Agent字符串
    """
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]
    return random.choice(user_agents)


def get_request_headers(cookie: str) -> Dict[str, str]:
    """
    获取请求头

    Args:
        cookie: Cookie字符串

    Returns:
        请求头字典
    """
    return {
        'User-Agent': get_random_user_agent(),
        'Cookie': cookie,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://s.weibo.com/',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }


def save_json(data: Any, filepath: str, ensure_dir: bool = True) -> bool:
    """
    保存数据到JSON文件

    Args:
        data: 要保存的数据
        filepath: 文件路径
        ensure_dir: 是否自动创建目录

    Returns:
        是否保存成功
    """
    try:
        if ensure_dir:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存JSON文件失败: {e}")
        return False


def load_json(filepath: str) -> Optional[Any]:
    """
    从JSON文件加载数据

    Args:
        filepath: 文件路径

    Returns:
        加载的数据，失败返回None
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载JSON文件失败: {e}")
        return None


def load_progress(progress_file: str) -> Dict[str, List[str]]:
    """
    加载爬取进度

    Args:
        progress_file: 进度文件路径

    Returns:
        进度字典，格式为 {keyword: [completed_time_windows]}
    """
    if not os.path.exists(progress_file):
        return {}

    data = load_json(progress_file)
    return data if data else {}


def save_progress(progress_file: str, progress: Dict[str, List[str]]) -> bool:
    """
    保存爬取进度

    Args:
        progress_file: 进度文件路径
        progress: 进度字典

    Returns:
        是否保存成功
    """
    return save_json(progress, progress_file)


def extract_weibo_id(url: str) -> Optional[str]:
    """
    从URL中提取微博ID

    Args:
        url: 微博URL

    Returns:
        微博ID
    """
    # 匹配模式: https://weibo.com/1234567890/Oabcdefg
    # 或者: https://m.weibo.cn/detail/1234567890
    patterns = [
        r'weibo\.com/\d+/(\w+)',
        r'weibo\.cn/detail/(\d+)',
        r'weibo\.com/\d+/status/(\w+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


def clean_text(text: str) -> str:
    """
    清理文本内容

    Args:
        text: 原始文本

    Returns:
        清理后的文本
    """
    if not text:
        return ""

    # 移除HTML标签
    text = re.sub(r'<[^>]+>', '', text)
    # 移除多余的空白
    text = re.sub(r'\s+', ' ', text)
    # 移除首尾空白
    text = text.strip()

    return text


def ensure_dir(path: str) -> None:
    """
    确保目录存在

    Args:
        path: 目录路径
    """
    os.makedirs(path, exist_ok=True)
