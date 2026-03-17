# -*- coding: utf-8 -*-

import time
import random
import requests
from itertools import product
import csv
import json
import sys
import os
from typing import Dict, List, Set, Tuple, Optional, Any
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from bs4 import BeautifulSoup
import re
import gspread
from google.oauth2.service_account import Credentials
from gspread_formatting import format_cell_range, CellFormat, set_row_height



# 設定標準輸出編碼
sys.stdout.reconfigure(encoding='utf-8-sig')

class Rent59ESpider():
    def __init__(self):
        self.session = requests.Session()
        self.headers_user_agent: str = ""
        self.error_log_file: str = 'error_message.json'

        self.uni_filter_params: Dict[str, str] = {
            'region': '1',  # 台北1、新北2
            'kind': '2',  # 類型-獨立套房
            'price': '$_13000$',  # 最低額度(不寫為0)$_最高額度$
            'shType': 'host',  # 屋主直租
            'metro': '162',  # 北捷
            'sort':'posttime_desc',  # 按更新時間排序
            'option': 'cold,washer,icebox,hotwater,broadband,bed',  # 冷氣、洗衣機、冰箱、熱水器、寬頻網路、床
            'notice': 'not_cover,all_sex,boy',  # 非頂加、皆可、限男
            'station': '4184',  # 古亭站
        }
        self.mul_filter_params: Dict[str, str] = {
        }
        self.field_names_order: List[str] = [
            '更新日期', '案件標題', '坪數', '樓層', '總樓層',
            '地址', '租金', '屋主', '網址', '電話',
            '屋主說',
        ]

        self.total_num = 0

        # 寫入空列表，清空舊紀錄
        with open(self.error_log_file, 'w', encoding='utf-8-sig') as f:
            json.dump([], f)

        self.refresh_session()

    def log_error(self, 
                  rent_id: str, 
                  message: Any, 
                  raw_data: Optional[Any]=None) -> None:
        """將錯誤訊息與原始資料存入 JSON 檔案"""
        error_entry = {
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
            'rent_id': rent_id,
            'error_message': str(message),
            'raw_data': raw_data
        }
        
        # 讀取現有紀錄並更新
        data = []
        if os.path.exists(self.error_log_file):
            try:
                with open(self.error_log_file, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)
            except:
                data = []
        
        data.append(error_entry)
        with open(self.error_log_file, 'w', encoding='utf-8-sig') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def refresh_session(self) -> None:
        """刷新 session"""
        print("正在啟動隱身瀏覽器通過驗證...", end='', flush=True)
        with Stealth().use_sync(sync_playwright()) as p:
            browser = p.chromium.launch(headless=True)
            
            # 模擬主流解析度，規避自動化偵測並確保網頁完整載入
            context = browser.new_context(viewport={'width': 1920, 
                                                    'height': 1080})
            page = context.new_page()
            
            try:
                page.goto('https://rent.591.com.tw', 
                          wait_until="domcontentloaded",  # 避免 networkidle 超時
                          timeout=60000  # 最多等待 60 秒
                          )
                # 短暫隨機等待(JavaScript 初始化完成，cookie/session 可用以及模擬真人停留時間)
                time.sleep(random.uniform(0.5, 3))
                self.headers_user_agent = page.evaluate("navigator.userAgent")
                cookies = context.cookies()
                for cookie in cookies:
                    self.session.cookies.set(cookie['name'], cookie['value'], 
                                             domain=cookie['domain'])
                print("已更新憑證")
            except Exception as e:
                self.log_error("SYSTEM", f"驗證失敗: {e}")
            finally:
                browser.close()

    def fetch_with_retry(self, url: str, 
                         headers: Optional[Dict[str, str]]=None, 
                         params: Optional[Any]=None, 
                         max_retries: int = 3
                         ) -> Optional[requests.Response]:
        """取得完整網頁與重試索取"""
        attempt = 0
        if headers is None: headers = {}
        headers['User-Agent'] = self.headers_user_agent

        while attempt < max_retries:
            try:
                r = self.session.get(url, headers=headers, params=params, 
                                     timeout=15)
                if r.status_code == 200: return r  # 執行成功的話，送出網頁資料解析

                if r.status_code in (429, 403):
                    self.refresh_session()
                    time.sleep(random.uniform(5, 10))
                    attempt += 1
                    continue
                return None
            
            except Exception as e:
                attempt += 1
                time.sleep(2)
        return None

    def search(self, 
               max_num: int = 150, 
               filter_params: Optional[Dict[str, str]]=None) -> List[str]:
        """撈取所有資料"""
        rents = []
        query_parts = []

        if filter_params:
            for k, v in filter_params.items():
                query_parts.append(f'{k}={v}')

        query = '&'.join(query_parts)
        url = 'https://rent.591.com.tw/list'
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
                   "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"}
        page = 1
        
        while max_num == -1 or len(rents) < max_num:
            full_params = f'{query}&page={page}'  # 一頁 30 筆
            r = self.fetch_with_retry(url, headers=headers, params=full_params)
            if r is None: break

            try:
                soup = BeautifulSoup(r.text, "html.parser")

                # 取得房屋總數
                total_tag = soup.select_one("p.total strong")
                self.total_num = total_tag.get_text(strip=True) if total_tag else "0"
                self.total_num = int(self.total_num)

                print(f'共 {self.total_num} 筆資料')

                for item in soup.select("div.item"):

                    link = item.select_one(".item-info-title a")

                    # 網址
                    url = link["href"].strip()

                    # 標題
                    title = link.get_text(strip=True)
                    
                    # 地址
                    addr = item.select_one(".house-place ~ span .inline-flex-row")
                    addr = addr.get_text(strip=True) if addr else ""

                    # 坪數、樓層與總樓層
                    lines = item.select(".house-home ~ span.line .inline-flex-row")
                    area = lines[0].get_text(strip=True) if len(lines) > 0 else ""
                    floor_text = lines[1].get_text(strip=True) if len(lines) > 1 else ""
                    
                    floor = ""
                    total_floor = ""

                    if floor_text and "/" in floor_text:
                        floor, total_floor = floor_text.split("/")

                    # 提前過濾頂樓物件
                    if floor == total_floor: continue
                    self.total_num -= 1

                    # 捷運站(鄰近或目標)與捷運站(鄰近或目標)距離
                    metro_name = item.select_one(".house-metro + span")
                    metro_dist = item.select_one(".house-metro + span + strong")

                    metro = ""
                    if metro_name and metro_dist:
                        metro = f"{metro_name.get_text(strip=True)} {metro_dist.get_text(strip=True)}"

                    # 屋主
                    owner = item.select_one(".role-name span")
                    owner = owner.get_text(strip=True)[2:] if owner else ""

                    # 更新時間
                    update = item.select_one(".role-name .line")
                    update = update.get_text(strip=True) if update else ""

                    # 租金
                    price = item.select_one(".item-info-price .inline-flex-row")
                    price = price.get_text(strip=True) if price else ""

                    rents.append([url, title, addr, area, floor, total_floor, 
                                  metro, owner, update, price])

                if page * 30 >= self.total_num: break
                time.sleep(random.uniform(1, 2))
                page += 1
                
            except Exception as e:
                self.log_error("SEARCH", e)
                break

        return rents[:max_num]

    def get_rent(self, rent: List[str]) -> Optional[Dict[str, Any]]:
        """取得單筆網站進階資訊"""
        url = rent[0]
        
        r = self.fetch_with_retry(url)
        if r is None: return None

        try:
            soup = BeautifulSoup(r.text, "html.parser")
            
            # 電話
            phone = re.search(r'09\d{2}-\d{3}-\d{3}', soup.get_text())
            phone = phone.group()
            rent.append(phone)

            # 房屋描述
            article = soup.select_one("div.house-condition-content div.article")
            description = article.get_text(separator="\n", strip=True)
            rent.append(description)

            data_info = {
                '更新日期': rent[8],
                '案件標題': rent[1], 
                '坪數': rent[3], 
                '樓層': rent[4], 
                '總樓層': rent[5],
                '地址': rent[2], 
                '租金': rent[9], 
                '屋主': rent[7],
                '網址': rent[0],
                '電話': rent[10],
                '屋主說': rent[11],
                '捷運': rent[6]
                }
            
            return data_info
        
        except Exception as e:
            self.log_error('get_rent', e, raw_data=None)
            return None

    def generate_filter_combinations(self, 
                                     mul_filter_params: Dict[str, str]
                                     ) -> Tuple[List[str], List[Tuple[str, ...]]]:
        """產生複選排列組合結果"""
        keys: List[str] = list(mul_filter_params.keys())
        values: List[List[str]] = [v.split(',') for v in mul_filter_params.values()]
        combinations: List[Tuple[str, ...]] = list(product(*values))
        return keys, combinations
    
    def collect_rent_ids(self, 
                        uni_filter_params: Dict[str, str], 
                        keys: List[str], 
                        combinations: List[Tuple[str, ...]]
                        , max_num: int = 20
                        ) -> Set[str]:
        """去除重複資料"""
        allrents_list: List[List[str]] = []

        for idx, combo in enumerate(combinations, 1):
            filter_params: Dict[str, str] = {
                **uni_filter_params,
                **dict(zip(keys, combo))
            }
            rents: List[str] = self.search(max_num=max_num, filter_params=filter_params)
            allrents_list.extend(rents)
            print(f"進度：{(idx/len(combinations))*100:6.2f} % | 累計：{len(allrents_list)}", end='\r')

        return allrents_list
    
    def fetch_rents_and_write_csv(self, 
                                 rents: Set[str], 
                                 output_file: str) -> None:
        """產生csv並寫入雲端試算表"""
        worksheet = self.init_google_sheet()
        
        with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.field_names_order)
            writer.writeheader()

            temp_data = []
            for idx, rent in enumerate(rents, 1):
                info = self.get_rent(rent)
                if info:
                    row = {k: info.get(k, '無') for k in self.field_names_order}
                    writer.writerow(row)
                    temp_data.append(list(row.values()))
                    f.flush()
                print(f"進度：{(idx/len(rents))*100:6.2f} % ({idx}/{len(rents)})", end='\r')
                time.sleep(random.uniform(0.1, 1))

            worksheet.append_row(temp_data)
    
    def init_google_sheet(self):
        """初始化 google sheet"""
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file"
        ]

        creds = Credentials.from_service_account_file(
            "service_account.json",
            scopes=scopes
        )

        client = gspread.authorize(creds)
        time_name = time.strftime("%Y_%m_%d_%H_%M")
        sheet_name = f"rent_list_{time_name}".replace("'", "")
        spreadsheet = client.open_by_key(os.environ["GOOGLE_SHEET_ID"])
        max_rows="100"
        new_worksheet = spreadsheet.add_worksheet(title=sheet_name, 
                                                  rows=max_rows, 
                                                  cols="20")
        new_worksheet.append_row(self.field_names_order)

        # 整個工作表文字換行
        wrap_format = CellFormat(wrapStrategy='CLIP')
        format_cell_range(new_worksheet, 'A:Z', wrap_format)

        # 設定每列高度 40 px（必須迴圈）
        for row_index in range(1, self.total_num):
            set_row_height(new_worksheet, str(row_index), 20)

        return new_worksheet

if __name__ == "__main__":
    spider = Rent59ESpider()

    # 取得篩選條件
    uni_params = spider.uni_filter_params
    mul_params = spider.mul_filter_params

    # 產生組合
    keys, combinations = spider.generate_filter_combinations(mul_params)
    print(f"開始搜尋租屋 ID（組合數：{len(combinations)}）")

    # 條件搜尋
    rent_ids = spider.collect_rent_ids(
        uni_filter_params=uni_params,
        keys=keys,
        combinations=combinations,
    )
    print(f"共取得 {len(rent_ids)} 筆資料")

    # 抓詳情並寫入 CSV
    output_file = f"rent_list.csv"
    spider.fetch_rents_and_write_csv(rent_ids, output_file)

    # 依是否有錯誤紀錄，調整輸出結果
    with open('error_message.json', 'r', encoding='utf-8-sig') as f:
        errors = json.load(f)
    if errors:
        print(f"\n任務完成！\n資料已寫入 {output_file}\n[錯誤] 請查看 error_message.json")
    else:
        print(f"\n任務完成！\n資料已寫入 {output_file}")