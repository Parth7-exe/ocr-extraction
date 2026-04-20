"""Quick API test script."""
import requests
import json

BASE = "http://localhost:8000"

# Test 1: Upload with validation OFF
print("=" * 50)
print("TEST 1: Upload with validation OFF")
print("=" * 50)
with open("test_invoice.png", "rb") as f:
    resp = requests.post(
        f"{BASE}/upload",
        files={"file": ("test_invoice.png", f, "image/png")},
        data={"enable_validation": "false"},
    )

print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    # Print without raw_text for readability
    display = {k: v for k, v in data.items() if k != "raw_text"}
    print(json.dumps(display, indent=2))
    print(f"\nraw_text length: {len(data.get('raw_text', ''))}")
    print(f"Has 'validation' key: {'validation' in data}")
    file_id = data.get("file_id")
else:
    print(resp.text[:500])
    exit(1)

# Test 2: Download endpoint
print("\n" + "=" * 50)
print("TEST 2: Download")
print("=" * 50)
dl_resp = requests.get(f"{BASE}/download/{file_id}")
print(f"Status: {dl_resp.status_code}")
ct = dl_resp.headers.get("content-type", "")
print(f"Content-Type: {ct}")

# Test 3: Upload with validation ON
print("\n" + "=" * 50)
print("TEST 3: Upload with validation ON")
print("=" * 50)
with open("test_invoice.png", "rb") as f:
    resp2 = requests.post(
        f"{BASE}/upload",
        files={"file": ("test_invoice.png", f, "image/png")},
        data={"enable_validation": "true"},
    )

print(f"Status: {resp2.status_code}")
if resp2.status_code == 200:
    data2 = resp2.json()
    display2 = {k: v for k, v in data2.items() if k != "raw_text"}
    print(json.dumps(display2, indent=2))
    print(f"\nHas 'validation' key: {'validation' in data2}")
else:
    print(resp2.text[:500])

# Test 4: Invalid file type
print("\n" + "=" * 50)
print("TEST 4: Invalid file type rejection")
print("=" * 50)
resp3 = requests.post(
    f"{BASE}/upload",
    files={"file": ("test.exe", b"fake content", "application/octet-stream")},
    data={"enable_validation": "false"},
)
print(f"Status: {resp3.status_code} (expected 400)")
print(resp3.json().get("detail", ""))

print("\n[DONE] All tests complete.")
