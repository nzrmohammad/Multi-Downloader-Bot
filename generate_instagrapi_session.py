# generate_instagrapi_session.py
import os
import getpass
from instagrapi import Client

# --- تنظیمات ---
proxy = "socks5h://127.0.0.1:2000"
username = input("Enter Instagram username: ")
password = getpass.getpass("Enter Instagram password: ")
verification_code = input("If 2FA is enabled, enter code now (or press Enter): ")
session_filename = f"{username}.json"

cl = Client()
cl.set_proxy(proxy)
print(f"[*] Using proxy: {proxy}")

try:
    print(f"[*] Logging in as {username}...")
    if verification_code:
        cl.login(username, password, verification_code=verification_code)
    else:
        cl.login(username, password)
    
    # ذخیره تنظیمات کامل (شامل نشست) در یک فایل JSON
    cl.dump_settings(session_filename)
    print("\n" + "="*50)
    print(f"✅ Session file saved successfully as '{session_filename}'")
    print("💡 You can now run the main bot.")
    print("="*50)

except Exception as e:
    print("\n" + "="*50)
    print("❌ An error occurred during login:")
    print(f"   Error details: {e}")
    print("="*50)