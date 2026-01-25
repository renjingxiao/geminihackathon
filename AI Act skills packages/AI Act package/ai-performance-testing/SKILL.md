---
name: ai-performance-testing
description: An AI tool to define and measure factual accuracy (>95% correct citations), completeness (>90% complete answers), and consistency (>85% consistency score) of AI systems.
---

# AI Performance Testing Skill

This skill provides a structured workflow for performance testing of AI systems, focusing on factual accuracy, completeness, and consistency. It leverages the Deepeval framework to measure the performance of LLM-based systems.

## Workflow for AI Performance Testing

Follow these steps to conduct comprehensive AI performance testing:

Remind: you should create new files instead of modify template
Remind: you should use local existing venv instead of directly create one
Remind: you should only modify the tested model, do not change any config for the testing process/models

1.  **Generate Test Data:**
    *   **Objective:** Create a dataset for testing the AI system.
    *   **Action:** Use the `template/data_generator.py` script to generate test data. You may need to ask the user for a data source to integrate. The output data file should be appropriately named for the test run.
    *   **Verification:** A test data file is created and available for the performance test.

2.  **Set up the Target LLM-based System:**
    *   **Objective:** Integrate the LLM-based system to be tested with the Deepeval framework.
    *   **Action:** Configure the `template/performance_test.py` script to connect to the target LLM system. This may involve setting API keys, model names, and other parameters.
    *   **Verification:** The setup is complete and the system is ready for testing.

3.  **Execute Performance Tests:**
    *   **Objective:** Run the performance tests to measure the system's factual accuracy, completeness, and consistency.
    *   **Action:** Execute the `template/performance_test.py` script. The script will use the generated test data to query the LLM system and evaluate its responses against the defined metrics.
    *   **Verification:** The test script runs successfully and outputs the performance metrics.

4.  **Generate Performance Report:**
    *   **Objective:** Create a structured report summarizing the test findings.
    *   **Action:** Process the test results to generate a markdown-formatted report that includes detailed outcomes for accuracy, completeness, and consistency.
    *   **Verification:** Ensure the report is comprehensive, accurate, and saved as a `.md` file in an accessible location.