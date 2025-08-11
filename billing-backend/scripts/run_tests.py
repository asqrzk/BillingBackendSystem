#!/usr/bin/env python3
"""
Test Runner for Billing Backend System

This script runs unit tests for both subscription and payment services.
It provides options for running specific test categories and generating coverage reports.

Usage:
    python scripts/run_tests.py --help
    python scripts/run_tests.py --all                    # Run all tests
    python scripts/run_tests.py --subscription          # Run subscription service tests only
    python scripts/run_tests.py --payment               # Run payment service tests only
    python scripts/run_tests.py --coverage              # Run with coverage report
    python scripts/run_tests.py --security              # Run security tests only
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path


def run_command(command, cwd=None):
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return e.returncode, e.stdout, e.stderr


def run_subscription_tests(coverage=False, test_pattern=None):
    """Run subscription service tests."""
    print("🧪 Running Subscription Service Tests")
    print("=" * 50)
    
    os.chdir("subscription-service")
    
    # Base pytest command
    cmd = "python -m pytest"
    
    if coverage:
        cmd += " --cov=app --cov-report=term-missing --cov-report=html:htmlcov"
    
    if test_pattern:
        cmd += f" -k {test_pattern}"
    
    # Run tests
    returncode, stdout, stderr = run_command(cmd)
    
    print(stdout)
    if stderr:
        print("STDERR:", stderr)
    
    os.chdir("..")
    return returncode == 0


def run_payment_tests(coverage=False, test_pattern=None):
    """Run payment service tests."""
    print("💳 Running Payment Service Tests")
    print("=" * 50)
    
    os.chdir("payment-service")
    
    # Base pytest command
    cmd = "python -m pytest"
    
    if coverage:
        cmd += " --cov=app --cov-report=term-missing --cov-report=html:htmlcov"
    
    if test_pattern:
        cmd += f" -k {test_pattern}"
    
    # Run tests
    returncode, stdout, stderr = run_command(cmd)
    
    print(stdout)
    if stderr:
        print("STDERR:", stderr)
    
    os.chdir("..")
    return returncode == 0


def run_security_tests(coverage=False):
    """Run security-focused tests."""
    print("🔒 Running Security Tests")
    print("=" * 50)
    
    # Run security tests from both services
    subscription_success = run_subscription_tests(coverage, "security or webhook_security")
    payment_success = run_payment_tests(coverage, "security or webhook")
    
    return subscription_success and payment_success


def print_test_summary():
    """Print test suite summary."""
    print("\n" + "=" * 60)
    print("📊 Test Suite Summary")
    print("=" * 60)
    print("Current test coverage includes:")
    print("• Subscription Service: ~25+ unit tests")
    print("  - Subscription creation, cancellation, plan changes")
    print("  - Usage tracking with Redis atomic operations") 
    print("  - Webhook processing and idempotency")
    print("  - HMAC signature verification (security)")
    print("")
    print("• Payment Service: ~20+ unit tests")
    print("  - Payment processing with card validation")
    print("  - Transaction management and refunds")
    print("  - Gateway integration and error handling")
    print("  - Luhn algorithm validation (security)")
    print("")
    print("• Security Tests: ~15+ tests")
    print("  - HMAC-SHA256 signature generation/verification")
    print("  - Timestamp tolerance and replay protection")
    print("  - Constant-time comparison (timing attack protection)")
    print("  - Input validation and error handling")
    print("")
    print("🎯 Total: ~60+ unit tests covering critical business logic")
    print("📈 Focus: Core functionality that could break with code changes")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Run billing backend tests")
    
    # Test selection arguments
    parser.add_argument("--all", action="store_true", 
                       help="Run all tests for both services")
    parser.add_argument("--subscription", action="store_true",
                       help="Run subscription service tests only")
    parser.add_argument("--payment", action="store_true",
                       help="Run payment service tests only") 
    parser.add_argument("--security", action="store_true",
                       help="Run security tests only")
    
    # Options
    parser.add_argument("--coverage", action="store_true",
                       help="Generate coverage report")
    parser.add_argument("--pattern", type=str,
                       help="Run tests matching specific pattern")
    parser.add_argument("--summary", action="store_true",
                       help="Show test suite summary")
    
    args = parser.parse_args()
    
    # Check if we're in the right directory
    if not Path("subscription-service").exists() or not Path("payment-service").exists():
        print("❌ Error: This script must be run from the project root directory")
        print("Expected to find: subscription-service/ and payment-service/")
        sys.exit(1)
    
    print("🚀 Billing Backend Test Runner")
    print("=" * 60)
    
    if args.summary:
        print_test_summary()
        return
    
    # Determine what tests to run
    success = True
    
    if args.all or (not args.subscription and not args.payment and not args.security):
        # Run all tests
        print("Running all tests...\n")
        subscription_success = run_subscription_tests(args.coverage, args.pattern)
        print()
        payment_success = run_payment_tests(args.coverage, args.pattern)
        success = subscription_success and payment_success
        
    elif args.subscription:
        success = run_subscription_tests(args.coverage, args.pattern)
        
    elif args.payment:
        success = run_payment_tests(args.coverage, args.pattern)
        
    elif args.security:
        success = run_security_tests(args.coverage)
    
    # Print results
    print("\n" + "=" * 60)
    if success:
        print("✅ All tests PASSED!")
        if args.coverage:
            print("📊 Coverage reports generated in service directories")
    else:
        print("❌ Some tests FAILED!")
        sys.exit(1)
    
    print("\n💡 Tips:")
    print("• Run with --coverage to see test coverage")
    print("• Use --pattern to run specific tests")
    print("• Check htmlcov/index.html for detailed coverage report")
    print("• Run --security to focus on security-critical tests")


if __name__ == "__main__":
    main() 