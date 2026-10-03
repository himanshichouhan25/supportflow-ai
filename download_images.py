import urllib.request
import os

images = {
    "philips-hd9200.jpg": "https://www.domesticappliances.philips.co.in/cdn/shop/files/HD9200_90.jpg?v=1788253098&width=900",
    "syska-led-bulb-9w.jpg": "https://tiimg.tistatic.com/fp/1/007/013/syska-rgb-multicolor-wifi-9w-led-bulb-911.jpg"
}

out_dir = r"d:\PROJECTS\ai-customer-support-agent\frontend\assets\products"
os.makedirs(out_dir, exist_ok=True)

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

for name, url in images.items():
    path = os.path.join(out_dir, name)
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            with open(path, 'wb') as f:
                f.write(response.read())
        print(f"Downloaded: {name}")
    except Exception as e:
        print(f"Failed {name}: {e}")
