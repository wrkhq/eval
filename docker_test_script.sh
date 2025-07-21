#!/bin/bash
# Don't exit on error - we want to capture results even if tests fail
# set -e

REPO_NAME=$1
RESULTS_DIR="/workspace/results"
CURRENT_REPO="/workspace/current_repo"
TEST_SCRIPTS="/workspace/test_scripts"

echo "Starting test execution for repository: $REPO_NAME"
echo "Current directory contents:"
ls -la $CURRENT_REPO

# Copy test scripts
echo "Copying test scripts..."
cp $TEST_SCRIPTS/test_runner.py $CURRENT_REPO/
cp $TEST_SCRIPTS/test.py $CURRENT_REPO/

# Change to repository directory
cd $CURRENT_REPO

# Install required packages (suppress output)
echo "Installing test dependencies..."
pip install pytest pytest-json-report >/dev/null 2>&1

# Run tests
echo "Running tests..."
python test_runner.py
TEST_EXIT_CODE=$?

# Copy results
echo "Checking for results files..."
if [ -f "test_results.json" ]; then
    echo "Copying test_results.json to results directory..."
    cp test_results.json $RESULTS_DIR/${REPO_NAME}_results.json
    echo "Results successfully copied to ${REPO_NAME}_results.json"
elif [ -f "results.json" ]; then
    echo "Copying results.json to results directory..."
    cp results.json $RESULTS_DIR/${REPO_NAME}_results.json
    echo "Results successfully copied to ${REPO_NAME}_results.json"
else
    echo "No results file found, creating minimal error result..."
    echo '{"passed": 0, "failed": 1, "total": 1, "error": "No results file generated"}' > $RESULTS_DIR/${REPO_NAME}_results.json
fi

echo "Test execution completed with exit code: $TEST_EXIT_CODE"
exit $TEST_EXIT_CODE
