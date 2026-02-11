import subprocess
import json
import time
import os
import sys

BASE_URL = "http://127.0.0.1:8000"
PDF_PATH = "704664982-Loan-letter.pdf"

def run_curl(args):
    """Run curl command and return JSON output."""
    cmd = ["curl", "-s"] + args
    try:
        result = subprocess.check_output(cmd, text=True)
        return json.loads(result)
    except subprocess.CalledProcessError as e:
        print(f"Curl failed: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON decode failed. Output: {result}")
        return None

def main():
    if not os.path.exists(PDF_PATH):
        print(f"Error: {PDF_PATH} not found.")
        return

    print(f"Uploading {PDF_PATH}...")
    # direct curl upload
    upload_res = run_curl(["-X", "POST", f"{BASE_URL}/documents", "-F", f"file=@{PDF_PATH}"])
    
    if not upload_res or "document_id" not in upload_res:
        print("Upload failed or invalid response.")
        if upload_res: print(json.dumps(upload_res, indent=2))
        return

    doc_id = upload_res["document_id"]
    print(f"Document ID: {doc_id}")

    print("Waiting for summary processing...")
    while True:
        summary = run_curl([f"{BASE_URL}/documents/{doc_id}/summary"])
        if not summary:
            print("Failed to get summary.")
            break
            
        status = summary.get("status")
        print(f"Status: {status}")
        
        if status == "complete":
            print("\n=== SUMMARY ===")
            print(json.dumps(summary, indent=2))
            break
        elif status == "failed":
            print(f"Analysis failed: {summary.get('error')}")
            break
            
        time.sleep(2)

    if status == "complete":
        print("\n=== RED FLAGS ===")
        res = run_curl([f"{BASE_URL}/documents/{doc_id}/red-flags"])
        print(json.dumps(res, indent=2) if res else "Failed")

        print("\n=== HIDDEN CLAUSES ===")
        res = run_curl([f"{BASE_URL}/documents/{doc_id}/hidden-clauses"])
        print(json.dumps(res, indent=2) if res else "Failed")

        print("\n=== FINANCIAL TERMS ===")
        res = run_curl([f"{BASE_URL}/documents/{doc_id}/financial-terms"])
        print(json.dumps(res, indent=2) if res else "Failed")

if __name__ == "__main__":
    main()
