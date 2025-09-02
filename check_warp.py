# check_warp.py
import requests

# پراکسی SOCKS5 که توسط WARP/Hiddify ارائه می‌شود
# نیازمند نصب requests[socks] است: pip install requests[socks]
PROXY = "socks5h://127.0.0.1:2000"
proxies = {"http": PROXY, "https": PROXY}

# سایتی که IP شما را برمی‌گرداند
IP_CHECK_URL = "https://api.ipify.org?format=json"

print(f"[*] در حال تست پراکسی SOCKS5 در آدرس: {PROXY}")

try:
    response = requests.get(IP_CHECK_URL, proxies=proxies, timeout=15)
    response.raise_for_status()
    ip_address = response.json()["ip"]
    print("\n" + "="*50)
    print("✅ نتیجه: موفق!")
    print(f"💡 پراکسی WARP شما به درستی کار می‌کند. IP مشاهده شده: {ip_address}")
    print("   این یعنی مشکل از پراکسی نیست، بلکه اینستاگرام این IP را مسدود کرده است.")
    print("="*50)

except Exception as e:
    print("\n" + "="*50)
    print("❌ نتیجه: ناموفق!")
    print("   دلیل: امکان اتصال از طریق پراکسی WARP وجود ندارد.")
    print(f"   جزئیات خطا: {e}")
    print("\n💡 لطفاً از صحت عملکرد WARP و Hiddify روی سرور خود مطمئن شوید.")
    print("="*50)