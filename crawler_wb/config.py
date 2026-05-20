# -*- coding: utf-8 -*-
"""
配置管理模块
管理爬虫的各项配置参数
"""

import os
import yaml
from datetime import datetime
from typing import List
from dataclasses import dataclass, field


@dataclass
class TimeConfig:
    """时间配置"""
    start_date: str  # 格式: "2024-06-13 00:00"
    end_date: str    # 格式: "2024-06-14 23:59"
    time_window: int = 60  # 时间窗口（分钟），默认1小时


@dataclass
class CrawlerConfig:
    """爬虫配置"""
    request_delay_min: float = 2.0  # 请求最小间隔（秒）
    request_delay_max: float = 5.0  # 请求最大间隔（秒）
    max_retries: int = 3            # 最大重试次数
    timeout: int = 30               # 请求超时时间（秒）
    max_workers: int = 5            # 并发下载线程数


@dataclass
class StorageConfig:
    """存储配置"""
    text_dir: str = "data/text"
    image_dir: str = "data/images"
    video_dir: str = "data/videos"
    log_dir: str = "logs"


@dataclass
class CookieManagerConfig:
    """Cookie管理配置"""
    max_fail_count: int = 3  # 最大失败次数


@dataclass
class ModalityConfig:
    """模态数据保存配置"""
    save_text: bool = True           # 是否保存文本
    save_images: bool = False        # 是否保存图片
    save_videos: bool = False        # 是否保存视频
    image_quality: str = "large"     # 图片质量: large, mw690, thumbnail
    video_quality: str = "480p"      # 视频质量: 720p, 480p, 360p


@dataclass
class Config:
    """主配置类"""
    keywords: List[str] = field(default_factory=list)
    keyword_file: str = "keywords.txt"
    cookie_file: str = "cookies.txt"
    cookie_manager: CookieManagerConfig = None
    time: TimeConfig = None
    crawler: CrawlerConfig = None
    storage: StorageConfig = None
    modalities: ModalityConfig = None

    def __post_init__(self):
        if self.cookie_manager is None:
            self.cookie_manager = CookieManagerConfig()
        if self.crawler is None:
            self.crawler = CrawlerConfig()
        if self.storage is None:
            self.storage = StorageConfig()
        if self.modalities is None:
            self.modalities = ModalityConfig()


def load_keywords_from_file(filepath: str) -> List[str]:
    """
    从文件加载关键词

    Args:
        filepath: 关键词文件路径

    Returns:
        关键词列表
    """
    keywords = []
    if not os.path.exists(filepath):
        print(f"关键词文件不存在: {filepath}")
        return keywords

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # 忽略空行和注释行
                if line and not line.startswith('#'):
                    keywords.append(line)
        print(f"从文件加载了 {len(keywords)} 个关键词")
    except Exception as e:
        print(f"读取关键词文件失败: {e}")

    return keywords


def load_config(config_path: str = "config_wb.yaml") -> Config:
    """
    从YAML文件加载配置

    Args:
        config_path: 配置文件路径

    Returns:
        Config对象
    """
    # 获取项目根目录
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_file = os.path.join(base_dir, config_path)

    if not os.path.exists(config_file):
        raise FileNotFoundError(f"配置文件不存在: {config_file}")

    with open(config_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    # 解析时间配置
    time_data = data.get('time', {})
    time_config = TimeConfig(
        start_date=time_data.get('start_date', '2024-06-13 00:00'),
        end_date=time_data.get('end_date', '2024-06-13 23:59'),
        time_window=time_data.get('time_window', 60)
    )

    # 解析爬虫配置
    crawler_data = data.get('crawler', {})
    crawler_config = CrawlerConfig(
        request_delay_min=crawler_data.get('request_delay_min', 2.0),
        request_delay_max=crawler_data.get('request_delay_max', 5.0),
        max_retries=crawler_data.get('max_retries', 3),
        timeout=crawler_data.get('timeout', 30),
        max_workers=crawler_data.get('max_workers', 5)
    )

    # 解析存储配置
    storage_data = data.get('storage', {})
    storage_config = StorageConfig(
        text_dir=storage_data.get('text_dir', 'data/text'),
        image_dir=storage_data.get('image_dir', 'data/images'),
        video_dir=storage_data.get('video_dir', 'data/videos'),
        log_dir=storage_data.get('log_dir', 'logs')
    )

    # 解析Cookie管理配置
    cookie_manager_data = data.get('cookie_manager', {})
    cookie_manager_config = CookieManagerConfig(
        max_fail_count=cookie_manager_data.get('max_fail_count', 3)
    )

    # 解析模态数据配置
    modalities_data = data.get('modalities', {})
    modalities_config = ModalityConfig(
        save_text=modalities_data.get('save_text', True),
        save_images=modalities_data.get('save_images', False),
        save_videos=modalities_data.get('save_videos', False),
        image_quality=modalities_data.get('image_quality', 'large'),
        video_quality=modalities_data.get('video_quality', '480p')
    )

    # 获取关键词文件路径
    keyword_file = data.get('keyword_file', 'keywords.txt')

    # 创建主配置对象
    config = Config(
        keywords=[],  # 先置空，后面从文件加载
        keyword_file=keyword_file,
        cookie_file=data.get('cookie_file', 'cookies.txt'),
        cookie_manager=cookie_manager_config,
        time=time_config,
        crawler=crawler_config,
        storage=storage_config,
        modalities=modalities_config
    )

    # 从文件加载关键词
    keyword_filepath = os.path.join(base_dir, keyword_file)
    config.keywords = load_keywords_from_file(keyword_filepath)

    # 如果关键词文件为空，尝试从配置文件中读取（兼容旧配置）
    if not config.keywords:
        config.keywords = data.get('keywords', ['洪灾'])

    return config


def validate_config(config: Config) -> bool:
    """
    验证配置是否有效

    Args:
        config: Config对象

    Returns:
        配置是否有效
    """
    errors = []

    # 检查关键词
    if not config.keywords:
        errors.append("关键词列表不能为空")

    # 检查Cookie文件
    cookie_file_path = get_absolute_path(config.cookie_file)
    if not os.path.exists(cookie_file_path):
        errors.append(f"Cookie文件不存在: {cookie_file_path}")
    else:
        # 检查文件是否有有效内容
        with open(cookie_file_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines()
                     if line.strip() and not line.strip().startswith('#')]
        if not lines:
            errors.append(f"Cookie文件为空，请在 {cookie_file_path} 中添加Cookie")

    # 检查时间配置
    try:
        start = datetime.strptime(config.time.start_date, '%Y-%m-%d %H:%M')
        end = datetime.strptime(config.time.end_date, '%Y-%m-%d %H:%M')
        if start >= end:
            errors.append("开始时间必须早于结束时间")
    except ValueError as e:
        errors.append(f"时间格式错误: {e}")

    # 检查时间窗口
    if config.time.time_window < 10 or config.time.time_window > 1440:
        errors.append("时间窗口应在10-1440分钟之间")

    # 检查模态配置
    valid_image_qualities = ['large', 'mw690', 'thumbnail']
    if config.modalities.image_quality not in valid_image_qualities:
        errors.append(f"图片质量选项无效，可选值: {valid_image_qualities}")

    valid_video_qualities = ['720p', '480p', '360p']
    if config.modalities.video_quality not in valid_video_qualities:
        errors.append(f"视频质量选项无效，可选值: {valid_video_qualities}")

    if errors:
        print("配置验证失败:")
        for error in errors:
            print(f"  - {error}")
        return False

    return True


def get_base_dir() -> str:
    """获取项目根目录"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_absolute_path(relative_path: str) -> str:
    """将相对路径转换为绝对路径"""
    return os.path.join(get_base_dir(), relative_path)