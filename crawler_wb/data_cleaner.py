# -*- coding: utf-8 -*-
"""
数据清洗模块
处理时间格式转换、文本清理等
"""

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple


class DataCleaner:
    """数据清洗器"""

    def __init__(self, current_time: datetime = None):
        """
        初始化数据清洗器

        Args:
            current_time: 当前时间，用于计算相对时间
        """
        self.current_time = current_time or datetime.now()

    def clean_time(self, time_str: str) -> Optional[datetime]:
        """
        清洗并转换时间字符串

        支持的格式：
        - "47秒前" -> 计算实际时间
        - "57分钟前" -> 计算实际时间
        - "今天08:45" -> 当天时间
        - "06月30日 15:36" -> 当年日期
        - "2020年06月29日 22:51" -> 完整日期
        - "2024-06-13 08:45:00" -> 标准格式

        Args:
            time_str: 时间字符串

        Returns:
            datetime对象，解析失败返回None
        """
        if not time_str:
            return None

        time_str = time_str.strip()

        try:
            # 处理 "X秒前"
            match = re.match(r'(\d+)秒前', time_str)
            if match:
                seconds = int(match.group(1))
                return self.current_time - timedelta(seconds=seconds)

            # 处理 "X分钟前"
            match = re.match(r'(\d+)分钟前', time_str)
            if match:
                minutes = int(match.group(1))
                return self.current_time - timedelta(minutes=minutes)

            # 处理 "X小时前"
            match = re.match(r'(\d+)小时前', time_str)
            if match:
                hours = int(match.group(1))
                return self.current_time - timedelta(hours=hours)

            # 处理 "今天HH:MM"
            match = re.match(r'今天(\d{2}):(\d{2})', time_str)
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2))
                return self.current_time.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # 处理 "昨天HH:MM"
            match = re.match(r'昨天(\d{2}):(\d{2})', time_str)
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2))
                yesterday = self.current_time - timedelta(days=1)
                return yesterday.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # 处理 "MM月DD日 HH:MM"
            match = re.match(r'(\d{2})月(\d{2})日\s+(\d{2}):(\d{2})', time_str)
            if match:
                month = int(match.group(1))
                day = int(match.group(2))
                hour = int(match.group(3))
                minute = int(match.group(4))
                return datetime(self.current_time.year, month, day, hour, minute)

            # 处理 "YYYY年MM月DD日 HH:MM"
            match = re.match(r'(\d{4})年(\d{2})月(\d{2})日\s+(\d{2}):(\d{2})', time_str)
            if match:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))
                hour = int(match.group(4))
                minute = int(match.group(5))
                return datetime(year, month, day, hour, minute)

            # 处理标准格式 "YYYY-MM-DD HH:MM:SS"
            match = re.match(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})', time_str)
            if match:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))
                hour = int(match.group(4))
                minute = int(match.group(5))
                second = int(match.group(6))
                return datetime(year, month, day, hour, minute, second)

            # 处理标准格式 "YYYY-MM-DD HH:MM"
            match = re.match(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})', time_str)
            if match:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))
                hour = int(match.group(4))
                minute = int(match.group(5))
                return datetime(year, month, day, hour, minute)

        except (ValueError, AttributeError):
            pass

        return None

    def is_time_in_range(self, dt: datetime, start: datetime, end: datetime) -> bool:
        """
        检查时间是否在指定范围内

        Args:
            dt: 要检查的时间
            start: 开始时间
            end: 结束时间

        Returns:
            是否在范围内
        """
        if dt is None:
            return False
        return start <= dt <= end

    def clean_content(self, content: str) -> str:
        """
        清洗微博内容

        Args:
            content: 原始内容

        Returns:
            清洗后的内容
        """
        if not content:
            return ""

        # 移除HTML标签
        content = re.sub(r'<[^>]+>', '', content)

        # 移除emoji标签（如 [微笑]）
        # content = re.sub(r'\[[一-龥]+\]', '', content)

        # 移除话题标签的井号（保留话题内容）
        # content = re.sub(r'#([^#]+)#', r'\1', content)

        # 移除@用户的链接
        content = re.sub(r'<a[^>]*href=["\'].*?weibo\.cn/[^"\']*["\'][^>]*>@([^<]+)</a>', r'@\1', content)

        # 移除多余的空白
        content = re.sub(r'\s+', ' ', content)

        # 移除首尾空白
        content = content.strip()

        return content

    def clean_author_name(self, name: str) -> str:
        """
        清洗作者名称

        Args:
            name: 原始名称

        Returns:
            清洗后的名称
        """
        if not name:
            return ""

        # 移除HTML标签
        name = re.sub(r'<[^>]+>', '', name)

        # 移除特殊字符
        name = re.sub(r'[\r\n\t]', '', name)

        # 移除首尾空白
        name = name.strip()

        return name

    def extract_location(self, text: str) -> Optional[str]:
        """
        从文本中提取位置信息

        Args:
            text: 包含位置信息的文本

        Returns:
            位置字符串
        """
        if not text:
            return None

        # 匹配 "来自 iPhone客户端·北京" 或 "来自 北京"
        match = re.search(r'来自\s*(?:.*?·)?([^·\s]+)$', text)
        if match:
            return match.group(1)

        return None

    def clean_numbers(self, num_str: str) -> int:
        """
        清洗数字字符串

        Args:
            num_str: 数字字符串（可能包含"万"等单位）

        Returns:
            整数
        """
        if not num_str:
            return 0

        num_str = num_str.strip()

        try:
            # 处理 "1.2万" 格式
            if '万' in num_str:
                num_str = num_str.replace('万', '')
                return int(float(num_str) * 10000)

            # 处理普通数字
            return int(num_str)
        except ValueError:
            return 0

    def format_datetime(self, dt: datetime, fmt: str = '%Y-%m-%d %H:%M:%S') -> str:
        """
        格式化datetime为字符串

        Args:
            dt: datetime对象
            fmt: 格式字符串

        Returns:
            格式化后的字符串
        """
        if dt is None:
            return ""
        return dt.strftime(fmt)

    def clean_weibo_data(self, data: dict) -> dict:
        """
        清洗完整的微博数据

        Args:
            data: 原始数据字典

        Returns:
            清洗后的数据字典
        """
        cleaned = {}

        # 清洗作者
        cleaned['author'] = self.clean_author_name(data.get('author', ''))

        # 清洗内容
        cleaned['content'] = self.clean_content(data.get('content', ''))

        # 清洗时间
        time_str = data.get('publish_time', '')
        dt = self.clean_time(time_str)
        cleaned['publish_time'] = self.format_datetime(dt) if dt else time_str

        # 清洗位置
        cleaned['location'] = self.clean_author_name(data.get('location', ''))

        # 清洗数字
        cleaned['reposts_count'] = self.clean_numbers(data.get('reposts_count', '0'))
        cleaned['comments_count'] = self.clean_numbers(data.get('comments_count', '0'))
        cleaned['likes_count'] = self.clean_numbers(data.get('likes_count', '0'))

        # 保留其他字段
        for key in ['weibo_id', 'author_id', 'images', 'video', 'comments', 'crawl_time']:
            if key in data:
                cleaned[key] = data[key]

        return cleaned
