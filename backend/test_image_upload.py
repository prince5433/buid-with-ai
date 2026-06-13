import requests
import os
from io import BytesIO
from PIL import Image

# Create a dummy image
img = Image.new('RGB', (100, 100), color = 'red')
img_byte_arr = BytesIO()
img.save(img_byte_arr, format='PNG')
img_byte_arr.seek(0)

# Upload it
url = "http://localhost:8000/api/upload"
files = {'files': ('test.png', img_byte_arr, 'image/png')}
response = requests.post(url, files=files)

print("Status Code:", response.status_code)
print("Response:", response.text)
