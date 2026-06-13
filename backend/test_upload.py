import httpx
import sys

def test_upload():
    try:
        with open("sample_documents/scientific_paper.txt", "rb") as f:
            files = {"files": ("scientific_paper.txt", f, "text/plain")}
            response = httpx.post("http://localhost:8000/api/upload", files=files)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_upload()
