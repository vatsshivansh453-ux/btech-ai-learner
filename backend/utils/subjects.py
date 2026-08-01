"""
Core B.Tech (CSE-focused) subject/topic catalog.

This is just a syllabus-style outline of standard topic names — the kind
of list any curriculum or textbook table-of-contents would have. No
external content is stored here; every topic's actual notes are
generated fresh by the AI (utils/notes.py) when a student opens it.

Feel free to edit/extend this list for your branch's actual syllabus.
"""

SUBJECTS = {
    "Data Structures & Algorithms": [
        "Arrays and Strings", "Linked Lists", "Stacks and Queues",
        "Trees and Binary Search Trees", "Heaps and Priority Queues",
        "Graphs — Representation and Traversal", "Sorting Algorithms",
        "Searching Algorithms", "Dynamic Programming", "Greedy Algorithms",
        "Backtracking", "Time and Space Complexity Analysis",
    ],
    "Operating Systems": [
        "Process Management", "CPU Scheduling Algorithms",
        "Process Synchronization", "Deadlocks",
        "Memory Management and Paging", "Virtual Memory",
        "File Systems", "Disk Scheduling", "Threads and Multithreading",
    ],
    "Computer Networks": [
        "OSI and TCP/IP Models", "Physical and Data Link Layer",
        "IP Addressing and Subnetting", "Routing Algorithms",
        "Transport Layer — TCP and UDP", "Application Layer Protocols",
        "Network Security Basics", "Congestion Control",
    ],
    "Database Management Systems": [
        "ER Model and Relational Model", "SQL Fundamentals",
        "Normalization", "Transactions and ACID Properties",
        "Concurrency Control", "Indexing", "Query Optimization",
        "NoSQL Databases Overview",
    ],
    "Object-Oriented Programming": [
        "Classes and Objects", "Inheritance", "Polymorphism",
        "Encapsulation and Abstraction", "Constructors and Destructors",
        "Operator Overloading", "Exception Handling", "Design Patterns Basics",
    ],
    "Computer Organization & Architecture": [
        "Number Systems and Boolean Algebra", "Instruction Set Architecture",
        "CPU Design and Datapath", "Pipelining", "Memory Hierarchy and Cache",
        "I/O Organization",
    ],
    "Theory of Computation": [
        "Finite Automata", "Regular Expressions and Languages",
        "Context-Free Grammars", "Pushdown Automata", "Turing Machines",
        "Decidability and Undecidability",
    ],
    "Software Engineering": [
        "SDLC Models", "Requirements Engineering", "Software Design Principles",
        "Testing Strategies", "Agile Methodology", "Version Control Concepts",
    ],
}


def list_subjects():
    return list(SUBJECTS.keys())


def list_topics(subject):
    return SUBJECTS.get(subject, [])
