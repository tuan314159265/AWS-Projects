import os
import json
import time
import subprocess

API_URL = "https://2ohkfkehda.execute-api.ap-southeast-2.amazonaws.com/prod/query"
REGION = "ap-southeast-2"
PROFILE = "default"

def run_cmd(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    return result

def test_rag_api():
    print("--------------------------------------------------")
    print("1. Đang test RAG API (API Gateway -> Lambda)")
    print("--------------------------------------------------")
    
    payload = json.dumps({"query": "tin tức việt nam mới nhất"})
    
    start_time = time.time()
    try:
        # Sử dụng curl
        cmd = [
            "curl", "-s", "-X", "POST", API_URL, 
            "-H", "Content-Type: application/json", 
            "-d", payload
        ]
        res = run_cmd(cmd)
        elapsed = time.time() - start_time
        
        if res.returncode == 0 and res.stdout:
            try:
                data = json.loads(res.stdout)
                if "error" in data:
                    print(f"[THẤT BẠI] API trả về lỗi: {data['error']}")
                    return False
                print(f"[THÀNH CÔNG] API trả về kết quả trong {elapsed:.2f}s")
                print(f" - Summary length: {len(data.get('summary', ''))}")
                print(f" - Số lượng kết quả (results): {len(data.get('results', []))}")
                return True
            except json.JSONDecodeError:
                print(f"[THẤT BẠI] Lỗi parse JSON từ curl: {res.stdout}")
                return False
        else:
            print(f"[THẤT BẠI] curl lỗi: {res.stderr}")
            return False
    except Exception as e:
        print(f"[LỖI] Không thể gọi API: {e}")
        return False

def test_etl_lambda():
    print("\n--------------------------------------------------")
    print("2. Đang test ETL Lambda (AWS Lambda Invoke)")
    print("--------------------------------------------------")
    
    start_time = time.time()
    try:
        # Sử dụng aws cli
        cmd = [
            "aws", "lambda", "invoke",
            "--function-name", "newsrag-etl",
            "--payload", "{}",
            "response.json",
            "--region", REGION,
            "--profile", PROFILE
        ]
        res = run_cmd(cmd)
        elapsed = time.time() - start_time
        
        if res.returncode == 0:
            with open("response.json", "r", encoding="utf-8") as f:
                payload_str = f.read()
                
            try:
                result_data = json.loads(payload_str)
                print(f"[THÀNH CÔNG] Lambda chạy xong trong {elapsed:.2f}s")
                print(f" - Kết quả trả về: {json.dumps(result_data, indent=2, ensure_ascii=False)}")
                if os.path.exists("response.json"):
                    os.remove("response.json")
                return True
            except json.JSONDecodeError:
                print(f"[THẤT BẠI] Không thể parse kết quả JSON: {payload_str}")
                return False
        else:
             print(f"[THẤT BẠI] Lỗi Invoke Lambda: {res.stderr}")
             return False
            
    except Exception as e:
        print(f"[LỖI] Invoke Lambda thất bại: {e}")
        return False

def check_ecr_images():
    print("\n--------------------------------------------------")
    print("3. Đang kiểm tra ECR Repositories (Crawler & Lambda)")
    print("--------------------------------------------------")
    try:
        repos = ['newsrag-crawler', 'newsrag-lambda']
        all_good = True
        for repo in repos:
            cmd = [
                "aws", "ecr", "describe-images",
                "--repository-name", repo,
                "--region", REGION,
                "--profile", PROFILE
            ]
            res = run_cmd(cmd)
            if res.returncode == 0:
                data = json.loads(res.stdout)
                images = data.get('imageDetails', [])
                if images:
                    print(f"[THÀNH CÔNG] Repo '{repo}' có {len(images)} image(s) đã được tải lên.")
                else:
                    print(f"[CẢNH BÁO] Repo '{repo}' không có image nào.")
                    all_good = False
            else:
                print(f"[LỖI] Truy xuất repo {repo} thất bại: {res.stderr}")
                all_good = False
        return all_good
    except Exception as e:
        print(f"[LỖI] Không thể kết nối đến ECR: {e}")
        return False

if __name__ == "__main__":
    print("BẮT ĐẦU KIỂM THỬ TOÀN BỘ HỆ THỐNG NEWS RAG TRÊN AWS...\n")
    
    rag_ok = test_rag_api()
    etl_ok = test_etl_lambda()
    ecr_ok = check_ecr_images()
    
    print("\n==================================================")
    print("TỔNG KẾT KẾT QUẢ KIỂM THỬ")
    print("==================================================")
    print(f"1. RAG API (API Gateway + Lambda): {'✅ PASS' if rag_ok else '❌ FAIL'}")
    print(f"2. ETL Pipeline (Lambda Invoke):   {'✅ PASS' if etl_ok else '❌ FAIL'}")
    print(f"3. ECR Images (Crawler & Lambda):  {'✅ PASS' if ecr_ok else '❌ FAIL'}")
    print("==================================================")
