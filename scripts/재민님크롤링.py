import time
import requests
from bs4 import BeautifulSoup
import json

def get_corp_info(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        # 1. 페이지 요청
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() 
        response.encoding = 'euc-kr'
        # 2. 파싱
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 네이버 업종 상세 페이지의 테이블 클래스는 보통 'type_5'입니다.
        rows = soup.select('table.type_5 tr') 
        
        corp_info_list = []
        
        for row in rows[:22]:
            # a 태그 찾기
            target_link = row.select_one('td.name > div.name_area > a')
            
            if target_link: # 존재 여부 확인
                name = target_link.get_text(strip=True)
                href = target_link.get('href', '')
                print(name)
                if 'code=' in href:
                    code = href.split('code=')[1].split('&')[0]
                    
                    corp_info_list.append({
                        'name': name,
                        'code': code
                    })
        
        return corp_info_list

    except Exception as e:
        print(f"에러 발생: {e}")
        return [] # 에러 시 빈 리스트 반환

# --- 실행 부분 ---
target_url = 'https://finance.naver.com/sise/sise_group_detail.naver?type=upjong&no=287'

# 데이터 가져오기
print("데이터 수집 시작...")
data = get_corp_info(target_url)
time.sleep(0.5) # 요청 후 0.5초 대기

# 결과 저장
if data:
    file_path = "corp_data.json"
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        
    print(f"총 {len(data)}건의 데이터를 '{file_path}'에 저장했습니다.")
else:
    print("수집된 데이터가 없습니다.")