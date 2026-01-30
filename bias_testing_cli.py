#!/usr/bin/env python3
"""
Bias Testing CLI - EU AI Act Article 10 & 27
Command-line interface for bias testing and monitoring.

Usage:
    python bias_testing_cli.py test --data test_data.json
    python bias_testing_cli.py detect --text "text to check"
    python bias_testing_cli.py report
    python bias_testing_cli.py demo
"""

import sys
import json
import argparse
from pathlib import Path

from bias_testing import (
    BiasTestingSystem,
    ProtectedAttribute,
    BiasSeverity
)


def cmd_test(args):
    """Run demographic bias test"""
    system = BiasTestingSystem(ai_system_id=args.system_id)

    if args.data:
        # Load test data from JSON
        with open(args.data, 'r') as f:
            data = json.load(f)
        predictions = data['predictions']
        labels = data['labels']
        protected_attr = data['protected_attribute']
        attr_type = ProtectedAttribute(data.get('attribute_type', 'gender'))
    else:
        print("Error: --data required")
        return 1

    result = system.run_demographic_test(
        predictions=predictions,
        labels=labels,
        protected_attr=protected_attr,
        attribute_type=attr_type
    )

    print(f"\nTest ID: {result.test_id}")
    print(f"Attribute: {result.protected_attribute.value}")
    print(f"Disparate Impact: {result.metrics.disparate_impact}")
    print(f"Compliant: {result.metrics.is_compliant()}")
    print(f"Severity: {result.severity.value}")

    print("\nFindings:")
    for finding in result.findings:
        print(f"  - {finding}")

    print("\nCorrective Actions:")
    for action in result.corrective_actions:
        print(f"  - {action}")

    return 0


def cmd_detect(args):
    """Detect bias in text output"""
    system = BiasTestingSystem(ai_system_id=args.system_id)

    if args.text:
        text = args.text
    elif args.file:
        with open(args.file, 'r') as f:
            text = f.read()
    else:
        print("Error: --text or --file required")
        return 1

    result = system.detect_output_bias(text)

    print(f"\nBias Detected: {result.bias_detected}")
    if result.bias_detected:
        print(f"Type: {result.bias_type}")
        print(f"Severity: {result.severity.value}")
        print(f"Problematic Phrases: {result.problematic_phrases}")
        print(f"Explanation: {result.explanation}")
        if result.suggested_alternatives:
            print("Suggested Alternatives:")
            for alt in result.suggested_alternatives:
                print(f"  - {alt}")

    return 0


def cmd_report(args):
    """Generate compliance report"""
    system = BiasTestingSystem(ai_system_id=args.system_id)
    system.load_history()

    report = system.generate_report(format=args.format)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"Report saved to: {args.output}")
    else:
        print(report)

    return 0


def cmd_demo(args):
    """Run demo with sample data"""
    print("Running Bias Testing Demo...")
    print("=" * 50)

    system = BiasTestingSystem(ai_system_id="DEMO-001", use_gemini=args.use_gemini)

    # Demo 1: Gender bias test
    print("\n[1] Demographic Bias Test (Gender)")
    print("-" * 40)

    predictions = [0.9, 0.85, 0.7, 0.65, 0.4, 0.35, 0.8, 0.3, 0.75, 0.25]
    labels =      [1,   1,    1,   0,    0,   0,    1,   0,   1,    0]
    gender =      ['M', 'M',  'M', 'M',  'M', 'F',  'F', 'F', 'F',  'F']

    result = system.run_demographic_test(
        predictions=predictions,
        labels=labels,
        protected_attr=gender,
        attribute_type=ProtectedAttribute.GENDER
    )

    print(f"Disparate Impact: {result.metrics.disparate_impact}")
    print(f"Equalized Odds: {result.metrics.equalized_odds}")
    print(f"Compliant: {result.metrics.is_compliant()}")
    print(f"Severity: {result.severity.value}")

    # Demo 2: Age bias test
    print("\n[2] Demographic Bias Test (Age)")
    print("-" * 40)

    age_groups = ['young', 'young', 'young', 'old', 'old', 'old', 'young', 'old']
    predictions2 = [0.9, 0.85, 0.8, 0.4, 0.35, 0.3, 0.75, 0.25]
    labels2 = [1, 1, 1, 0, 0, 0, 1, 0]

    result2 = system.run_demographic_test(
        predictions=predictions2,
        labels=labels2,
        protected_attr=age_groups,
        attribute_type=ProtectedAttribute.AGE
    )

    print(f"Disparate Impact: {result2.metrics.disparate_impact}")
    print(f"Compliant: {result2.metrics.is_compliant()}")

    # Demo 3: Output bias detection
    print("\n[3] Output Bias Detection")
    print("-" * 40)

    test_texts = [
        "The ideal candidate is a young, energetic male with no family commitments.",
        "All qualified applicants will be considered regardless of background.",
        "This position is not suitable for older workers."
    ]

    for text in test_texts:
        output_result = system.detect_output_bias(text)
        status = "BIAS" if output_result.bias_detected else "OK"
        print(f"\n\"{text[:60]}...\"")
        print(f"  -> {status}")
        if output_result.bias_detected:
            print(f"     Type: {output_result.bias_type}")

    # Generate report
    print("\n[4] Generating Report")
    print("-" * 40)

    report = system.generate_report()
    report_path = system.storage_dir / "demo_report.md"
    with open(report_path, 'w') as f:
        f.write(report)
    print(f"Report saved: {report_path}")

    print("\n" + "=" * 50)
    print("Demo complete.")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="EU AI Act Bias Testing CLI (Article 10 & 27)"
    )
    parser.add_argument(
        "--system-id",
        default="AI-SYSTEM-001",
        help="AI system identifier"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Test command
    test_parser = subparsers.add_parser("test", help="Run demographic bias test")
    test_parser.add_argument("--data", required=True, help="JSON file with test data")

    # Detect command
    detect_parser = subparsers.add_parser("detect", help="Detect bias in text")
    detect_parser.add_argument("--text", help="Text to analyze")
    detect_parser.add_argument("--file", help="File containing text to analyze")

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate compliance report")
    report_parser.add_argument("--format", default="markdown", choices=["markdown", "json"])
    report_parser.add_argument("--output", help="Output file path")

    # Demo command
    demo_parser = subparsers.add_parser("demo", help="Run demo with sample data")
    demo_parser.add_argument("--use-gemini", action="store_true", help="Use Gemini AI")

    args = parser.parse_args()

    if args.command == "test":
        return cmd_test(args)
    elif args.command == "detect":
        return cmd_detect(args)
    elif args.command == "report":
        return cmd_report(args)
    elif args.command == "demo":
        return cmd_demo(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
