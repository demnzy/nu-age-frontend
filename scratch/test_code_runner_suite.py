import sys, os
sys.path.insert(0, os.path.abspath("."))

from src.utils.code_runner import run_code_lab_tests, execute_remote_code, execute_python, execute_sql

# 1. Test C++ CodeLab
cpp_code = """
#include <iostream>
int main() {
    int n;
    if (std::cin >> n) {
        std::cout << n * 2;
    } else {
        std::cout << "No input";
    }
    return 0;
}
"""
test_cases_cpp = [
    {"description": "Double 5", "input": "5", "expected_output": "10"},
    {"description": "Double 21", "input": "21", "expected_output": "42"},
]

print("=== Running C++ Tests ===")
cpp_res = run_code_lab_tests("cpp", cpp_code, "", test_cases_cpp)
for r in cpp_res:
    print(f"[{'PASS' if r['passed'] else 'FAIL'}] {r['description']} -> Actual: {repr(r['actual'])} (Expected: {repr(r['expected'])}) Error: {r['error']}")

# 2. Test Python CodeLab
py_code = """
n = int(input())
print(n * 2)
"""
test_cases_py = [
    {"description": "Py Double 5", "input": "5", "expected_output": "10"},
    {"description": "Py Double 21", "input": "21", "expected_output": "42"},
]
print("\n=== Running Python Tests ===")
py_res = run_code_lab_tests("python", py_code, "", test_cases_py)
for r in py_res:
    print(f"[{'PASS' if r['passed'] else 'FAIL'}] {r['description']} -> Actual: {repr(r['actual'])} (Expected: {repr(r['expected'])}) Error: {r['error']}")

# 3. Test SQLite CodeLab
sql_setup = "CREATE TABLE students (id INT, name TEXT, grade INT); INSERT INTO students VALUES (1, 'Alice', 95), (2, 'Bob', 80);"
sql_code = "SELECT name FROM students WHERE grade >= 90;"
test_cases_sql = [
    {"description": "Honor Roll Query", "expected_output": "Alice"},
]
print("\n=== Running SQLite Tests ===")
sql_res = run_code_lab_tests("sql", sql_code, sql_setup, test_cases_sql)
for r in sql_res:
    print(f"[{'PASS' if r['passed'] else 'FAIL'}] {r['description']} -> Actual: {repr(r['actual'])} (Expected: {repr(r['expected'])}) Error: {r['error']}")
