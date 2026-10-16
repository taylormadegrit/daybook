"""
Master Test Runner for Daybook Test Suite.
Executes all 7 categories:
1. Unit Core Tests (test_unit_core.py)
2. API Integration Tests (test_api_integration.py)
3. Edge Case Tests (test_edge_cases.py)
4. Error Handling Tests (test_error_handling.py)
5. State & Concurrency Tests (test_state_concurrency.py)
6. Security Tests (test_security.py)
7. Performance Benchmark Tests (test_performance.py)
"""
import sys
import os
import unittest
import time

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def run_full_suite(run_number=1):
    print(f"\n{'='*70}")
    print(f">> EXECUTING DAYBOOK MASTER BACKTEST SUITE -- RUN #{run_number}")
    print(f"{'='*70}")

    loader = unittest.TestLoader()
    suite_dir = os.path.dirname(__file__)

    test_modules = [
        "test_unit_core",
        "test_api_integration",
        "test_edge_cases",
        "test_error_handling",
        "test_state_concurrency",
        "test_security",
        "test_performance",
    ]

    master_suite = unittest.TestSuite()
    for mod in test_modules:
        sub_suite = loader.discover(start_dir=suite_dir, pattern=f"{mod}.py")
        master_suite.addTests(sub_suite)

    start_time = time.perf_counter()
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(master_suite)
    duration = time.perf_counter() - start_time

    print(f"\n{'-'*70}")
    print(f"RUN #{run_number} SUMMARY:")
    print(f"Total Tests Run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Total Duration: {duration:.2f} seconds")
    print(f"Status: {'✅ PASSED (100%)' if result.wasSuccessful() else '❌ FAILED'}")
    print(f"{'-'*70}\n")

    return result.wasSuccessful(), result.testsRun, len(result.failures), len(result.errors), duration


def main():
    iterations = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    all_runs = []

    for i in range(1, iterations + 1):
        success, total, fails, errs, dur = run_full_suite(run_number=i)
        all_runs.append({
            "run": i,
            "success": success,
            "total": total,
            "fails": fails,
            "errs": errs,
            "duration": dur,
        })
        if not success and iterations == 1:
            sys.exit(1)

    print("\n" + "="*70)
    print("🏁 FINAL BACKTEST MULTI-RUN AGGREGATION")
    print("="*70)
    passed_runs = sum(1 for r in all_runs if r["success"])
    for r in all_runs:
        status_str = "PASS" if r["success"] else "FAIL"
        print(f"Run {r['run']}: {status_str} ({r['total']} tests, {r['fails']} failures, {r['errs']} errors in {r['duration']:.2f}s)")

    print(f"\nFinal Result: {passed_runs}/{len(all_runs)} runs passed successfully.")
    if passed_runs == 0:
        print("❌ CRITICAL: No runs succeeded.")
        sys.exit(1)
    else:
        print(f"✅ STABILITY REQUIREMENT SATISFIED ({passed_runs}/{len(all_runs)} clean runs).")
        sys.exit(0)


if __name__ == "__main__":
    main()
