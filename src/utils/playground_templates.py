"""
Multi-language starter templates, metadata, and language configurations
for the Nu-Age Coding Playground and Code Labs.
"""

LANGUAGES_METADATA = [
    {
        "id": "python",
        "name": "Python 3.12",
        "category": "Offline",
        "badge": "100% Offline",
        "icon": "CODE_ROUNDED",
        "color": "BLUE_400",
        "engine": "local_python",
        "ext": ".py",
        "description": "Local AST-safe execution. Supports OOP, classes, inheritance, dataclasses, and standard libraries.",
    },
    {
        "id": "sql",
        "name": "SQL (SQLite)",
        "category": "Offline",
        "badge": "100% Offline",
        "icon": "STORAGE_ROUNDED",
        "color": "TEAL_400",
        "engine": "local_sql",
        "ext": ".sql",
        "description": "In-memory SQLite database. Write schemas, insert records, and run queries with tabular results.",
    },
    {
        "id": "html",
        "name": "Web (HTML/CSS/JS)",
        "category": "Offline",
        "badge": "100% Offline",
        "icon": "HTML_ROUNDED",
        "color": "DEEP_ORANGE_400",
        "engine": "local_html",
        "ext": ".html",
        "description": "Live web markup & script sandbox with real-time browser preview.",
    },
    {
        "id": "cpp",
        "name": "C++ (GCC 9.2)",
        "category": "Cloud Sandbox",
        "badge": "Compiler",
        "icon": "TERMINAL_ROUNDED",
        "color": "CYAN_400",
        "engine": "remote",
        "ext": ".cpp",
        "description": "Modern C++ with STL vectors, algorithms, and high-speed container compilation.",
    },
    {
        "id": "c",
        "name": "C (GCC 9.2)",
        "category": "Cloud Sandbox",
        "badge": "Compiler",
        "icon": "TERMINAL_ROUNDED",
        "color": "BLUE_GREY_400",
        "engine": "remote",
        "ext": ".c",
        "description": "Standard C compiler for systems programming, structs, pointers, and memory manipulation.",
    },
    {
        "id": "javascript",
        "name": "JavaScript (Node.js)",
        "category": "Cloud Sandbox",
        "badge": "Runtime",
        "icon": "JAVASCRIPT_ROUNDED",
        "color": "AMBER_400",
        "engine": "remote",
        "ext": ".js",
        "description": "Modern ES6+ JavaScript runtime with async/await, closures, and functional array methods.",
    },
    {
        "id": "typescript",
        "name": "TypeScript",
        "category": "Cloud Sandbox",
        "badge": "Compiler",
        "icon": "CODE_ROUNDED",
        "color": "LIGHT_BLUE_400",
        "engine": "remote",
        "ext": ".ts",
        "description": "Statically typed JavaScript superset with interfaces, types, and modern tooling.",
    },
    {
        "id": "java",
        "name": "Java (OpenJDK 13)",
        "category": "Cloud Sandbox",
        "badge": "JVM",
        "icon": "COFFEE_ROUNDED",
        "color": "ORANGE_400",
        "engine": "remote",
        "ext": ".java",
        "description": "Object-oriented Java runtime with strong typing, class hierarchies, and JVM execution.",
    },
    {
        "id": "go",
        "name": "Go (Golang)",
        "category": "Cloud Sandbox",
        "badge": "Compiler",
        "icon": "PLAY_ARROW_ROUNDED",
        "color": "CYAN_300",
        "engine": "remote",
        "ext": ".go",
        "description": "Fast concurrent systems programming with goroutines, channels, and typed structs.",
    },
    {
        "id": "rust",
        "name": "Rust (1.40+)",
        "category": "Cloud Sandbox",
        "badge": "Compiler",
        "icon": "SHIELD_ROUNDED",
        "color": "BROWN_400",
        "engine": "remote",
        "ext": ".rs",
        "description": "Memory-safe systems programming with ownership, pattern matching, and zero-cost abstractions.",
    },
]

# Map language ID to templates
TEMPLATES = {
    "python": [
        {
            "name": "OOP & Classes (Vehicle Hierarchy)",
            "description": "Demonstrates classes, constructors, inheritance, encapsulation, and properties.",
            "stdin": "",
            "code": '''# Python Object-Oriented Programming (OOP) Showcase
class Vehicle:
    def __init__(self, brand: str, model: str, year: int):
        self.brand = brand
        self.model = model
        self.year = year
        self._mileage = 0  # Protected attribute

    def drive(self, miles: int) -> str:
        self._mileage += miles
        return f"{self.brand} {self.model} drove {miles} miles (Total: {self._mileage} mi)."

    @property
    def summary(self) -> str:
        return f"{self.year} {self.brand} {self.model} - {self._mileage} miles"


class ElectricCar(Vehicle):
    def __init__(self, brand: str, model: str, year: int, battery_kwh: int):
        super().__init__(brand, model, year)
        self.battery_kwh = battery_kwh
        self.charge_level = 100  # Percentage

    def charge(self, amount: int):
        self.charge_level = min(100, self.charge_level + amount)
        return f"Battery charged to {self.charge_level}%"

    def drive(self, miles: int) -> str:
        # Override with EV battery consumption
        battery_used = miles * 0.4
        self.charge_level = max(0, int(self.charge_level - battery_used))
        base_msg = super().drive(miles)
        return f"{base_msg} Remaining charge: {self.charge_level}%."


# Instantiate and test
fleet = [
    Vehicle("Toyota", "Camry", 2022),
    ElectricCar("Tesla", "Model 3", 2024, battery_kwh=75)
]

print("=== NU-AGE FLEET DIAGNOSTICS ===")
for v in fleet:
    print(v.summary)
    print(v.drive(45))
    if isinstance(v, ElectricCar):
        print(v.charge(20))
    print("-" * 35)
''',
        },
        {
            "name": "Interactive Input (Stdin Demo)",
            "description": "Shows how to read interactive user inputs with helpful prompts.",
            "stdin": "Alex Morgan\n22\nArtificial Intelligence\n",
            "code": '''# Interactive Program Input Demo
# NOTICE: When running code that asks for input, provide each answer
# in the 'Program Input (stdin)' box below (one answer per line)!

print("=== STUDENT ONBOARDING PORTAL ===")

name = input("Enter your full name: ")
age = int(input("Enter your age: "))
track = input("Select your primary learning track: ")

print(f"\\nWelcome to Nu-Age, {name}!")
print(f"Enrolled Track: {track}")
print(f"Years until 30: {max(0, 30 - age)}")
print("Status: Verified & Ready to Learn!")
''',
        },
        {
            "name": "Algorithms & Collections",
            "description": "High-performance list comprehensions, sorting, and collections.Counter.",
            "stdin": "",
            "code": '''# Python Algorithms & Collections
from collections import Counter
import math

grades = [88, 92, 79, 95, 88, 100, 72, 85, 92, 88]

# 1. Statistics
mean = sum(grades) / len(grades)
variance = sum((x - mean) ** 2 for x in grades) / len(grades)
std_dev = math.sqrt(variance)

# 2. Distribution counter
freq = Counter(grades)

print(f"Scores Count: {len(grades)}")
print(f"Mean Score: {mean:.2f}")
print(f"Standard Deviation: {std_dev:.2f}")
print(f"Most Common Grade: {freq.most_common(1)[0][0]} (appeared {freq.most_common(1)[0][1]} times)")

# 3. Letter Grade Transformation
letter_grades = [
    "A" if g >= 90 else "B" if g >= 80 else "C" if g >= 70 else "F"
    for g in sorted(grades, reverse=True)
]
print("\\nSorted Letter Grades Distribution:")
print(" -> ".join(letter_grades))
''',
        },
        {
            "name": "Blank Script",
            "description": "Clean, empty Python file ready for your code.",
            "stdin": "",
            "code": '''# Write your Python 3 code here!
def main():
    print("Hello from Nu-Age Playground!")

if __name__ == "__main__":
    main()
''',
        },
    ],
    "sql": [
        {
            "name": "E-Commerce Database (Tables + Queries)",
            "description": "Complete relational database with Customers, Products, and Orders.",
            "stdin": "",
            "code": '''-- Setup tables & sample data in-memory:
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    country TEXT
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER,
    amount REAL,
    order_date TEXT,
    FOREIGN KEY(customer_id) REFERENCES customers(id)
);

INSERT INTO customers VALUES 
(1, 'Amara Okafor', 'amara@example.ng', 'Nigeria'),
(2, 'Kwame Mensah', 'kwame@example.gh', 'Ghana'),
(3, 'Zainab Ahmed', 'zainab@example.ng', 'Nigeria'),
(4, 'Liam O''Connor', 'liam@example.ie', 'Ireland');

INSERT INTO orders VALUES
(101, 1, 250.00, '2026-01-15'),
(102, 1, 120.50, '2026-02-10'),
(103, 2, 450.00, '2026-02-18'),
(104, 3, 89.99, '2026-03-01'),
(105, 1, 310.00, '2026-03-05');

-- Query: Total spend per customer with country breakdown
SELECT 
    c.name AS CustomerName,
    c.country AS Country,
    COUNT(o.id) AS TotalOrders,
    ROUND(SUM(o.amount), 2) AS LifetimeSpend
FROM customers c
JOIN orders o ON c.id = o.customer_id
GROUP BY c.id
ORDER BY LifetimeSpend DESC;
''',
        },
        {
            "name": "Student Academics & Cohorts",
            "description": "Track student course enrolments, exam scores, and GPA rankings.",
            "stdin": "",
            "code": '''CREATE TABLE students (
    id INTEGER PRIMARY KEY,
    name TEXT,
    cohort TEXT,
    gpa REAL
);

INSERT INTO students VALUES
(1, 'Chinwe Eze', 'Cloud Engineering', 3.85),
(2, 'David Adeleke', 'Full-Stack Dev', 3.40),
(3, 'Fatima Bello', 'Cloud Engineering', 3.92),
(4, 'Emeka Obi', 'Data Science', 3.65),
(5, 'Aisha Yusuf', 'Data Science', 3.98);

-- Find top performing students across all cohorts
SELECT 
    cohort AS Track,
    COUNT(*) AS Enrolled,
    ROUND(AVG(gpa), 2) AS AverageGPA,
    MAX(gpa) AS TopScore
FROM students
GROUP BY cohort
ORDER BY TopScore DESC;
''',
        },
        {
            "name": "Blank SQL Query",
            "description": "Empty scratchpad for custom SQLite queries.",
            "stdin": "",
            "code": '''-- Write your SQLite schema or queries here
CREATE TABLE scratchpad (
    id INTEGER PRIMARY KEY,
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO scratchpad (note) VALUES ('Welcome to Nu-Age SQL Lab');
SELECT * FROM scratchpad;
''',
        },
    ],
    "html": [
        {
            "name": "Interactive Counter Card",
            "description": "HTML5 semantic structure with CSS styling and interactive JavaScript.",
            "stdin": "",
            "code": '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Nu-Age Web Sandbox</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0d1117;
      color: #e6edf3;
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
      margin: 0;
    }
    .card {
      background: #161b22;
      border: 1px solid #30363d;
      border-radius: 16px;
      padding: 32px;
      text-align: center;
      box-shadow: 0 12px 30px rgba(0,0,0,0.4);
      max-width: 360px;
    }
    h2 { margin-top: 0; color: #58a6ff; }
    .counter { font-size: 54px; font-weight: 800; color: #3fb950; margin: 20px 0; }
    button {
      background: #238636;
      color: white;
      border: none;
      padding: 12px 24px;
      font-size: 16px;
      font-weight: 600;
      border-radius: 8px;
      cursor: pointer;
      transition: background 0.2s;
    }
    button:hover { background: #2ea043; }
  </style>
</head>
<body>
  <div class="card">
    <h2>Interactive Counter</h2>
    <div class="counter" id="num">0</div>
    <button onclick="increment()">Click to Count +1</button>
  </div>

  <script>
    let count = 0;
    function increment() {
      count++;
      document.getElementById('num').innerText = count;
    }
  </script>
</body>
</html>
''',
        },
    ],
    "cpp": [
        {
            "name": "Fast I/O & Interactive Array",
            "description": "C++ competitive programming fast I/O and algorithm execution.",
            "stdin": "5\n12 45 3 22 9\n",
            "code": '''#include <iostream>
#include <vector>
#include <algorithm>

using namespace std;

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(NULL);

    int n;
    if (cin >> n) {
        vector<int> nums(n);
        for (int i = 0; i < n; i++) {
            cin >> nums[i];
        }

        cout << "Original vector: ";
        for (int x : nums) cout << x << " ";
        cout << "\\n";

        sort(nums.begin(), nums.end());

        cout << "Sorted vector:   ";
        for (int x : nums) cout << x << " ";
        cout << "\\n";
    } else {
        cout << "Hello from Nu-Age C++ Compiler!\\n";
    }

    return 0;
}
''',
        },
    ],
    "java": [
        {
            "name": "Main Class & Methods",
            "description": "Java class with standard static methods and loops.",
            "stdin": "Nu-Age Learner\n",
            "code": '''import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        System.out.println("=== Welcome to Java Playground ===");

        if (scanner.hasNextLine()) {
            String name = scanner.nextLine();
            System.out.println("Hello, " + name + "! Welcome to Java on Nu-Age.");
        } else {
            System.out.println("Hello, World from Java!");
        }

        System.out.println("\\nSquares from 1 to 5:");
        for (int i = 1; i <= 5; i++) {
            System.out.printf("%d squared is %d\\n", i, (i * i));
        }
    }
}
''',
        },
    ],
    "javascript": [
        {
            "name": "Async/Await & Array Functions",
            "description": "Modern JavaScript ES6+ features and data transformations.",
            "stdin": "",
            "code": '''// Modern JavaScript (Node.js) Playground
const students = [
  { name: "Amara", score: 92 },
  { name: "Bayo", score: 78 },
  { name: "Chioma", score: 85 },
  { name: "Damilola", score: 96 }
];

console.log("=== NU-AGE STUDENT DATA LAB ===");

// 1. Filter honors students
const honors = students.filter(s => s.score >= 85);
console.log("Honors Students (>85):", honors.map(s => s.name).join(", "));

// 2. Average score
const total = students.reduce((sum, s) => sum + s.score, 0);
const avg = total / students.length;
console.log(`Class Average: ${avg.toFixed(1)}%`);

// 3. Async promise demo
async function simulateNetworkTask() {
  console.log("\\nFetching remote cohort statistics...");
  return new Promise(resolve => {
    setTimeout(() => resolve("Synchronized successfully!"), 100);
  });
}

simulateNetworkTask().then(console.log);
''',
        },
    ],
}
