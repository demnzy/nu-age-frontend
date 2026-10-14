import sys
import os
sys.path.insert(0, os.path.abspath("."))
from src.utils.code_runner import execute_python

code = """
name = input("What is your name? ")
print(name)
print(f"{name} Hello world")
"""

res1 = execute_python(code, test_input="")
print("=== Result without input ===")
print("Success:", res1["success"])
print("Output:\n" + res1["output"])
print("Error:", res1["error"])

res2 = execute_python(code, test_input="Alice")
print("=== Result with input ===")
print("Success:", res2["success"])
print("Output:\n" + res2["output"])
print("Error:", res2["error"])
