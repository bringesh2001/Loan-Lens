import requests
import time
import os
import json

BASE_URL = "http://127.0.0.1:8000"
PDF_PATH = "704664982-Loan-letter.pdf"

def main():
    if not os.path.exists(PDF_PATH):
        print(f"Error: {PDF_PATH} not found.")
        return

    print(f"Uploading {PDF_PATH}...")
    with open(PDF_PATH, "rb") as f:
        response = requests.post(f"{BASE_URL}/documents", files={"file": f})
    
    if response.status_code != 201:
        print(f"Upload failed: {response.status_code} - {response.text}")
        return

    doc_data = response.json()
    doc_id = doc_data["document_id"]
    print(f"Document ID: {doc_id}")

    print("Waiting for summary processing...")
    while True:
        response = requests.get(f"{BASE_URL}/documents/{doc_id}/summary")
        if response.status_code != 200:
            print(f"Get summary failed: {response.status_code} - {response.text}")
            break
            
        summary = response.json()
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
        response = requests.get(f"{BASE_URL}/documents/{doc_id}/red-flags")
        print(json.dumps(response.json(), indent=2))

        print("\n=== HIDDEN CLAUSES ===")
        response = requests.get(f"{BASE_URL}/documents/{doc_id}/hidden-clauses")
        print(json.dumps(response.json(), indent=2))

        print("\n=== FINANCIAL TERMS ===")
        response = requests.get(f"{BASE_URL}/documents/{doc_id}/financial-terms")
        print(json.dumps(response.json(), indent=2))

if __name__ == "__main__":
    main()
