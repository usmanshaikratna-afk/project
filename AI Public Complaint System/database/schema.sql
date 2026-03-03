-- Departments table
CREATE TABLE departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    head VARCHAR(100),
    email VARCHAR(100),
    phone VARCHAR(15),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Complaints table
CREATE TABLE complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    citizen_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    phone VARCHAR(15),
    complaint_text TEXT NOT NULL,
    category VARCHAR(50),
    subcategory VARCHAR(50),
    priority VARCHAR(20) CHECK(priority IN ('High', 'Medium', 'Low')),
    status VARCHAR(20) DEFAULT 'Pending' CHECK(status IN ('Pending', 'In Progress', 'Resolved', 'Rejected')),
    assigned_dept VARCHAR(50),
    location VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    resolved_at TIMESTAMP,
    ai_confidence FLOAT,
    feedback_rating INTEGER CHECK(feedback_rating BETWEEN 1 AND 5),
    feedback_text TEXT,
    FOREIGN KEY (assigned_dept) REFERENCES departments(name)
);

-- Indexes for better performance
CREATE INDEX idx_complaints_status ON complaints(status);
CREATE INDEX idx_complaints_priority ON complaints(priority);
CREATE INDEX idx_complaints_category ON complaints(category);
CREATE INDEX idx_complaints_created_at ON complaints(created_at);

-- Sample department data
INSERT INTO departments (name, head, email, phone) VALUES
    ('Public Works Department', 'John Doe', 'pwd@example.com', '1234567890'),
    ('Water Supply Department', 'Jane Smith', 'water@example.com', '1234567891'),
    ('Sanitation Department', 'Bob Johnson', 'sanitation@example.com', '1234567892'),
    ('Electricity Department', 'Alice Brown', 'electricity@example.com', '1234567893'),
    ('Police Department', 'Charlie Wilson', 'police@example.com', '1234567894'),
    ('General Administration', 'Diana Miller', 'admin@example.com', '1234567895');

-- Audit log for tracking changes
CREATE TABLE complaint_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id INTEGER,
    action VARCHAR(50),
    old_status VARCHAR(20),
    new_status VARCHAR(20),
    changed_by VARCHAR(100),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (complaint_id) REFERENCES complaints(id)
);