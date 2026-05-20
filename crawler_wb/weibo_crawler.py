# -*- coding: utf-8 -*-
"""
微博爬虫主模块
协调各模块完成数据爬取任务
"""

import os
import sys
import time
import re
import argparse
import json
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler_wb.config import load_config, validate_config, Config, get_absolute_path
from crawler_wb.cookie_manager import CookieManager
from crawler_wb.data_extractor import WeiboExtractor
from crawler_wb.media_downloader import MediaDownloader
from crawler_wb.data_cleaner import DataCleaner
from crawler_wb.utils import (
    setup_logger,
    generate_time_windows,
    build_search_url,
    get_random_delay,
    save_json,
    load_json,
    format_time_for_display,
    format_time_for_url,
    ensure_dir,
)


class WeiboCrawler:
    """微博爬虫主类"""

    def __init__(self, config: Config):
        """
        初始化爬虫

        Args:
            config: 配置对象
        """
        self.config = config

        # 初始化各模块
        self.cookie_manager = CookieManager(
            cookie_file=get_absolute_path(config.cookie_file),
            max_fail_count=config.cookie_manager.max_fail_count
        )
        self.extractor = WeiboExtractor(timeout=config.crawler.timeout)
        self.downloader = MediaDownloader(
            image_dir=get_absolute_path(config.storage.image_dir),
            video_dir=get_absolute_path(config.storage.video_dir),
            max_workers=config.crawler.max_workers,
            timeout=config.crawler.timeout,
        )
        self.cleaner = DataCleaner()

        # 设置日志
        log_file = os.path.join(
            get_absolute_path(config.storage.log_dir),
            f"crawler_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        self.logger = setup_logger('WeiboCrawler', log_file)

        # 进度文件
        self.progress_file = os.path.join(
            get_absolute_path(config.storage.log_dir),
            'progress.json'
        )
        self.failed_pages_file = os.path.join(
            get_absolute_path(config.storage.log_dir),
            'failed_pages.json'
        )

        # 确保目录存在
        ensure_dir(get_absolute_path(config.storage.text_dir))
        ensure_dir(get_absolute_path(config.storage.log_dir))

        # 加载进度（页面级别）
        self.progress = self._load_progress()

        # 加载失败页面记录
        self.failed_pages = self._load_failed_pages()

        # 统计信息
        self.stats = {
            'total_weibos': 0,
            'total_images': 0,
            'total_videos': 0,
            'failed_requests': 0,
            'failed_downloads': 0,
        }

    def _load_progress(self) -> Dict[str, Dict[str, List[int]]]:
        """
        加载页面级别的爬取进度

        Returns:
            进度字典，格式为 {keyword: {window_key: [completed_pages]}}
        """
        if not os.path.exists(self.progress_file):
            return {}

        data = load_json(self.progress_file)
        return data if data else {}

    def _save_progress(self) -> bool:
        """
        保存页面级别的爬取进度

        Returns:
            是否保存成功
        """
        return save_json(self.progress, self.progress_file)

    def _load_failed_pages(self) -> Dict[str, Dict[str, Dict[int, Dict]]]:
        """
        加载失败页面记录

        Returns:
            失败页面字典，格式为 {keyword: {window_key: {page: {error_info}}}}
        """
        if not os.path.exists(self.failed_pages_file):
            return {}

        data = load_json(self.failed_pages_file)
        return data if data else {}

    def _save_failed_pages(self) -> bool:
        """
        保存失败页面记录

        Returns:
            是否保存成功
        """
        return save_json(self.failed_pages, self.failed_pages_file)

    def _get_completed_pages(self, keyword: str, window_key: str) -> List[int]:
        """
        获取指定时间窗口已完成的页码列表

        Args:
            keyword: 关键词
            window_key: 时间窗口标识

        Returns:
            已完成的页码列表
        """
        if keyword not in self.progress:
            return []
        if window_key not in self.progress[keyword]:
            return []
        return self.progress[keyword][window_key]

    def _mark_page_completed(self, keyword: str, window_key: str, page: int) -> None:
        """
        标记页面为已完成

        Args:
            keyword: 关键词
            window_key: 时间窗口标识
            page: 页码
        """
        if keyword not in self.progress:
            self.progress[keyword] = {}
        if window_key not in self.progress[keyword]:
            self.progress[keyword][window_key] = []

        if page not in self.progress[keyword][window_key]:
            self.progress[keyword][window_key].append(page)
            self._save_progress()

    def _mark_page_failed(self, keyword: str, window_key: str, page: int, error_info: Dict) -> None:
        """
        标记页面为失败，记录失败信息

        Args:
            keyword: 关键词
            window_key: 时间窗口标识
            page: 页码
            error_info: 错误信息字典
        """
        if keyword not in self.failed_pages:
            self.failed_pages[keyword] = {}
        if window_key not in self.failed_pages[keyword]:
            self.failed_pages[keyword][window_key] = {}

        # 记录失败次数和时间
        if page not in self.failed_pages[keyword][window_key]:
            self.failed_pages[keyword][window_key][page] = {
                'fail_count': 1,
                'first_fail_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'last_fail_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'errors': [error_info]
            }
        else:
            self.failed_pages[keyword][window_key][page]['fail_count'] += 1
            self.failed_pages[keyword][window_key][page]['last_fail_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.failed_pages[keyword][window_key][page]['errors'].append(error_info)

        self._save_failed_pages()

    def _remove_failed_page(self, keyword: str, window_key: str, page: int) -> None:
        """
        从失败记录中移除页面（成功爬取后）

        Args:
            keyword: 关键词
            window_key: 时间窗口标识
            page: 页码
        """
        if keyword in self.failed_pages and window_key in self.failed_pages[keyword]:
            if page in self.failed_pages[keyword][window_key]:
                del self.failed_pages[keyword][window_key][page]
                self._save_failed_pages()

    def _is_window_completed(self, keyword: str, window_key: str, total_pages: int) -> bool:
        """
        检查时间窗口是否全部完成

        Args:
            keyword: 关键词
            window_key: 时间窗口标识
            total_pages: 总页数

        Returns:
            是否全部完成
        """
        completed_pages = self._get_completed_pages(keyword, window_key)
        # 检查是否所有页面都已完成（考虑最大页数限制10页）
        max_pages = min(total_pages, 10) if total_pages > 0 else 10
        return len(completed_pages) >= max_pages and all(p in completed_pages for p in range(1, max_pages + 1))

    def run(self, start_date: str = None, end_date: str = None) -> None:
        """
        运行爬虫

        Args:
            start_date: 开始时间（可选，覆盖配置）
            end_date: 结束时间（可选，覆盖配置）
        """
        self.logger.info("微博爬虫启动")

        # 打印模态数据保存配置
        self.logger.info(f"保存文本: {self.config.modalities.save_text}")
        self.logger.info(f"保存图片: {self.config.modalities.save_images}")
        self.logger.info(f"保存视频: {self.config.modalities.save_videos}")

        # 使用传入的时间或配置中的时间
        start = start_date or self.config.time.start_date
        end = end_date or self.config.time.end_date

        # 生成时间窗口（小时级别）
        time_windows = generate_time_windows(start, end)
        self.logger.info(f"时间范围: {start} - {end}")
        self.logger.info(f"时间窗口数量: {len(time_windows)} (小时级别)")
        self.logger.info(f"关键词数量: {len(self.config.keywords)}")

        # 检查Cookie
        if self.cookie_manager.get_valid_count() == 0:
            self.logger.error("没有有效的Cookie，请检查配置")
            return

        # 遍历关键词和时间窗口
        for keyword in self.config.keywords:
            self.logger.info(f"开始爬取关键词: {keyword}")

            for window_start, window_end in time_windows:
                window_key = f"{keyword}_{format_time_for_url(window_start)}_{format_time_for_url(window_end)}"

                # 检查是否有失败页面需要重试
                failed_pages_in_window = []
                if keyword in self.failed_pages and window_key in self.failed_pages[keyword]:
                    failed_pages_in_window = list(self.failed_pages[keyword][window_key].keys())
                    if failed_pages_in_window:
                        self.logger.info(f"发现 {len(failed_pages_in_window)} 个失败页面需要重试: {failed_pages_in_window}")

                self.logger.info(f"爬取时间窗口: {format_time_for_display(window_start)} - {format_time_for_display(window_end)}")

                try:
                    # 爬取该时间窗口的数据（数据已在方法内实时保存）
                    weibos = self._crawl_time_window(keyword, window_start, window_end)

                    if weibos is not None:
                        self.logger.info(f"时间窗口完成，获取 {len(weibos)} 条微博")

                    # 添加延迟
                    delay = get_random_delay(
                        self.config.crawler.request_delay_min,
                        self.config.crawler.request_delay_max
                    )
                    time.sleep(delay)

                except Exception as e:
                    self.logger.error(f"爬取时间窗口失败: {window_key}, 错误: {e}")
                    self.stats['failed_requests'] += 1

        # 输出统计信息
        self._print_stats()

        # 保存错误日志
        self._save_error_logs()

        self.logger.info("爬虫完成")

    def _crawl_time_window(self, keyword: str, window_start: datetime, window_end: datetime) -> List[Dict]:
        """
        爬取指定时间窗口的数据

        Args:
            keyword: 关键词
            window_start: 开始时间
            window_end: 结束时间

        Returns:
            微博列表
        """
        all_weibos = []
        window_key = f"{keyword}_{format_time_for_url(window_start)}_{format_time_for_url(window_end)}"

        # 准备保存文件路径
        filename = f"{keyword}_{format_time_for_url(window_start)}_{format_time_for_url(window_end)}.json"
        filepath = os.path.join(get_absolute_path(self.config.storage.text_dir), filename)

        # 如果文件已存在，加载已有数据（支持断点续爬）
        if os.path.exists(filepath):
            existing_data = load_json(filepath)
            if existing_data:
                all_weibos = existing_data
                self.logger.info(f"加载已有数据: {len(all_weibos)} 条微博")

        # 获取已完成的页码和需要重试的失败页面
        completed_pages = self._get_completed_pages(keyword, window_key)
        failed_pages_to_retry = []
        if keyword in self.failed_pages and window_key in self.failed_pages[keyword]:
            failed_pages_to_retry = list(self.failed_pages[keyword][window_key].keys())

        # 如果有失败页面需要重试，先处理失败页面
        if failed_pages_to_retry:
            for retry_page in sorted(failed_pages_to_retry):
                self.logger.info(f"重试失败页面: 第{retry_page}页")
                # 这里单独处理重试页面，成功后会从失败记录中移除

        # 确定起始页码
        if completed_pages:
            start_page = max(completed_pages) + 1
        else:
            start_page = 1

        total_pages = 0
        max_pages = 10
        page = start_page

        while True:
            # 获取Cookie
            cookie = self.cookie_manager.get_cookie()
            if not cookie:
                self.logger.error("没有可用的Cookie")
                # 记录失败
                self._mark_page_failed(keyword, window_key, page, {
                    'error_type': 'no_cookie',
                    'message': '没有可用的Cookie'
                })
                break

            # 构建URL
            url = build_search_url(keyword, window_start, window_end, page)

            self.logger.debug(f"请求URL: {url}")

            # 获取页面
            html = self.extractor.fetch_page(url, cookie)

            if not html:
                self.logger.warning(f"获取页面失败: 第{page}页")
                self.cookie_manager.report_failure(cookie)
                self.stats['failed_requests'] += 1

                # 记录失败
                self._mark_page_failed(keyword, window_key, page, {
                    'error_type': 'fetch_failed',
                    'message': '获取页面失败'
                })

                # 尝试下一个Cookie
                if self.cookie_manager.get_valid_count() > 0:
                    continue
                else:
                    break

            # 检查Cookie是否有效
            if not self.extractor.is_cookie_valid(html):
                self.logger.warning(f"Cookie无效")
                self.cookie_manager.report_failure(cookie)

                # 记录失败
                self._mark_page_failed(keyword, window_key, page, {
                    'error_type': 'cookie_invalid',
                    'message': 'Cookie无效'
                })
                continue

            self.cookie_manager.report_success(cookie)

            # 起始页获取总页数
            if page == start_page:
                total_pages = self.extractor.get_page_count(html)
                self.logger.info(f"总页数: {total_pages}")

                if total_pages == 0:
                    self.logger.info("没有搜索结果")
                    # 标记当前页完成（无结果也算完成）
                    self._mark_page_completed(keyword, window_key, page)
                    break

            # 检查是否有结果
            if not self.extractor.has_results(html):
                self.logger.info(f"第{page}页没有结果")
                # 标记页面完成
                self._mark_page_completed(keyword, window_key, page)
                break

            # 提取微博数据
            weibos = self.extractor.extract_weibo_list(html)

            if not weibos:
                self.logger.info(f"第{page}页没有微博数据")
                # 标记页面完成
                self._mark_page_completed(keyword, window_key, page)
                break

            # 处理每条微博
            page_weibos = []
            for weibo in weibos:
                processed_weibo = self._process_weibo(
                    weibo, cookie, html,
                    keyword=keyword,
                    window_start=window_start,
                    window_end=window_end
                )
                if processed_weibo:
                    page_weibos.append(processed_weibo)

            # 追加本页数据到总列表
            all_weibos.extend(page_weibos)

            # 每页处理完成后立即保存数据
            if self.config.modalities.save_text:
                save_json(all_weibos, filepath)
                self.logger.info(f"第{page}页数据已保存，累计 {len(all_weibos)} 条微博 -> {filepath}")

            # 标记页面完成，并从失败记录中移除（如果之前记录为失败）
            self._mark_page_completed(keyword, window_key, page)
            self._remove_failed_page(keyword, window_key, page)

            # 检查是否还有下一页（限制最大页数为10页，避免无限爬取）
            if page >= max_pages or page >= total_pages:
                self.logger.info(f"已达到最大页数限制({max_pages})或总页数({total_pages})，停止爬取")
                break

            # 继续爬取下一页
            page += 1

            # 添加延迟
            delay = get_random_delay(
                self.config.crawler.request_delay_min,
                self.config.crawler.request_delay_max
            )
            time.sleep(delay)

        return all_weibos

    def _process_weibo(self, weibo: Dict, cookie: str, html: str = None,
                           keyword: str = None, window_start: datetime = None,
                           window_end: datetime = None) -> Optional[Dict]:
        """
        处理单条微博

        Args:
            weibo: 微博数据
            cookie: Cookie字符串
            html: 页面HTML（用于提取媒体URL）
            keyword: 关键词（用于分层存储）
            window_start: 时间窗口开始时间（用于分层存储）
            window_end: 时间窗口结束时间（用于分层存储）

        Returns:
            处理后的微博数据
        """
        weibo_id = weibo.get('weibo_id')
        if not weibo_id:
            return None

        # 清洗数据
        cleaned_weibo = self.cleaner.clean_weibo_data(weibo)

        # 根据配置决定是否下载媒体
        images = []
        video = None

        # 构建分层存储路径
        if keyword and window_start and window_end:
            window_str = f"{format_time_for_url(window_start)}_{format_time_for_url(window_end)}"
            media_subdir = os.path.join(keyword, window_str, str(weibo_id))
        else:
            media_subdir = str(weibo_id)

        # 下载图片（仅当配置开启且有图片时）
        if self.config.modalities.save_images and weibo.get('has_images') and html:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, 'html.parser')
                card = soup.select_one(f'.card-wrap[mid="{weibo_id}"]')
                if card:
                    image_urls = self._extract_image_urls_from_card(card)
                    if image_urls:
                        weibo_image_dir = os.path.join(
                            get_absolute_path(self.config.storage.image_dir),
                            media_subdir
                        )
                        ensure_dir(weibo_image_dir)
                        for i, img_url in enumerate(image_urls):
                            img_path = os.path.join(weibo_image_dir, f"{i}.jpg")
                            if self._download_file(img_url, img_path):
                                images.append(img_path)
                                self.stats['total_images'] += 1
            except Exception as e:
                self.logger.warning(f"下载图片失败: {weibo_id}, 错误: {e}")

        # 下载视频（仅当配置开启且有视频时）
        if self.config.modalities.save_videos and weibo.get('has_video') and html:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, 'html.parser')
                card = soup.select_one(f'.card-wrap[mid="{weibo_id}"]')
                if card:
                    video_urls = self._extract_video_urls_from_card(card)
                    if video_urls:
                        target_quality = self.config.modalities.video_quality
                        selected_url = self._select_video_by_quality(video_urls, target_quality)
                        if selected_url:
                            weibo_video_dir = os.path.join(
                                get_absolute_path(self.config.storage.video_dir),
                                media_subdir
                            )
                            ensure_dir(weibo_video_dir)
                            video_path = os.path.join(weibo_video_dir, f"{target_quality}.mp4")
                            if self._download_file(selected_url, video_path):
                                video = video_path
                                self.stats['total_videos'] += 1
            except Exception as e:
                self.logger.warning(f"下载视频失败: {weibo_id}, 错误: {e}")

        cleaned_weibo['images'] = images
        cleaned_weibo['video'] = video

        self.stats['total_weibos'] += 1

        return cleaned_weibo

    def _extract_image_urls_from_card(self, card) -> List[str]:
        """从卡片中提取图片URL"""
        import re
        image_urls = []

        # 从img标签提取
        img_tags = card.select('img[src*="sinaimg"]')
        for img in img_tags:
            src = img.get('src', '')
            if src and 'sinaimg' in src:
                # 根据配置替换图片质量
                quality = self.config.modalities.image_quality
                src = re.sub(r'/crop\.[^/]+/', f'/{quality}/', src)
                src = re.sub(r'/orj\d+/', f'/{quality}/', src)
                src = re.sub(r'/thumb\d+/', f'/{quality}/', src)
                if src not in image_urls:
                    image_urls.append(src)

        # 从视频封面提取
        video_elem = card.select_one('.WB_video_h5[data-str]')
        if video_elem:
            data_str = video_elem.get('data-str', '')
            poster_matches = re.findall(r"poster:\s*'([^']+sinaimg[^']+)'", data_str)
            for url in poster_matches:
                quality = self.config.modalities.image_quality
                url = re.sub(r'/orj\d+/', f'/{quality}/', url)
                if url not in image_urls:
                    image_urls.append(url)

        return image_urls

    def _extract_video_urls_from_card(self, card) -> List[Dict]:
        """从卡片中提取视频URL（带质量信息）"""
        import re
        video_urls = []

        video_elem = card.select_one('.WB_video_h5[data-str]')
        if video_elem:
            data_str = video_elem.get('data-str', '')
            # 提取所有视频URL和质量信息
            # 格式: {'selectLabel':'720p','label':'高清 720p','value':'url',...}
            quality_matches = re.findall(r"'selectLabel':'(\d+p)'[^}]*'value':'([^']+)'", data_str)
            for quality, url in quality_matches:
                if url.startswith('//'):
                    url = 'https:' + url
                video_urls.append({'quality': quality, 'url': url})

        return video_urls

    def _select_video_by_quality(self, video_urls: List[Dict], target_quality: str) -> Optional[str]:
        """根据配置选择视频质量"""
        for video in video_urls:
            if video['quality'] == target_quality:
                return video['url']
        # 如果没有找到目标质量，返回第一个可用的
        if video_urls:
            return video_urls[0]['url']
        return None

    def _download_file(self, url: str, filepath: str) -> bool:
        """下载文件"""
        import requests
        from crawler_wb.utils import get_random_user_agent

        try:
            headers = {
                'User-Agent': get_random_user_agent(),
                'Referer': 'https://weibo.com/',
            }
            response = requests.get(url, headers=headers, timeout=30, stream=True)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                return True
        except Exception as e:
            self.logger.warning(f"下载文件失败: {url[:50]}..., 错误: {e}")
        return False

    def _print_stats(self) -> None:
        """打印统计信息"""
        self.logger.info("===== 爬取统计 =====")
        self.logger.info(f"总微博数: {self.stats['total_weibos']}")
        self.logger.info(f"总图片数: {self.stats['total_images']}")
        self.logger.info(f"总视频数: {self.stats['total_videos']}")
        self.logger.info(f"失败请求: {self.stats['failed_requests']}")
        self.logger.info(f"失败下载: {self.stats['failed_downloads']}")

        # 统计进度信息
        completed_windows = 0
        total_failed_pages = 0

        for windows in self.progress.values():
            completed_windows += len(windows)

        for windows in self.failed_pages.values():
            for pages in windows.values():
                total_failed_pages += len(pages)

        self.logger.info(f"已完成时间窗口: {completed_windows}")
        self.logger.info(f"失败页面数: {total_failed_pages}")
        self.logger.info("====================")

    def _save_error_logs(self) -> None:
        """保存错误日志"""
        # 保存下载错误
        download_errors = self.downloader.get_errors()
        if download_errors:
            error_file = os.path.join(
                get_absolute_path(self.config.storage.log_dir),
                'download_errors.json'
            )
            save_json(download_errors, error_file)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='微博洪灾多模态数据爬虫')
    parser.add_argument('--config', type=str, default='config_wb.yaml', help='配置文件路径')
    parser.add_argument('--start', type=str, help='开始时间 (格式: YYYY-MM-DD HH:MM)')
    parser.add_argument('--end', type=str, help='结束时间 (格式: YYYY-MM-DD HH:MM)')

    args = parser.parse_args()

    # 加载配置
    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        print(f"错误: {e}")
        print("请确保配置文件存在，并正确配置关键词和Cookie")
        return

    # 验证配置
    if not validate_config(config):
        return

    # 创建爬虫并运行
    crawler = WeiboCrawler(config)
    crawler.run(args.start, args.end)


if __name__ == '__main__':
    main()