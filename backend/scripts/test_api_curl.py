import asyncio
import json
import sys
import time
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from httpx import ASGITransport, AsyncClient
from app.main import app
from app.services.nli_verifier import get_nli_verifier

DEMO_CLAIM = "WHO officially confirms green tea cures COVID-19 in 48 hours, saving 50,000 lives in India last month"


async def run_curl_simulation():
    print("=" * 85)
    print("       VERITAS API VERIFICATION ENDPOINT TEST (CURL SIMULATION)")
    print("=" * 85)
    print("Testing API lifecycle: Submit -> Pending Job ID -> Polling -> Completed JSON -> Caching Check")
    print("=" * 85)

    # Preload NLI Cross-Encoder model (as in lifespan)
    verifier = get_nli_verifier()
    verifier.load_model()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
        # -------------------------------------------------------------------
        # 1. First Submit: Fresh claim execution
        # -------------------------------------------------------------------
        print("\n[Step 1] Submitting claim via POST /api/verify...")
        t_start = time.perf_counter()
        submit_resp = await client.post(
            "/api/verify",
            json={"claim": DEMO_CLAIM, "generate_explanation": True},
        )
        print(f"HTTP Status: {submit_resp.status_code}")
        submit_data = submit_resp.json()
        print(f"Response Payload:\n{json.dumps(submit_data, indent=2)}\n")

        job_id = submit_data["job_id"]
        assert submit_data["status"] in ("pending", "processing", "queued")
        assert submit_data["cached"] is False
        print(f"--> Job Enqueued successfully! Job ID: {job_id}")

        # -------------------------------------------------------------------
        # 2. Polling GET /api/verify/{job_id} until completed
        # -------------------------------------------------------------------
        print(f"\n[Step 2] Polling GET /api/verify/{job_id}...")
        poll_count = 0
        final_job_data = None

        while True:
            poll_count += 1
            await asyncio.sleep(1.0)
            poll_resp = await client.get(f"/api/verify/{job_id}")
            poll_data = poll_resp.json()
            status_val = poll_data.get("status")
            stage_val = poll_data.get("stage")
            print(f"  Poll #{poll_count:02d} | Status: {status_val:<10} | Stage: {stage_val}")

            if status_val == "completed":
                final_job_data = poll_data
                break
            elif status_val == "failed":
                print(f"[ERROR] Job failed: {poll_data.get('error')}")
                return

            if poll_count >= 40:
                print("[ERROR] Polling timed out!")
                return

        elapsed_total = time.perf_counter() - t_start
        print(f"\n--> Verification completed in {elapsed_total:.2f}s (reported latency: {final_job_data.get('latency_ms')}ms)")
        print("\n" + "=" * 35 + " FULL UI JSON PAYLOAD " + "=" * 35)
        print(json.dumps(final_job_data, indent=2))
        print("=" * 85)

        # -------------------------------------------------------------------
        # 3. Second Submit: Instant Cache Hit Demo
        # -------------------------------------------------------------------
        print("\n[Step 3] Submitting IDENTICAL claim again to test Instant Caching...")
        t_cache_start = time.perf_counter()
        cache_submit_resp = await client.post(
            "/api/verify",
            json={"claim": DEMO_CLAIM},
        )
        t_cache_elapsed_ms = (time.perf_counter() - t_cache_start) * 1000
        cache_data = cache_submit_resp.json()

        print(f"HTTP Status: {cache_submit_resp.status_code}")
        print(f"Client Roundtrip Latency: {t_cache_elapsed_ms:.2f} ms")
        print(f"Cached Flag in Response  : {cache_data.get('cached')}")
        print(f"Job Status               : {cache_data.get('status')}")
        print(f"Reported Backend Latency : {cache_data.get('latency_ms')} ms")
        print(f"Verdict                  : {cache_data.get('result', {}).get('verdict')}")
        print(f"Confidence               : {cache_data.get('result', {}).get('confidence')}")

        assert cache_data["cached"] is True
        assert cache_data["status"] == "completed"
        assert t_cache_elapsed_ms < 100.0  # Delivered in milliseconds!
        print("\n--> Caching test PASSED! Second submission returned in milliseconds from SQLite jobs table.")

    print("\n" + "=" * 85)
    print("ALL API CURL SHAPE TESTS COMPLETED SUCCESSFULLY.")
    print("=" * 85)


if __name__ == "__main__":
    asyncio.run(run_curl_simulation())
