"""CLI test script to verify NPEI authentication and data retrieval.

Usage:
    python3 test_client.py <username> <password>
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
import json
import sys

from npei_api import NPEIClient


async def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python3 test_client.py <email/username> <password>")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]

    print(f"[*] Testing connection for user: {username}")
    client = NPEIClient(username=username, password=password)

    try:
        print("[*] 1. Authenticating against NPEI IAM API...")
        token = await client.authenticate()
        print(f"[+] Authentication successful! Token (first 20 chars): {token[:20]}...")

        print("[*] 2. Discovering customer, account, and service IDs...")
        account_info = await client.discover_account()
        print(f"[+] Account ID: {account_info.get('accountId')}")
        print(f"[+] Service ID: {account_info.get('serviceId')}")
        print(f"[+] Customer ID: {account_info.get('customerId')}")

        print("[*] 3. Checking Ontario Energy Season calculations...")
        season_info = client.get_season_info()
        print(f"[+] Season Info:\n{json.dumps(season_info, indent=2)}")

        print("[*] 4. Fetching Niagara Falls weather data (London Hydro shared services)...")
        today = date.today().isoformat()
        last_week = (date.today() - timedelta(days=7)).isoformat()
        weather = await client.get_weather(from_date=last_week, to_date=today, time_type="daily")
        if weather and "weather" in weather:
            records = weather["weather"]
            print(f"[+] Received {len(records)} weather records. Latest record:")
            print(json.dumps(records[-1] if records else {}, indent=2))
        else:
            print("[!] No weather data returned or empty response.")

        print("[*] 5. Testing usage retrieval for September 2026 (known populated month)...")
        usage = await client.get_usage(
            start_date="2026-09-01",
            end_date="2026-09-30",
            view="DAILY",
        )
        if usage:
            print(f"[+] Received {len(usage)} daily usage records!")
            print("[+] Sample day (Sept 1, 2026):")
            print(json.dumps(usage[0], indent=2))
        else:
            print("[!] No usage data returned for September 2026.")

        print("\n[SUCCESS] NPEI API Client is fully functional!")

    except Exception as err:
        print(f"\n[ERROR] Test failed: {err}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
