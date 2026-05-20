# -*- coding: utf-8 -*-
"""
媒体下载器模块
下载微博中的图片和视频
"""

import os
import re
import json
import time
import requests
from typing import List, Optional, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .utils import get_random_delay, get_random_user_agent, ensure_dir


@dataclass
class DownloadResult:
    """下载结果"""
    success: bool
    filepath: str
    error: str = ""


class MediaDownloader:
    """媒体下载器"""

    # 图片服务器域名
    IMAGE_DOMAINS = [
        'wx1.sinaimg.cn',
        'wx2.sinaimg.cn',
        'wx3.sinaimg.cn',
        'wx4.sinaimg.cn',
    ]

    def __init__(self, image_dir: str, video_dir: str, max_workers: int = 5, timeout: int = 30):
        """
        初始化媒体下载器

        Args:
            image_dir: 图片存储目录
            video_dir: 视频存储目录
            max_workers: 最大并发线程数
            timeout: 下载超时时间（秒）
        """
        self.image_dir = image_dir
        self.video_dir = video_dir
        self.max_workers = max_workers
        self.timeout = timeout

        # 确保目录存在
        ensure_dir(image_dir)
        ensure_dir(video_dir)

        # 下载错误记录
        self.errors: List[Dict] = []

    def _get_headers(self, cookie: str = None) -> Dict[str, str]:
        """获取请求头"""
        headers = {
            'User-Agent': get_random_user_agent(),
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://weibo.com/',
        }
        if cookie:
            headers['Cookie'] = cookie
        return headers

    def download_image(self, pic_id: str, weibo_id: str, cookie: str = None) -> DownloadResult:
        """
        下载单张图片

        Args:
            pic_id: 图片ID
            weibo_id: 微博ID（用于创建文件夹）
            cookie: Cookie字符串

        Returns:
            DownloadResult对象
        """
        # 创建微博专属文件夹
        weibo_image_dir = os.path.join(self.image_dir, weibo_id)
        ensure_dir(weibo_image_dir)

        # 尝试不同的图片格式和服务器
        extensions = ['.jpg', '.png', '.jpeg', '.gif']

        for domain in self.IMAGE_DOMAINS:
            for ext in extensions:
                url = f"https://{domain}/large/{pic_id}{ext}"
                filepath = os.path.join(weibo_image_dir, f"{pic_id}{ext}")

                # 如果文件已存在，跳过
                if os.path.exists(filepath):
                    return DownloadResult(success=True, filepath=filepath)

                try:
                    headers = self._get_headers(cookie)
                    response = requests.get(url, headers=headers, timeout=self.timeout, stream=True)

                    if response.status_code == 200:
                        with open(filepath, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        return DownloadResult(success=True, filepath=filepath)

                except requests.RequestException as e:
                    continue

        # 所有尝试都失败
        error_msg = f"图片下载失败: {pic_id}"
        self.errors.append({'type': 'image', 'pic_id': pic_id, 'weibo_id': weibo_id, 'error': error_msg})
        return DownloadResult(success=False, filepath="", error=error_msg)

    def download_images(self, pic_ids: List[str], weibo_id: str, cookie: str = None) -> List[DownloadResult]:
        """
        批量下载图片

        Args:
            pic_ids: 图片ID列表
            weibo_id: 微博ID
            cookie: Cookie字符串

        Returns:
            下载结果列表
        """
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.download_image, pic_id, weibo_id, cookie): pic_id
                for pic_id in pic_ids
            }

            for future in as_completed(futures):
                result = future.result()
                results.append(result)

                # 添加随机延迟
                time.sleep(get_random_delay(0.5, 1.5))

        return results

    def get_video_info(self, weibo_id: str, cookie: str = None) -> Optional[Dict]:
        """
        获取视频信息

        Args:
            weibo_id: 微博ID
            cookie: Cookie字符串

        Returns:
            视频信息字典，包含不同分辨率的URL
        """
        # 通过微博详情页获取视频信息
        detail_url = f"https://m.weibo.cn/detail/{weibo_id}"

        headers = {
            'User-Agent': get_random_user_agent(),
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://m.weibo.cn/',
        }
        if cookie:
            headers['Cookie'] = cookie

        try:
            response = requests.get(detail_url, headers=headers, timeout=self.timeout)
            if response.status_code != 200:
                return None

            # 从页面中提取视频信息
            text = response.text

            # 尝试从JSON数据中提取
            match = re.search(r'"page_info":\s*\{[^}]*"media_info":\s*\{([^}]+)\}', text)
            if match:
                media_info_str = match.group(1)
                # 提取视频URL
                video_urls = {}

                # 匹配不同分辨率的URL
                for quality in ['stream_url_hd', 'stream_url', 'stream_url_mp4']:
                    url_match = re.search(f'"{quality}":\\s*"([^"]+)"', media_info_str)
                    if url_match:
                        video_urls[quality] = url_match.group(1)

                if video_urls:
                    return video_urls

            # 尝试另一种方式：通过微博视频API
            video_id_match = re.search(r'"object_id":\s*"([^"]+)"', text)
            if video_id_match:
                video_id = video_id_match.group(1)
                return self._get_video_from_api(video_id, cookie)

        except requests.RequestException:
            pass

        return None

    def _get_video_from_api(self, video_id: str, cookie: str = None) -> Optional[Dict]:
        """
        通过API获取视频信息

        Args:
            video_id: 视频ID
            cookie: Cookie字符串

        Returns:
            视频信息字典
        """
        api_url = f"https://weibo.com/tv/api/component?page=/tv/show/{video_id}"

        headers = {
            'User-Agent': get_random_user_agent(),
            'Accept': 'application/json',
            'Referer': f'https://weibo.com/tv/show/{video_id}',
            'X-Requested-With': 'XMLHttpRequest',
        }
        if cookie:
            headers['Cookie'] = cookie

        try:
            response = requests.post(api_url, headers=headers, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 200:
                    return data.get('data', {})
        except (requests.RequestException, json.JSONDecodeError):
            pass

        return None

    def download_video(self, weibo_id: str, cookie: str = None, prefer_quality: str = 'hd') -> DownloadResult:
        """
        下载视频

        Args:
            weibo_id: 微博ID
            cookie: Cookie字符串
            prefer_quality: 优先下载的画质 ('hd', 'sd', 'mp4')

        Returns:
            DownloadResult对象
        """
        # 创建微博专属文件夹
        weibo_video_dir = os.path.join(self.video_dir, weibo_id)
        ensure_dir(weibo_video_dir)

        # 获取视频信息
        video_info = self.get_video_info(weibo_id, cookie)
        if not video_info:
            error_msg = f"无法获取视频信息: {weibo_id}"
            self.errors.append({'type': 'video', 'weibo_id': weibo_id, 'error': error_msg})
            return DownloadResult(success=False, filepath="", error=error_msg)

        # 按优先级选择视频URL
        quality_priority = ['stream_url_hd', 'stream_url', 'stream_url_mp4']
        if prefer_quality == 'sd':
            quality_priority = ['stream_url', 'stream_url_mp4', 'stream_url_hd']

        video_url = None
        selected_quality = None

        for quality in quality_priority:
            if quality in video_info and video_info[quality]:
                video_url = video_info[quality]
                selected_quality = quality
                break

        if not video_url:
            error_msg = f"未找到可用的视频URL: {weibo_id}"
            self.errors.append({'type': 'video', 'weibo_id': weibo_id, 'error': error_msg})
            return DownloadResult(success=False, filepath="", error=error_msg)

        # 下载视频
        filepath = os.path.join(weibo_video_dir, f"{selected_quality}.mp4")

        # 如果文件已存在，跳过
        if os.path.exists(filepath):
            return DownloadResult(success=True, filepath=filepath)

        try:
            headers = self._get_headers(cookie)
            response = requests.get(video_url, headers=headers, timeout=self.timeout * 3, stream=True)

            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                return DownloadResult(success=True, filepath=filepath)

        except requests.RequestException as e:
            error_msg = f"视频下载失败: {weibo_id}, 错误: {str(e)}"
            self.errors.append({'type': 'video', 'weibo_id': weibo_id, 'error': error_msg})
            return DownloadResult(success=False, filepath="", error=error_msg)

        error_msg = f"视频下载失败: {weibo_id}, 状态码: {response.status_code}"
        self.errors.append({'type': 'video', 'weibo_id': weibo_id, 'error': error_msg})
        return DownloadResult(success=False, filepath="", error=error_msg)

    def get_pic_ids_from_weibo(self, weibo_id: str, cookie: str = None) -> List[str]:
        """
        从微博详情页获取图片ID列表

        Args:
            weibo_id: 微博ID
            cookie: Cookie字符串

        Returns:
            图片ID列表
        """
        detail_url = f"https://m.weibo.cn/detail/{weibo_id}"

        headers = {
            'User-Agent': get_random_user_agent(),
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://m.weibo.cn/',
        }
        if cookie:
            headers['Cookie'] = cookie

        try:
            response = requests.get(detail_url, headers=headers, timeout=self.timeout)
            if response.status_code != 200:
                return []

            text = response.text

            # 提取pic_ids
            match = re.search(r'"pic_ids":\s*\[([^\]]+)\]', text)
            if match:
                ids_str = match.group(1)
                # 解析JSON数组
                pic_ids = re.findall(r'"([^"]+)"', ids_str)
                return pic_ids

        except requests.RequestException:
            pass

        return []

    def download_all_media(self, weibo_id: str, cookie: str = None, has_images: bool = True, has_video: bool = False) -> Dict:
        """
        下载微博的所有媒体内容

        Args:
            weibo_id: 微博ID
            cookie: Cookie字符串
            has_images: 是否有图片
            has_video: 是否有视频

        Returns:
            下载结果字典
        """
        result = {
            'images': [],
            'video': None,
        }

        if has_images:
            # 获取图片ID
            pic_ids = self.get_pic_ids_from_weibo(weibo_id, cookie)
            if pic_ids:
                # 下载图片
                image_results = self.download_images(pic_ids, weibo_id, cookie)
                result['images'] = [r.filepath for r in image_results if r.success]

        if has_video:
            # 下载视频
            video_result = self.download_video(weibo_id, cookie)
            if video_result.success:
                result['video'] = video_result.filepath

        return result

    def get_errors(self) -> List[Dict]:
        """获取下载错误列表"""
        return self.errors

    def clear_errors(self) -> None:
        """清空错误列表"""
        self.errors = []

    def save_error_log(self, filepath: str) -> bool:
        """
        保存错误日志

        Args:
            filepath: 日志文件路径

        Returns:
            是否保存成功
        """
        if not self.errors:
            return True

        try:
            ensure_dir(os.path.dirname(filepath))
            with open(filepath, 'w', encoding='utf-8') as f:
                for error in self.errors:
                    f.write(f"{error}\n")
            return True
        except Exception:
            return False