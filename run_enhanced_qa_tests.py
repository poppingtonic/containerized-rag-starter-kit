#!/usr/bin/env python3
"""
Simple test runner for QA System
Usage: python run_enhanced_qa_tests.py [test_name]
"""

import sys
from test_enhanced_qa_system import QATestSuite

def main():
    test_suite = QATestSuite()
    
    if len(sys.argv) > 1:
        test_name = sys.argv[1].lower()
        
        # Map test names to methods
        test_map = {
            "complex": test_suite.test_query_complex,
            "subquestions": test_suite.test_subquestion_generation,
            "verify": test_suite.test_answer_verification,
            "comparison": test_suite.test_standard_vs_advanced_comparison,
            "health": test_suite.test_enhanced_query_health_policy,
            "agriculture": test_suite.test_enhanced_query_agricultural_technology,
            "security": test_suite.test_security_prompt_injection,
            "economic": test_suite.test_enhanced_query_economic_impact,
            "false": test_suite.test_verification_false_answer
        }
        
        if test_name in test_map:
            print(f"Running single test: {test_name}")
            test_map[test_name]()
            test_suite.print_summary()
        else:
            print("Available tests:")
            for name in test_map.keys():
                print(f"  - {name}")
    else:
        print("Running all tests...")
        test_suite.run_all_tests()

if __name__ == "__main__":
    main()