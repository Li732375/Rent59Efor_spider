# Rent59E Spider 🏠

一個用 Python 開發的 **591 租屋網爬蟲**，可抓取房屋資訊，輸出 CSV，並同步更新 Google 試算表。
支援單選、多選篩選條件，自動過濾頂樓與重複資料，還能透過 GitHub Actions 自動化執行。

---

## 功能特色

* 模擬瀏覽器，通過網站驗證
* 支援單一與多重篩選條件
* 過濾頂樓與重複房屋資料
* 擷取房屋詳細資訊：租金、坪數、樓層、地址、屋主、電話、捷運站等
* 將資料寫入 CSV 與 Google 試算表
* 自動記錄抓取錯誤至 `error_message.json`

---

## 安裝需求

1. 安裝 Python 3.9 或以上
2. 安裝套件依賴：

```bash
pip install -r requirements.txt
```

> requirements.txt 範例概覽：
>
> ```text
> requests
> beautifulsoup4
> playwright
> playwright-stealth
> gspread
> google-auth
> gspread-formatting
> ```

3. 安裝 Playwright 瀏覽器：

```bash
playwright install
```

4. 啟用 Google Sheets API（必須步驟）

⚠️ 若跳過這一步，程式無法將資料寫入試算表，會出現權限錯誤。

步驟：

   1. 打開 Google Cloud Console
   2. 選擇或新增專案
   3. 搜尋 Google Sheets API → 點擊 啟用
   4. 確認你的 Service Account 已加入該試算表並設定共用編輯權限
   5. 建立 Google Service Account 並下載 service_account.json
   6. 將 Service Account JSON 放在專案根目錄

---

## 使用方法

1. 將 `service_account.json` 放在專案根目錄
2. 修改篩選條件：

```python
spider.uni_filter_params  # 單選條件，如地區、房型、價格
spider.mul_filter_params  # 多選條件，如捷運站
```

3. 執行爬蟲程式：

```bash
python 59E_spider.py
```

4. 執行完成後：

   * CSV 檔案 `rent_list_....csv` 出現在專案目錄
   * Google 試算表每次都會自動新增工作表和抓取資料，不會覆寫過去的試算表
   * 抓取錯誤會記錄在 `error_message.json`

---

## 篩選條件說明

### `uni_filter_params`（單選）

| 參數     | 說明                      |
| ------ | ----------------------- |
| region | 台北 1、新北 2               |
| kind   | 房屋類型，2 = 獨立套房           |
| price  | 租金範圍，例如 `$_13000$`      |
| shType | 屋主直租                    |
| metro  | 捷運站編號                   |
| sort   | 排序方式，例如 `posttime_desc` |
| option | 設施，如冷氣、洗衣機、冰箱           |
| notice | 限制條件，如性別、是否頂樓           |

### `mul_filter_params`（多選）

* 可指定多個捷運站，程式自動生成所有組合抓取

---

## 輸出欄位說明

| 欄位    | 說明       |
| ----- | -------- |
| 更新日期  | 房屋資料更新時間 |
| 發佈時間  | 房屋發布時間   |
| 租金    | 租金金額     |
| 坪數    | 房屋坪數     |
| 樓層    | 所在樓層     |
| 總樓層   | 建築總樓層    |
| 捷運站   | 鄰近捷運站    |
| 捷運站距離 | 與捷運站距離   |
| 網址    | 房屋頁面網址   |
| 屋主    | 房東姓名     |
| 電話    | 房東電話     |
| 地址    | 房屋地址     |
| 案件標題  | 房屋標題     |
| 屋主說   | 房東對房屋的描述 |

---

## 自動化抓取（GitHub Actions）

你可以用 **GitHub Actions** 自動執行爬蟲，每次抓取資料並更新 GitHub 或 Google 試算表。

### 工作流程概述

1. Ubuntu 最新環境
2. 安裝 Python 3.10
3. 安裝套件依賴與 Playwright
4. 安裝 Noto Sans TC 字型
5. 配置 Google Service Account (`service_account.json`)
6. 執行爬蟲程式 `59E_spider.py`
7. 將 CSV 或 Google 試算表資料提交回 GitHub

### 設定 GitHub Secrets

| Secret 名稱                | 用途                             |
| ------------------------ | ------------------------------ |
| `GOOGLE_SERVICE_ACCOUNT` | Google Service Account JSON 內容 |
| `GOOGLE_SHEET_ID`        | Google 試算表 ID                  |
| `GITHUB_TOKEN`           | GitHub Actions 自動生成 token      |

### 執行 GitHub Actions

1. 將 `.github/workflows/rent59e-spider.yml` 加入專案
2. 點擊 GitHub Actions → 選擇 `Rent59E-spider` workflow → `Run workflow`
3. 等待流程完成，CSV 與 Google 試算表會自動更新

> 注意：Settings → Actions → General → Workflow permissions → **Read and write permissions**，否則會出現 403 權限錯誤。

### 工作流程示意

```text
[GitHub Actions Trigger]
        │
        ▼
 [Ubuntu Environment Setup]
        │
        ▼
 [Python & Dependencies Install]
        │
        ▼
 [Playwright & Font Setup]
        │
        ▼
 [Google Credential Setup]
        │
        ▼
 [Run Spider Script → Generate CSV & Google Sheet]
        │
        ▼
 [Commit & Push Updated CSV to GitHub]
```

---

## 注意事項

* 避免短時間大量抓取，防止反爬蟲
* CSV 與 Google 試算表會依程式抓取順序寫入
* 抓取錯誤會寫入 `error_message.json`
* 建議先測試少量資料 (`max_num`) 再抓取大量資料

---
