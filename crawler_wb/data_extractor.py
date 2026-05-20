# -*- coding: utf-8 -*-
"""
数据提取器模块
从微博搜索页面提取博文数据
"""

import re
import json
import requests
from typing import List, Optional, Dict, Any
from datetime import datetime
from bs4 import BeautifulSoup

from .utils import get_request_headers
from .data_cleaner import DataCleaner


class WeiboExtractor:
    """微博数据提取器"""

    def __init__(self, timeout: int = 30):
        """
        初始化提取器

        Args:
            timeout: 请求超时时间（秒）
        """
        self.timeout = timeout
        self.cleaner = DataCleaner()

    def fetch_page(self, url: str, cookie: str) -> Optional[str]:
        """
        获取页面内容

        Args:
            url: 页面URL
            cookie: Cookie字符串

        Returns:
            页面HTML内容，失败返回None
        """
        headers = get_request_headers(cookie)

        try:
            response = requests.get(url, headers=headers, timeout=self.timeout)
            if response.status_code == 200:
                return response.text
        except requests.RequestException:
            pass

        return None

    def get_page_count(self, html: str) -> int:
        """
        获取搜索结果的总页数

        Args:
            html: 页面HTML

        Returns:
            总页数
        """
        if not html:
            return 0

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # 查找分页信息 - 多种选择器尝试
            selectors = [
                'ul.s-scroll li a[href*="page="]',
                '.s-pagination a[href*="page="]',
                '.page a[href*="page="]',
                'a[href*="page="]',
            ]

            for selector in selectors:
                page_links = soup.select(selector)
                if page_links:
                    max_page = 1
                    for link in page_links:
                        href = link.get('href', '')
                        match = re.search(r'page=(\d+)', href)
                        if match:
                            page_num = int(match.group(1))
                            max_page = max(max_page, page_num)
                    if max_page > 1:
                        return max_page

            # 如果没有找到分页，检查是否有结果
            cards = soup.select('.card-wrap[action-type="feed_list_item"]')
            if cards:
                return 50  # 默认50页

        except Exception:
            pass

        return 0

    def extract_weibo_list(self, html: str) -> List[Dict[str, Any]]:
        """
        从页面中提取微博列表

        Args:
            html: 页面HTML

        Returns:
            微博数据列表
        """
        if not html:
            return []

        weibo_list = []

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # 查找所有微博卡片 - 使用更精确的选择器
            cards = soup.select('.card-wrap[action-type="feed_list_item"]')

            print(f"找到 {len(cards)} 个微博卡片")

            for card in cards:
                weibo_data = self._extract_single_weibo(card)
                if weibo_data and weibo_data.get('weibo_id'):
                    weibo_list.append(weibo_data)

        except Exception as e:
            print(f"解析页面失败: {e}")

        return weibo_list

    def _extract_single_weibo(self, card) -> Optional[Dict[str, Any]]:
        """
        从单个卡片中提取微博信息

        Args:
            card: BeautifulSoup元素

        Returns:
            微博数据字典
        """
        try:
            weibo_data = {}

            # 提取微博ID - 从mid属性
            mid = card.get('mid', '')
            if mid:
                weibo_data['weibo_id'] = mid
            else:
                # 尝试从action-data提取
                action_data = card.get('action-data', '')
                mid_match = re.search(r'mid=(\d+)', action_data)
                if mid_match:
                    weibo_data['weibo_id'] = mid_match.group(1)

            if not weibo_data.get('weibo_id'):
                return None

            # 提取作者信息 - 从.name类
            author_elem = card.select_one('.name')
            if author_elem:
                weibo_data['author'] = author_elem.get_text(strip=True)
                # 提取作者ID
                author_link = author_elem.get('href', '')
                author_id_match = re.search(r'/u/(\d+)', author_link) or re.search(r'/(\d+)[?/]', author_link)
                if author_id_match:
                    weibo_data['author_id'] = author_id_match.group(1)
            else:
                weibo_data['author'] = ''

            # 提取微博内容 - 从.txt[node-type="feed_list_content"]
            content_elem = card.select_one('.txt[node-type="feed_list_content"]')
            if content_elem:
                # 获取完整文本，包括链接中的话题
                content_text = content_elem.get_text(separator=' ', strip=True)
                weibo_data['content'] = self.cleaner.clean_content(content_text)
            else:
                # 备用选择器
                content_elem = card.select_one('.txt')
                if content_elem:
                    weibo_data['content'] = self.cleaner.clean_content(content_elem.get_text(strip=True))
                else:
                    weibo_data['content'] = ''

            # 提取发布时间 - 从.from中的第一个链接
            from_elem = card.select_one('.from')
            if from_elem:
                time_link = from_elem.select_one('a')
                if time_link:
                    weibo_data['publish_time'] = time_link.get_text(strip=True)
                else:
                    weibo_data['publish_time'] = ''

                # 提取来源（如"来自 微博网页版"）
                source_links = from_elem.select('a')
                if len(source_links) > 1:
                    weibo_data['source'] = source_links[-1].get_text(strip=True)
            else:
                weibo_data['publish_time'] = ''

            # 提取互动数据（转发、评论、点赞）- 从.card-act
            act_elem = card.select_one('.card-act')
            if act_elem:
                # 查找所有链接
                act_links = act_elem.select('a')

                for link in act_links:
                    link_text = link.get_text(strip=True)
                    action_type = link.get('action-type', '')

                    # 转发
                    if '转发' in link_text or action_type == 'feed_list_forward':
                        count_match = re.search(r'(\d+)', link_text)
                        weibo_data['reposts_count'] = count_match.group(1) if count_match else '0'

                    # 评论
                    elif '评论' in link_text or action_type == 'feed_list_comment':
                        count_match = re.search(r'(\d+)', link_text)
                        weibo_data['comments_count'] = count_match.group(1) if count_match else '0'

                    # 点赞
                    elif '赞' in link_text or action_type == 'feed_list_like':
                        count_match = re.search(r'(\d+)', link_text)
                        weibo_data['likes_count'] = count_match.group(1) if count_match else '0'

            # 设置默认值
            weibo_data.setdefault('reposts_count', '0')
            weibo_data.setdefault('comments_count', '0')
            weibo_data.setdefault('likes_count', '0')

            # 检查是否有图片
            has_images = False
            # 检查多种图片容器
            pic_selectors = [
                '.card-pic',
                '.media-wrap img',
                '.pic-list',
                'img[src*="sinaimg"]',
            ]
            for selector in pic_selectors:
                if card.select_one(selector):
                    has_images = True
                    break
            weibo_data['has_images'] = has_images

            # 检查是否有视频
            has_video = False
            video_selectors = [
                '.card-video',
                '.media-wrap video',
                '[node-type="feed_list_media_video"]',
                'a[href*="weibo.com/tv"]',
            ]
            for selector in video_selectors:
                if card.select_one(selector):
                    has_video = True
                    break
            weibo_data['has_video'] = has_video

            # 添加爬取时间
            weibo_data['crawl_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            return weibo_data

        except Exception as e:
            print(f"提取微博失败: {e}")
            return None

    def extract_comments(self, weibo_id: str, cookie: str, max_count: int = 50) -> List[Dict]:
        """
        获取微博评论

        Args:
            weibo_id: 微博ID
            cookie: Cookie字符串
            max_count: 最大获取数量

        Returns:
            评论列表
        """
        comments = []

        # 微博移动端评论API
        api_url = f"https://m.weibo.cn/comments/hotflow?id={weibo_id}&mid={weibo_id}&max_id_type=0"

        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
            'Accept': 'application/json, text/plain, */*',
            'Referer': f'https://m.weibo.cn/detail/{weibo_id}',
            'Cookie': cookie,
        }

        try:
            response = requests.get(api_url, headers=headers, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                if data.get('ok') == 1:
                    comment_data = data.get('data', {}).get('data', [])
                    for item in comment_data[:max_count]:
                        comment = {
                            'id': item.get('id', ''),
                            'text': self.cleaner.clean_content(item.get('text', '')),
                            'like_count': item.get('like_count', 0),
                            'user_name': item.get('user', {}).get('screen_name', ''),
                            'user_id': item.get('user', {}).get('id', ''),
                            'created_at': item.get('created_at', ''),
                        }
                        comments.append(comment)

        except (requests.RequestException, json.JSONDecodeError):
            pass

        return comments

    def is_cookie_valid(self, html: str) -> bool:
        """
        检查Cookie是否有效

        Args:
            html: 页面HTML

        Returns:
            Cookie是否有效
        """
        if not html:
            return False

        # 检查是否被重定向到登录页或验证页
        if 'login.sina' in html or '请登录' in html or '登录微博' in html:
            return False

        # 检查是否是新浪通行证验证页面（retcode=6102等）
        if 'retcode=' in html or '新浪通行证' in html or '通行证' in html:
            return False

        # 检查是否有搜索结果容器
        if 'card-wrap' in html or 'pl-weibo-search' in html:
            return True

        return False

    def has_results(self, html: str) -> bool:
        """
        检查页面是否有搜索结果

        Args:
            html: 页面HTML

        Returns:
            是否有结果
        """
        if not html:
            return False

        # 检查是否有"没有找到相关结果"的提示
        if '没有找到相关结果' in html or '抱歉，未找到' in html:
            return False

        # 检查是否有微博卡片
        soup = BeautifulSoup(html, 'html.parser')
        cards = soup.select('.card-wrap[action-type="feed_list_item"]')
        return len(cards) > 0