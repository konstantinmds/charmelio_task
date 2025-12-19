#!/usr/bin/env python3
"""
End-to-end demo script for the Contract Clause Extractor.

Prerequisites:
    1. Docker services running: make up
    2. Services healthy: make healthcheck
    3. OPENAI_API_KEY set in .env

Usage:
    python scripts/e2e_demo.py

    # With a custom PDF:
    python scripts/e2e_demo.py --file path/to/contract.pdf

    # Output raw JSON:
    python scripts/e2e_demo.py --json
"""

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

# Configuration
API_BASE = "http://localhost:8000"
DEFAULT_PDF = "sample_contracts/DELACE (PTY) LTD-Sales - RoW Non-Disclosure Agreement (NDA) (091123).pdf"
POLL_INTERVAL = 3  # seconds
MAX_WAIT = 120  # seconds


def check_health(client: httpx.Client) -> bool:
    """Check if API is healthy."""
    try:
        resp = client.get(f"{API_BASE}/health")
        return resp.status_code == 200
    except httpx.RequestError:
        return False


def check_readiness(client: httpx.Client) -> dict:
    """Check readiness of all dependencies."""
    try:
        resp = client.get(f"{API_BASE}/health/ready")
        return resp.json()
    except httpx.RequestError as e:
        return {"error": str(e)}


def upload_pdf(client: httpx.Client, file_path: Path) -> dict:
    """Upload a PDF and start extraction."""
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "application/pdf")}
        resp = client.post(f"{API_BASE}/api/extract", files=files)
        resp.raise_for_status()
        return resp.json()


def get_extraction(client: httpx.Client, document_id: str) -> dict:
    """Get extraction result for a document."""
    resp = client.get(f"{API_BASE}/api/extractions/{document_id}")
    if resp.status_code == 404:
        return {"status": "pending"}
    resp.raise_for_status()
    return resp.json()


def list_extractions(client: httpx.Client, page: int = 1, page_size: int = 10) -> dict:
    """List all extractions with pagination."""
    resp = client.get(f"{API_BASE}/api/extractions", params={"page": page, "page_size": page_size})
    resp.raise_for_status()
    return resp.json()


def poll_until_complete(client: httpx.Client, document_id: str, max_wait: int = MAX_WAIT) -> dict:
    """Poll for extraction completion."""
    start = time.time()
    while time.time() - start < max_wait:
        result = get_extraction(client, document_id)
        status = result.get("status", "pending")

        if status == "completed":
            return result
        elif status == "failed":
            return result

        elapsed = int(time.time() - start)
        print(f"  Status: {status} ({elapsed}s elapsed)", end="\r")
        time.sleep(POLL_INTERVAL)

    return {"status": "timeout", "error": f"Exceeded {max_wait}s wait time"}


def print_extraction_result(data: dict) -> None:
    """Pretty print extraction results."""
    result = data.get("extraction_result", {})

    print("\n" + "=" * 60)
    print("EXTRACTION RESULTS")
    print("=" * 60)

    # Summary
    if result.get("summary"):
        print(f"\nSummary: {result['summary']}")

    # Confidence
    if result.get("confidence"):
        print(f"Confidence: {result['confidence']:.0%}")

    # Parties
    parties = result.get("parties", {})
    if parties:
        print("\n--- Parties ---")
        print(f"  Party One: {parties.get('party_one', 'N/A')}")
        print(f"  Party Two: {parties.get('party_two', 'N/A')}")
        if parties.get("additional_parties"):
            print(f"  Additional: {', '.join(parties['additional_parties'])}")

    # Dates
    dates = result.get("dates", {})
    if dates:
        print("\n--- Dates ---")
        print(f"  Effective Date: {dates.get('effective_date', 'N/A')}")
        print(f"  Termination Date: {dates.get('termination_date', 'N/A')}")
        print(f"  Term Length: {dates.get('term_length', 'N/A')}")

    # Clauses
    clauses = result.get("clauses", {})
    if clauses:
        print("\n--- Clauses ---")
        for key, value in clauses.items():
            if value:
                # Truncate long values
                display = value[:200] + "..." if len(str(value)) > 200 else value
                print(f"  {key.replace('_', ' ').title()}: {display}")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description="E2E demo for Contract Clause Extractor")
    parser.add_argument("--file", "-f", type=Path, help="Path to PDF file")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    # Determine PDF path
    script_dir = Path(__file__).parent.parent
    pdf_path = args.file or script_dir / DEFAULT_PDF

    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}")
        sys.exit(1)

    print("=" * 60)
    print("CONTRACT CLAUSE EXTRACTOR - E2E DEMO")
    print("=" * 60)

    with httpx.Client(timeout=30.0) as client:
        # Step 1: Health check
        print("\n[1/6] Checking API health...")
        if not check_health(client):
            print("  Error: API is not responding. Run 'make up' first.")
            sys.exit(1)
        print("  API is healthy")

        # Step 2: Readiness check
        print("\n[2/6] Checking service readiness...")
        readiness = check_readiness(client)
        if "error" in readiness:
            print(f"  Error: {readiness['error']}")
            sys.exit(1)

        # Handle nested response: {"status": "ok", "checks": {"database": "ok", ...}}
        checks = readiness.get("checks", readiness)
        for service, status in checks.items():
            icon = "OK" if status == "ok" else "FAIL"
            print(f"  {service}: {icon}")

        if readiness.get("status") != "ok":
            print("  Error: Not all services are ready")
            sys.exit(1)

        # Step 3: Upload PDF
        print(f"\n[3/6] Uploading PDF: {pdf_path.name}")
        try:
            upload_result = upload_pdf(client, pdf_path)
            document_id = upload_result["document_id"]
            print(f"  Document ID: {document_id}")
            print(f"  Status: {upload_result['status']}")
        except httpx.HTTPStatusError as e:
            print(f"  Error uploading: {e.response.text}")
            sys.exit(1)

        # Step 4: Poll for completion
        print(f"\n[4/6] Waiting for extraction (max {MAX_WAIT}s)...")
        result = poll_until_complete(client, document_id)

        status = result.get("status")
        if status == "failed":
            print(f"  Extraction failed: {result.get('error_message', 'Unknown error')}")
            sys.exit(1)
        elif status == "timeout":
            print(f"  Timed out waiting for extraction")
            sys.exit(1)

        print("  Extraction completed!              ")

        # Step 5: Test GET /api/extractions/{document_id}
        print(f"\n[5/6] Testing GET /api/extractions/{document_id[:8]}...")
        try:
            single_result = get_extraction(client, document_id)
            if single_result.get("status") == "completed":
                print(f"  Endpoint works!")
                print(f"  Extraction ID: {single_result.get('extraction_id')}")
                print(f"  Model Used: {single_result.get('model_used')}")
            else:
                print(f"  Unexpected status: {single_result.get('status')}")
        except httpx.HTTPStatusError as e:
            print(f"  Error: {e.response.text}")
            sys.exit(1)

        # Step 6: Test GET /api/extractions (list)
        print("\n[6/6] Testing GET /api/extractions (list)...")
        try:
            list_result = list_extractions(client, page=1, page_size=5)
            total = list_result.get("total", 0)
            items = list_result.get("items", [])
            print(f"  Endpoint works!")
            print(f"  Total extractions: {total}")
            print(f"  Items on page 1: {len(items)}")

            # Verify our extraction is in the list
            our_extraction = next(
                (item for item in items if item.get("document_id") == document_id),
                None
            )
            if our_extraction:
                print(f"  Our extraction found in list!")
            else:
                print(f"  Note: Our extraction not on first page (may be on later page)")
        except httpx.HTTPStatusError as e:
            print(f"  Error: {e.response.text}")
            sys.exit(1)

    # Final output
    print("\n" + "=" * 60)
    print("ALL ENDPOINTS TESTED SUCCESSFULLY!")
    print("=" * 60)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print_extraction_result(result)

        # Also show metadata
        print(f"Document ID: {result.get('document_id')}")
        print(f"Extraction ID: {result.get('extraction_id')}")
        print(f"Model Used: {result.get('model_used')}")
        print(f"Created At: {result.get('created_at')}")

    sys.exit(0)


if __name__ == "__main__":
    main()
