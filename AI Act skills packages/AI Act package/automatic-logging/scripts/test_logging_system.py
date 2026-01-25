"""
Unit Tests for Article 12 Automatic Logging System.
Uses mock data to verify all features.
"""
import os
import sys
import time
import shutil
import unittest
from datetime import datetime, timedelta
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import (
    hash_text, generate_uuid, ensure_csvs_initialized,
    consolidate_to_excel, OPERATIONAL_CSV, RISK_CSV,
    OUTPUT_DIR, CAPABILITY_CSV, BIOMETRIC_CSV
)
from logger import ComplianceLogger, log_interaction, get_logger
from watchdog import (
    check_latency, check_frequency, check_operation,
    reset_frequency_tracker, LATENCY_THRESHOLD_SECONDS
)


class TestUtils(unittest.TestCase):
    """Test utility functions."""
    
    def test_hash_text_consistency(self):
        """Verify SHA-256 produces consistent hashes."""
        text = "Hello, World!"
        hash1 = hash_text(text)
        hash2 = hash_text(text)
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 64)  # SHA-256 = 64 hex chars
    
    def test_hash_text_empty(self):
        """Empty text returns empty hash."""
        self.assertEqual(hash_text(""), "")
    
    def test_generate_uuid_unique(self):
        """UUIDs should be unique."""
        ids = [generate_uuid() for _ in range(100)]
        self.assertEqual(len(set(ids)), 100)
    
    def test_ensure_csvs_initialized(self):
        """CSVs should be created with headers."""
        ensure_csvs_initialized()
        self.assertTrue(OPERATIONAL_CSV.exists())
        self.assertTrue(RISK_CSV.exists())


class TestLogger(unittest.TestCase):
    """Test the ComplianceLogger."""
    
    @classmethod
    def setUpClass(cls):
        """Initialize logger once."""
        cls.logger = ComplianceLogger(system_version="test-1.0.0")
    
    def test_log_operation(self):
        """Log a normal operation."""
        start = datetime.now()
        time.sleep(0.1)
        end = datetime.now()
        
        log_id = self.logger.log_operation(
            input_text="Test input",
            output_text="Test output",
            start_time=start,
            end_time=end
        )
        
        self.assertIsNotNone(log_id)
        self.assertEqual(len(log_id), 36)  # UUID length
    
    def test_log_risk(self):
        """Log a risk event."""
        log_id = self.logger.log_risk(
            event_type="Risk",
            risk_category="Test Category",
            description="Test risk description",
            action_taken="Test action"
        )
        
        self.assertIsNotNone(log_id)


class TestWatchdog(unittest.TestCase):
    """Test the AI Watchdog."""
    
    def setUp(self):
        """Reset tracker before each test."""
        reset_frequency_tracker()
        self.logger = ComplianceLogger(system_version="watchdog-test")
    
    def test_latency_normal(self):
        """Normal latency should not trigger alert."""
        start = datetime.now()
        end = start + timedelta(seconds=1)
        
        result = check_latency(start, end, None)
        self.assertFalse(result)
    
    def test_latency_high(self):
        """High latency should trigger alert."""
        start = datetime.now()
        end = start + timedelta(seconds=6)  # > 5s threshold
        
        result = check_latency(start, end, self.logger)
        self.assertTrue(result)
    
    def test_frequency_normal(self):
        """Normal frequency should not trigger alert."""
        reset_frequency_tracker()
        result = check_frequency(None)
        self.assertFalse(result)
    
    def test_frequency_high(self):
        """High frequency should trigger alert."""
        reset_frequency_tracker()
        
        # Simulate 10 rapid calls
        for _ in range(10):
            result = check_frequency(self.logger)
        
        # The 10th call should trigger
        self.assertTrue(result)


class TestDecorator(unittest.TestCase):
    """Test the @log_interaction decorator."""
    
    def test_decorator_basic(self):
        """Decorator should log function calls."""
        reset_frequency_tracker()
        
        @log_interaction(system_version="decorator-test")
        def mock_ai_function(user_input: str) -> str:
            return f"Response to: {user_input}"
        
        result = mock_ai_function("Hello AI")
        self.assertEqual(result, "Response to: Hello AI")


class TestConsolidation(unittest.TestCase):
    """Test Excel consolidation."""
    
    def test_consolidate_to_excel(self):
        """All CSVs should consolidate into one Excel."""
        ensure_csvs_initialized()
        
        # Add some test data
        logger = ComplianceLogger(system_version="consolidation-test")
        logger.log_operation("test", "test", datetime.now(), datetime.now())
        logger.log_risk("Test", "Test", "Test consolidation", "None")
        
        # Consolidate
        excel_path = consolidate_to_excel()
        
        self.assertTrue(Path(excel_path).exists())
        
        # Verify sheets
        import openpyxl
        wb = openpyxl.load_workbook(excel_path)
        sheet_names = wb.sheetnames
        
        self.assertIn("1. Capability Checklist", sheet_names)
        self.assertIn("2. Operational Logs", sheet_names)
        self.assertIn("3. Risk & Incident Logs", sheet_names)
        self.assertIn("4. Biometric Specifics", sheet_names)


class TestAuditor(unittest.TestCase):
    """Test the AI Auditor (requires API key)."""
    
    def test_auditor_with_mock_data(self):
        """Test auditor generates a report."""
        # Skip if no API key
        if not os.getenv("GEMINI_API_KEY"):
            self.skipTest("GEMINI_API_KEY not set")
        
        from auditor import audit_logs
        
        # Add some mock risk data first
        logger = ComplianceLogger(system_version="auditor-test")
        for i in range(5):
            logger.log_risk(
                event_type="Risk",
                risk_category="Test Category",
                description=f"Mock risk event {i}",
                action_taken="None"
            )
        
        # Run auditor
        report_path = audit_logs(n_risk=10, n_ops=10)
        
        self.assertTrue(Path(report_path).exists())
        
        # Check report content
        content = Path(report_path).read_text()
        self.assertIn("Compliance", content)


def run_all_tests():
    """Run all tests and keep outputs."""
    print("=" * 60)
    print("Article 12 Automatic Logging System - Unit Tests")
    print("=" * 60)
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Run tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestUtils))
    suite.addTests(loader.loadTestsFromTestCase(TestLogger))
    suite.addTests(loader.loadTestsFromTestCase(TestWatchdog))
    suite.addTests(loader.loadTestsFromTestCase(TestDecorator))
    suite.addTests(loader.loadTestsFromTestCase(TestConsolidation))
    suite.addTests(loader.loadTestsFromTestCase(TestAuditor))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 60)
    print("OUTPUTS GENERATED:")
    print("=" * 60)
    
    for f in OUTPUT_DIR.iterdir():
        print(f"  - {f.name}")
    
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print("ALL TESTS PASSED!")
    else:
        print(f"FAILED: {len(result.failures)} failures, {len(result.errors)} errors")
    print("=" * 60)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
