import subprocess
import re
import time
import os
from dotenv import load_dotenv
import requests

def update_vapi_assistant(url: str, api_key: str, assistant_id: str):
    print(f"\n[Tunnel Wrapper] Syncing new URL with Vapi Assistant: {assistant_id}...")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": {
            "provider": "custom-llm",
            "url": f"{url}/api/vapi/custom-llm",
            "model": "gpt-4o-mini"
        }
    }
    try:
        res = requests.patch(
            f"https://api.vapi.ai/assistant/{assistant_id}",
            json=payload,
            headers=headers
        )
        if res.status_code == 200:
            print("[Tunnel Wrapper] Successfully updated Vapi Assistant URL in the cloud!")
        else:
            print(f"[Tunnel Wrapper] Failed to update Vapi Assistant (Status {res.status_code}): {res.text}")
            
        # Also sync phone numbers assigned to this assistant
        print("[Tunnel Wrapper] Fetching phone numbers to update server webhooks...")
        phone_res = requests.get("https://api.vapi.ai/phone-number", headers=headers)
        if phone_res.status_code == 200:
            phone_numbers = phone_res.json()
            for p in phone_numbers:
                if p.get("assistantId") == assistant_id:
                    num_id = p.get("id")
                    num_str = p.get("number")
                    print(f"[Tunnel Wrapper] Syncing URL for Phone Number {num_str} ({num_id})...")
                    phone_payload = {
                        "server": {
                            "url": f"{url}/api/vapi/custom-llm",
                            "timeoutSeconds": 20,
                            "headers": {
                                "Bypass-Tunnel-Reminder": "true"
                            }
                        }
                    }
                    patch_res = requests.patch(
                        f"https://api.vapi.ai/phone-number/{num_id}",
                        json=phone_payload,
                        headers=headers
                    )
                    if patch_res.status_code == 200:
                        print(f"[Tunnel Wrapper] Successfully updated Phone Number {num_str} server URL!")
                    else:
                        print(f"[Tunnel Wrapper] Failed to update Phone Number {num_str}: {patch_res.text}")
        else:
            print(f"[Tunnel Wrapper] Failed to fetch phone numbers: {phone_res.text}")
    except Exception as e:
        print(f"[Tunnel Wrapper] Error calling Vapi API: {e}")


def main():
    # Load env keys from .env
    script_dir = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(script_dir, ".env"))
    
    port = 8000
    print(f"Starting localtunnel wrapper for port {port}...")
    
    # We run 'npx -y localtunnel --port 8000' using cmd.exe on Windows
    cmd = ["cmd.exe", "/c", f"npx -y localtunnel --port {port}"]
    
    # File to save the active tunnel URL
    tunnel_file = os.path.join(script_dir, "tunnel_url.txt")
    
    # Clean up old file on startup
    if os.path.exists(tunnel_file):
        try:
            os.remove(tunnel_file)
        except Exception:
            pass

    while True:
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            print("[Tunnel Wrapper] Spawned localtunnel process.")
            
            # Read stdout line by line
            for line in process.stdout:
                print(line, end="")
                # Look for "your url is: https://..."
                match = re.search(r"your url is:\s*(https?://[^\s]+)", line)
                if match:
                    url = match.group(1).strip()
                    print(f"\n[Tunnel Wrapper] Detected tunnel URL: {url}")
                    with open(tunnel_file, "w", encoding="utf-8") as f:
                        f.write(url)
                    print(f"[Tunnel Wrapper] Saved URL to {tunnel_file}")
                    
                    # Auto-sync with Vapi if keys exist
                    api_key = os.getenv("VAPI_API_KEY")
                    assistant_id = os.getenv("VAPI_ASSISTANT_ID")
                    if api_key and assistant_id:
                        update_vapi_assistant(url, api_key, assistant_id)
                    else:
                        print("[Tunnel Wrapper] VAPI_API_KEY or VAPI_ASSISTANT_ID not set in .env. Skipping cloud sync.")
                    
            process.wait()
            print("[Tunnel Wrapper] localtunnel process exited. Restarting in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            print(f"[Tunnel Wrapper] Error occurred: {e}. Retrying in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    main()

