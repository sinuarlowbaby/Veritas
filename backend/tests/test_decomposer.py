import asyncio
import json
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from httpx import ASGITransport, AsyncClient
from app.main import app

TEST_HEADLINES = [
    (
        "Headline 1 (Health misinformation + attribution + statistic)",
        "WHO officially confirms green tea cures COVID-19 in 48 hours, saving 50,000 lives in India last month",
    ),
    (
        "Headline 2 (Policy rumor + date + fiscal impact)",
        "Finance Ministry eliminates all income tax for citizens over 60 starting April 1, causing Rs 40,000 crore revenue loss",
    ),
    (
        "Headline 3 (Viral forward + causality + geographic claim)",
        "Government orders immediate ban on 5G mobile towers because radiation caused mysterious bird deaths in Delhi",
    ),
]


async def run_isolation_tests():
    print("=" * 80)
    print("VERITAS CLAIM DECOMPOSER - ISOLATION ENDPOINT TEST")
    print("=" * 80)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        # Check health first
        health_resp = await client.get("/health")
        print(f"\n[GET /health] Status: {health_resp.status_code}")
        print(f"Payload: {health_resp.json()}\n")

        # Test each composite headline against /api/decompose
        for title, raw_input in TEST_HEADLINES:
            print("-" * 80)
            print(f"TEST CASE: {title}")
            print(f"RAW INPUT: \"{raw_input}\"")
            print("-" * 80)

            response = await client.post(
                "/api/decompose",
                json={"text": raw_input},
                timeout=30.0,
            )

            if response.status_code == 200:
                data = response.json()
                print(f"STATUS: {response.status_code} OK")
                print(f"TOTAL SUB-CLAIMS EXTRACTED: {data['total_sub_claims']}")
                print("\nATOMIC SUB-CLAIMS:")
                for item in data["sub_claims"]:
                    print(f"  [{item['id']}] ({item['type']}):")
                    print(f"    --> {item['text']}")
                print()
            else:
                print(f"ERROR: {response.status_code} - {response.text}")

    print("=" * 80)
    print("ALL DECOMPOSER ISOLATION TESTS COMPLETED SUCCESSFULLY.")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_isolation_tests())
