CREATE DATABASE IF NOT EXISTS ScholarshipDB;
USE ScholarshipDB;
-- 1. Students Table
CREATE TABLE Students (
    student_id INT AUTO_INCREMENT PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    department VARCHAR(50) NOT NULL,
    current_year INT CHECK (current_year BETWEEN 1 AND 5)
);

-- 2. Schemes Table
CREATE TABLE Schemes (
    scheme_id INT AUTO_INCREMENT PRIMARY KEY,
    scheme_name VARCHAR(100) NOT NULL,
    max_amount DECIMAL(10, 2) NOT NULL
);

-- 3. Bank Details Table (Enforces 1:1 relationship and valid details)
CREATE TABLE Bank_Details (
    bank_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT UNIQUE NOT NULL,
    account_number VARCHAR(20) UNIQUE NOT NULL,
    ifsc_code VARCHAR(15) NOT NULL,
    bank_name VARCHAR(50) NOT NULL,
    FOREIGN KEY (student_id) REFERENCES Students(student_id) ON DELETE CASCADE
);

-- 4. Applications Table (Enforces: One application per student per scheme per year)
CREATE TABLE Applications (
    application_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    scheme_id INT NOT NULL,
    application_year INT NOT NULL,
    status VARCHAR(20) DEFAULT 'Pending' CHECK (status IN ('Pending', 'Verified', 'Approved', 'Rejected')),
    submission_date DATE DEFAULT (CURRENT_DATE),
    FOREIGN KEY (student_id) REFERENCES Students(student_id),
    FOREIGN KEY (scheme_id) REFERENCES Schemes(scheme_id),
    CONSTRAINT unique_student_scheme_year UNIQUE (student_id, scheme_id, application_year)
);

-- 5. Sanctions Table (Enforces: Sanction within limits)
CREATE TABLE Sanctions (
    sanction_id INT AUTO_INCREMENT PRIMARY KEY,
    application_id INT UNIQUE NOT NULL,
    sanctioned_amount DECIMAL(10, 2) NOT NULL,
    sanction_date DATE NOT NULL,
    FOREIGN KEY (application_id) REFERENCES Applications(application_id)
);

-- 6. Disbursements Table (Tracks payouts)
CREATE TABLE Disbursements (
    disbursement_id INT AUTO_INCREMENT PRIMARY KEY,
    sanction_id INT NOT NULL,
    disbursed_amount DECIMAL(10, 2) NOT NULL,
    disbursement_date DATE NOT NULL,
    transaction_ref VARCHAR(50) UNIQUE NOT NULL,
    FOREIGN KEY (sanction_id) REFERENCES Sanctions(sanction_id)
);


-- ==========================================================
-- 2. INSERT STATEMENTS (SAMPLE DATA)
-- ==========================================================

-- Insert Students (IDs 1 to 10)
INSERT INTO Students (first_name, last_name, email, department, current_year) VALUES
('Rahul', 'Sharma', 'rahul.sharma@example.com', 'Computer Science', 3),
('Priya', 'Reddy', 'priya.reddy@example.com', 'Electronics', 2),
('Amit', 'Kumar', 'amit.kumar@example.com', 'Mechanical', 4),
('Sneha', 'Verma', 'sneha.verma@example.com', 'Civil', 1),
('Vikram', 'Rao', 'vikram.rao@example.com', 'Artificial Intelligence', 3),
('Ananya', 'Nair', 'ananya.nair@example.com', 'Information Technology', 2),
('Kiran', 'Patel', 'kiran.patel@example.com', 'Mechanical', 4),
('Neha', 'Gupta', 'neha.gupta@example.com', 'Computer Science', 1),
('Rohan', 'Das', 'rohan.das@example.com', 'Electronics', 3),
('Divya', 'Menon', 'divya.menon@example.com', 'Civil', 2);

-- Insert Schemes
INSERT INTO Schemes (scheme_name, max_amount) VALUES
('Merit-Based Scholarship', 50000.00),
('Need-Based Financial Aid', 35000.00),
('Technical Excellence Grant', 40000.00),
('Sports Quota Scholarship', 25000.00),
('Women in Tech Scholarship', 60000.00),
('Research & Innovation Grant', 75000.00);

-- Insert Bank Details
INSERT INTO Bank_Details (student_id, account_number, ifsc_code, bank_name) VALUES
(1, 'ACC9876543210', 'HDFC0001234', 'HDFC Bank'),
(2, 'ACC8765432109', 'SBIN0005678', 'State Bank of India'),
(3, 'ACC7654321098', 'ICIC0009101', 'ICICI Bank'),
(4, 'ACC6543210987', 'UTIB0001122', 'Axis Bank'),
(5, 'ACC5432109876', 'PUNB0003344', 'Punjab National Bank'),
(6, 'ACC4321098765', 'BARB0001234', 'Bank of Baroda'),
(7, 'ACC3210987654', 'CNRB0005678', 'Canara Bank'),
(8, 'ACC2109876543', 'SBIN0009988', 'State Bank of India'),
(9, 'ACC1098765432', 'HDFC0004455', 'HDFC Bank'),
(10, 'ACC0987654321', 'ICIC0007788', 'ICICI Bank');

-- Insert Applications
INSERT INTO Applications (student_id, scheme_id, application_year, status, submission_date) VALUES
(1, 1, 2026, 'Approved', '2026-02-10'),
(2, 2, 2026, 'Pending', '2026-03-01'),
(3, 3, 2026, 'Verified', '2026-03-05'),
(4, 1, 2026, 'Rejected', '2026-02-15'),
(5, 3, 2026, 'Approved', '2026-02-20'),
(6, 5, 2026, 'Approved', '2026-03-10'),
(7, 3, 2026, 'Pending', '2026-03-12'),
(8, 1, 2026, 'Verified', '2026-03-14'),
(9, 2, 2026, 'Approved', '2026-03-15'),
(10, 6, 2026, 'Pending', '2026-03-18');

-- Insert Sanctions
INSERT INTO Sanctions (application_id, sanctioned_amount, sanction_date) VALUES
(1, 45000.00, '2026-02-18'),
(5, 40000.00, '2026-02-25'),
(6, 55000.00, '2026-03-15'),
(9, 30000.00, '2026-03-18');

-- Insert Disbursements
INSERT INTO Disbursements (sanction_id, disbursed_amount, disbursement_date, transaction_ref) VALUES
(1, 45000.00, '2026-02-20', 'TXNREF10029384'),
(2, 40000.00, '2026-02-28', 'TXNREF10029385'),
(3, 55000.00, '2026-03-16', 'TXNREF99887766'),
(4, 30000.00, '2026-03-20', 'TXNREF99887767');

--Comprehensive Query: Complete details for a specific Sanction ID (e.g., Sanction ID = 2)
SELECT 
    s.student_id,
    CONCAT(s.first_name, ' ', s.last_name) AS student_name,
    s.email,
    s.department,
    s.current_year,
    b.account_number,
    b.ifsc_code,
    b.bank_name,
    sc.scheme_name,
    sa.sanction_id,
    sa.sanctioned_amount,
    sa.sanction_date,
    d.disbursed_amount,
    d.disbursement_date,
    d.transaction_ref
FROM Sanctions sa
JOIN Applications a ON sa.application_id = a.application_id
JOIN Students s ON a.student_id = s.student_id
LEFT JOIN Bank_Details b ON s.student_id = b.student_id
JOIN Schemes sc ON a.scheme_id = sc.scheme_id
LEFT JOIN Disbursements d ON sa.sanction_id = d.sanction_id
WHERE sa.sanction_id = 2;

