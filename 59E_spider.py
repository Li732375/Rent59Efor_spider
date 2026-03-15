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

# 設定標準輸出編碼
sys.stdout.reconfigure(encoding='utf-8-sig')

class Rent59ESpider():
    def __init__(self):
        self.session = requests.Session()
        self.headers_user_agent: str = ""
        self.error_log_file: str = 'error_message.json'

        self.uni_filter_params: Dict[str, str] = {
            'region': '1',
            'kind': '2',
            'price': '$_13000$',
            'shType': 'host',
            'metro': '162',
            'sort':'posttime_desc',
        }
        self.mul_filter_params: Dict[str, str] = {
            'option': 'cold,washer,icebox,hotwater,broadband,bed',
            'notice': 'not_cover,all_sex,boy',
            'station': '4184',
        }
        self.field_names_order: List[str] = [
            '更新日期', '案件標題', '類型', '坪數', '樓層', '總樓層',
            '地址', '租金', '屋主', '網址', '型態', '押金', '屋主說'
        ]

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
        print("正在啟動隱身瀏覽器通過驗證...", end='', flush=True)
        with Stealth().use_sync(sync_playwright()) as p:
            browser = p.chromium.launch(headless=True)
            
            # 模擬主流解析度，規避自動化偵測並確保網頁完整載入
            context = browser.new_context(viewport={'width': 1920, 
                                                    'height': 1080})
            page = context.new_page()
            
            try:
                page.goto('rent.591.com.tw', 
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
        attempt = 0
        if headers is None: headers = {}
        headers['User-Agent'] = self.headers_user_agent
        headers['Referer'] = 'rent.591.com.tw'

        while attempt < max_retries:
            try:
                r = self.session.get(url, headers=headers, params=params, 
                                     timeout=15)
                if r.status_code == 200: return r

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
        rents = []
        query_parts = []

        if filter_params:
            for k, v in filter_params.items():
                query_parts.append(f'{k}={v}')

        query = '&'.join(query_parts)
        url = 'https://rent.591.com.tw/list'
        headers = {'Accept': 'application/json, text/plain, */*'}
        page = 1
        
        while max_num == -1 or len(rents) < max_num:
            full_params = f'{query}&page={page}'  # 一頁 30 筆
            r = self.fetch_with_retry(url, headers=headers, params=full_params)
            if r is None: break

            try:
                datas = r.json()
                if 'data' not in datas: break
                rents.extend(data['link']['job'].split('/job/')[-1] for data in datas['data'])
                if page >= datas['metadata']['pagination']['lastPage']: break
                time.sleep(random.uniform(1, 2))
                page += 1
                
            except Exception as e:
                self.log_error("SEARCH", e)
                break

        return rents[:max_num]

    def get_rent(self, rent_id: str) -> Optional[Dict[str, Any]]:
        url = f'https://rent.591.com.tw/{rent_id}'
        headers = {'Referer': f'https://rent.591.com.tw/{rent_id}', 
                   'Accept': 'application/json'}
        
        r = self.fetch_with_retry(url, headers=headers)
        if r is None: return None
        rent_data = None

        try:
            resp_json = r.json()
            rent_data = resp_json.get('data')
            if not rent_data or rent_data.get('switch') == 'off': return None

            salary_map = {10: '面議', 
                          20: '論件計酬', 
                          30: '時薪', 
                          40: '日薪', 
                          50: '有薪', 
                          60: '年薪', 
                          70: '其他',
                          }
            header = rent_data.get('header', {})
            rent_detail = rent_data.get('jobDetail', {})
            condition = rent_data.get('condition', {})
            welfare = rent_data.get('welfare', {})

            workType = ', '.join(rent_detail.get('workType', [])) or '全職'
            raw_area = rent_detail.get('addressRegion', "")
            rentArea = raw_area if len(raw_area) == 3 else raw_area[3:]
            
            data_info = {
                '更新日期': header.get('appearDate'),
                '工作型態': workType,  
                '工作時段': rent_detail.get('workPeriod'),
                '薪資類型': salary_map.get(rent_detail.get('salaryType'), '其他'),
                '最低薪資': int(rent_detail.get('salaryMin', 0)),
                '最高薪資': int(rent_detail.get('salaryMax', 0)),
                '職缺名稱': header.get('jobName'),
                '學歷': condition.get('edu'),
                '工作經驗': condition.get('workExp'),
                '工作縣市': rent_detail.get('addressArea'),
                '工作里區': rentArea,
                '工作地址': rent_detail.get('addressDetail') or '無',
                '公司名稱': header.get('custName'),
                '職缺描述': rent_detail.get('jobDescription') or '無',
                '其他描述': condition.get('other') or '無',
                '擅長要求': ', '.join(item.get('description', '') for item in condition.get('specialty', [])) or '無',
                '證照': ', '.join(item.get('name', '') for item in condition.get('certificate', [])) or '無',
                '駕駛執照': ', '.join(condition.get('driverLicense', [])) or '無',
                '出差': rent_detail.get('businessTrip') or '無',
                '104 職缺網址': f'https://www.104.com.tw/job/{rent_id}?apply=form',
                '公司產業類別': rent_data.get('industry'),
                '法定福利': ', '.join(welfare.get('legalTag', [])) or '無',
            }
            return data_info
        
        except Exception as e:
            self.log_error(rent_id, e, raw_data=rent_data)
            return None

    def generate_filter_combinations(self, 
                                     mul_filter_params: Dict[str, str]
                                     ) -> Tuple[List[str], List[Tuple[str, ...]]]:
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
        allrents_set: Set[str] = set()

        for idx, combo in enumerate(combinations, 1):
            filter_params: Dict[str, str] = {
                **uni_filter_params,
                **dict(zip(keys, combo))
            }
            rents: List[str] = self.search(max_num=max_num, filter_params=filter_params)
            allrents_set.update(rents)
            print(f"進度：{(idx/len(combinations))*100:6.2f} % | 累計職缺：{len(allrents_set)}", end='\r')

        return allrents_set
    
    def fetch_rents_and_write_csv(self, 
                                 rent_ids: Set[str], 
                                 output_file: str) -> None:
        with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.field_names_order)
            writer.writeheader()

            for idx, rent_id in enumerate(rent_ids, 1):
                info = self.get_rent(rent_id)
                if info:
                    writer.writerow({k: info.get(k, '無') for k in self.field_names_order})
                    f.flush()
                print(f"進度：{(idx/len(rent_ids))*100:6.2f} % ({idx}/{len(rent_ids)})", end='\r')
                time.sleep(random.uniform(0.1, 1))
    
if __name__ == "__main__":
    spider = Rent59ESpider()

    # 取得篩選條件
    uni_params = spider.uni_filter_params
    mul_params = spider.mul_filter_params

    # 產生組合
    keys, combinations = spider.generate_filter_combinations(mul_params)
    print(f"開始搜尋租屋 ID（組合數：{len(combinations)}）")

    # 搜尋職缺 ID
    rent_ids = spider.collect_rent_ids(
        uni_filter_params=uni_params,
        keys=keys,
        combinations=combinations,
    )
    print(f"共取得 {len(rent_ids)} 筆資料")

    # 抓詳情並寫入 CSV (格式 2026-01-05-13-45)
    output_file = f"rent_list_{time.strftime('%Y-%m-%d-%H-%M')}.csv"
    spider.fetch_rents_and_write_csv(rent_ids, output_file)

    # 依是否有錯誤紀錄，調整輸出結果
    with open('error_message.json', 'r', encoding='utf-8-sig') as f:
        errors = json.load(f)
    if errors:
        print(f"\n任務完成！\n資料已寫入 {output_file}\n[錯誤] 請查看 error_message.json")
    else:
        print(f"\n任務完成！\n資料已寫入 {output_file}")