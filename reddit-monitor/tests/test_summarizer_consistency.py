"""
Consistency test for summarizer SKIP detection.
Runs each selftext N times and checks Mistral is stable:
  - trash inputs  → SKIP every time
  - normal inputs → never SKIP
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.summarizer import summarize

N = 5  # number of runs per selftext

TRASH = [
    # 1. Just a link post with no text
    "[link] [comments]",
    # 2. Navigation/metadata noise
    "submitted by /u/AutoModerator\n[link] [comments]\n• Posted by u/throwaway123",
]

NORMAL = [
    # 3. Real security post
    (
        "A critical vulnerability (CVE-2024-1234) was discovered in OpenSSH versions prior to 9.6. "
        "The flaw allows unauthenticated remote code execution via a heap overflow in the SSH key "
        "exchange handler. Patches are available upstream and all major Linux distributions have "
        "pushed updates. Users are advised to upgrade immediately or restrict SSH access via firewall rules."
    ),
    # 4. Tool release announcement
    (
        "We released Trivy v0.50 today. Major changes include: support for scanning SBOM files in "
        "CycloneDX format, improved detection of Go module vulnerabilities, and a new --ignore-policy "
        "flag for OPA-based filtering. The container image is available on Docker Hub. "
        "Full changelog: https://github.com/aquasecurity/trivy/releases/tag/v0.50.0"
    ),
    # 5. Discussion with real content
    (
        "I've been using Falco for runtime security monitoring in our Kubernetes cluster for about 6 months. "
        "Overall it works well for detecting unexpected syscalls and network connections, but the false "
        "positive rate on busy nodes is frustrating. We ended up writing custom rules to whitelist our "
        "CI workloads. Has anyone found a good strategy for tuning Falco rules without missing real threats?"
    ),
]

CASES = [
    {"label": "TRASH 1 - link only",         "text": TRASH[0],  "expect_skip": True},
    {"label": "TRASH 2 - metadata noise",    "text": TRASH[1],  "expect_skip": True},
    {"label": "NORMAL 1 - CVE advisory",     "text": NORMAL[0], "expect_skip": False},
    {"label": "NORMAL 2 - tool release",     "text": NORMAL[1], "expect_skip": False},
    {"label": "NORMAL 3 - community discussion", "text": NORMAL[2], "expect_skip": False},
]


def run():
    for case in CASES:
        label = case["label"]
        expect_skip = case["expect_skip"]
        skip_count = 0

        print(f"\n{'─' * 60}")
        print(f"  {label}  [expect: {'SKIP' if expect_skip else 'SUMMARY'}]")
        print(f"{'─' * 60}")

        for i in range(1, N + 1):
            result = summarize(case["text"])
            skipped = result is None
            if skipped:
                skip_count += 1
            tag = "SKIP" if skipped else "SUMMARY"
            preview = "" if skipped else f"  {result[:90]}..."
            print(f"  [{i}/{N}] {tag}{preview}")

        summary_count = N - skip_count
        print(f"  SKIP: {skip_count}/{N}  SUMMARY: {summary_count}/{N}")

    print()


if __name__ == "__main__":
    run()
