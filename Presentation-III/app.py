import os
import datetime
import decimal
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from mysql.connector import Error, errorcode
from config import Config
from db import get_db_cursor, test_connection

app = Flask(__name__)
app.config.from_object(Config)

# Helper function for JSON serialization of Decimals and Dates
def serialize_row(row):
    if not row:
        return row
    result = {}
    for key, val in row.items():
        if isinstance(val, (datetime.date, datetime.datetime)):
            result[key] = val.isoformat()
        elif isinstance(val, decimal.Decimal):
            result[key] = float(val)
        else:
            result[key] = val
    return result

def serialize_rows(rows):
    return [serialize_row(r) for r in rows] if rows else []

# =====================================================================
# Role-Based Access Control (RBAC) Decorators & Context
# =====================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({"success": False, "message": "Authentication required. Please sign in."}), 401
            return redirect(url_for('page_login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({"success": False, "message": "Authentication required. Please sign in."}), 401
            return redirect(url_for('page_login', next=request.path))
        if session.get('role') != 'admin':
            if request.path.startswith('/api/'):
                return jsonify({
                    "success": False, 
                    "message": "Access Denied: Administrator role required to perform this action."
                }), 403
            return redirect(url_for('page_dashboard', unauthorized=1))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_user_context():
    return {
        'current_user': session.get('username'),
        'current_role': session.get('role', 'guest'),
        'current_student_id': session.get('student_id'),
        'current_student_name': session.get('student_name', ''),
        'is_admin': session.get('role') == 'admin',
        'is_student': session.get('role') == 'student'
    }

# =====================================================================
# Authentication Routes (Login / Logout / Role Switch)
# =====================================================================

@app.route('/login', methods=['GET', 'POST'])
def page_login():
    if request.method == 'GET':
        if 'user_id' in session:
            return redirect(url_for('page_dashboard'))
        return render_template('login.html')

    # Handle POST login
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()

    if not username or not password:
        return jsonify({"success": False, "message": "Username and password are required."}), 400

    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT user_id, username, password, role, student_id 
                FROM Users 
                WHERE username = %s;
            """, (username,))
            user = cursor.fetchone()

            if not user or user['password'] != password:
                return jsonify({"success": False, "message": "Invalid username or password."}), 401

            # Populate session
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['student_id'] = user['student_id']

            if user['student_id']:
                cursor.execute("""
                    SELECT first_name, last_name, department, current_year 
                    FROM Students 
                    WHERE student_id = %s;
                """, (user['student_id'],))
                stu = cursor.fetchone()
                if stu:
                    session['student_name'] = f"{stu['first_name']} {stu['last_name']}"
                    session['student_dept'] = stu['department']
                    session['student_year'] = stu['current_year']
            else:
                session['student_name'] = 'Administrator'

            return jsonify({
                "success": True,
                "message": f"Welcome back, {session.get('student_name', user['username'])}!",
                "role": user['role'],
                "redirect": "/"
            })
    except Error as err:
        return jsonify({"success": False, "message": f"Database authentication error: {err.msg}"}), 500

@app.route('/logout')
def page_logout():
    session.clear()
    return redirect(url_for('page_login'))

@app.route('/api/auth/me', methods=['GET'])
def api_auth_me():
    if 'user_id' in session:
        return jsonify({
            "authenticated": True,
            "user_id": session.get('user_id'),
            "username": session.get('username'),
            "role": session.get('role'),
            "student_id": session.get('student_id'),
            "student_name": session.get('student_name')
        })
    return jsonify({"authenticated": False, "role": "guest"})

# =====================================================================
# HTML Page Routes (Protected by Session & Role Guards)
# =====================================================================

@app.route('/')
@login_required
def page_dashboard():
    return render_template('index.html', active_page='dashboard')

@app.route('/students')
@login_required
def page_students():
    return render_template('students.html', active_page='students')

@app.route('/schemes')
@login_required
def page_schemes():
    return render_template('schemes.html', active_page='schemes')

@app.route('/applications')
@login_required
def page_applications():
    return render_template('applications.html', active_page='applications')

@app.route('/disbursements')
@login_required
def page_disbursements():
    return render_template('disbursements.html', active_page='disbursements')

# =====================================================================
# Health, Status & Setup Endpoints
# =====================================================================

@app.route('/api/status', methods=['GET'])
def api_status():
    status = test_connection()
    return jsonify(status)

@app.route('/api/setup/configure', methods=['POST'])
def api_setup_configure():
    """Allows setting MySQL root password from UI, saving to .env, and initializing DB."""
    data = request.get_json() or {}
    password = data.get('password', '')
    user = data.get('user', Config.DB_USER)
    host = data.get('host', Config.DB_HOST)
    port = int(data.get('port', Config.DB_PORT))

    from init_db import initialize_database
    success = initialize_database(host=host, user=user, password=password, port=port, seed=True)

    if success:
        # Update .env file
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        try:
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write(f"DB_HOST={host}\n")
                f.write(f"DB_PORT={port}\n")
                f.write(f"DB_USER={user}\n")
                f.write(f"DB_PASSWORD={password}\n")
                f.write(f"DB_NAME=ScholarshipDB\n")
                f.write(f"PORT={Config.PORT}\n")
                f.write(f"FLASK_DEBUG={Config.DEBUG}\n")
                f.write(f"SECRET_KEY={Config.SECRET_KEY}\n")
        except Exception as ex:
            print("Failed to rewrite .env:", ex)

        # Update in-memory config
        Config.DB_PASSWORD = password
        Config.DB_USER = user
        Config.DB_HOST = host
        Config.DB_PORT = port

        return jsonify({
            "success": True,
            "message": "Connected to MySQL and initialized ScholarshipDB successfully!"
        })
    else:
        return jsonify({
            "success": False,
            "message": "Could not connect to MySQL with the provided credentials. Please check your root password."
        }), 400


# =====================================================================
# Dashboard Metrics API
# =====================================================================

@app.route('/api/dashboard/stats', methods=['GET'])
@login_required
def api_dashboard_stats():
    try:
        is_student = (session.get('role') == 'student' and session.get('student_id'))
        stu_id = session.get('student_id')

        with get_db_cursor() as cursor:
            # 1. Total Students
            cursor.execute("SELECT COUNT(*) AS total FROM Students;")
            total_students = cursor.fetchone()['total']

            # 2. Total Active Schemes
            cursor.execute("SELECT COUNT(*) AS total FROM Schemes;")
            total_schemes = cursor.fetchone()['total']

            # 3. Application Counts by Status
            if is_student:
                cursor.execute("""
                    SELECT 
                        COUNT(a.application_id) AS total_apps,
                        SUM(CASE WHEN a.status = 'Pending' THEN 1 ELSE 0 END) AS pending_apps,
                        SUM(CASE WHEN a.status = 'Approved' AND dsb.disbursement_id IS NULL THEN 1 ELSE 0 END) AS approved_apps,
                        SUM(CASE WHEN dsb.disbursement_id IS NOT NULL THEN 1 ELSE 0 END) AS disbursed_apps,
                        SUM(CASE WHEN a.status = 'Rejected' THEN 1 ELSE 0 END) AS rejected_apps
                    FROM Applications a
                    LEFT JOIN Sanctions snc ON a.application_id = snc.application_id
                    LEFT JOIN Disbursements dsb ON snc.sanction_id = dsb.sanction_id
                    WHERE a.student_id = %s;
                """, (stu_id,))
            else:
                cursor.execute("""
                    SELECT 
                        COUNT(a.application_id) AS total_apps,
                        SUM(CASE WHEN a.status = 'Pending' THEN 1 ELSE 0 END) AS pending_apps,
                        SUM(CASE WHEN a.status = 'Approved' AND dsb.disbursement_id IS NULL THEN 1 ELSE 0 END) AS approved_apps,
                        SUM(CASE WHEN dsb.disbursement_id IS NOT NULL THEN 1 ELSE 0 END) AS disbursed_apps,
                        SUM(CASE WHEN a.status = 'Rejected' THEN 1 ELSE 0 END) AS rejected_apps
                    FROM Applications a
                    LEFT JOIN Sanctions snc ON a.application_id = snc.application_id
                    LEFT JOIN Disbursements dsb ON snc.sanction_id = dsb.sanction_id;
                """)
            app_stats = cursor.fetchone()

            # 4. Total Funds Sanctioned and Disbursed
            if is_student:
                cursor.execute("""
                    SELECT COALESCE(SUM(snc.sanctioned_amount), 0) AS total_sanctioned
                    FROM Sanctions snc
                    JOIN Applications a ON snc.application_id = a.application_id
                    WHERE a.student_id = %s;
                """, (stu_id,))
                total_sanctioned = cursor.fetchone()['total_sanctioned']

                cursor.execute("""
                    SELECT COALESCE(SUM(dsb.disbursed_amount), 0) AS total_disbursed
                    FROM Disbursements dsb
                    JOIN Sanctions snc ON dsb.sanction_id = snc.sanction_id
                    JOIN Applications a ON snc.application_id = a.application_id
                    WHERE a.student_id = %s;
                """, (stu_id,))
                total_disbursed = cursor.fetchone()['total_disbursed']
            else:
                cursor.execute("SELECT COALESCE(SUM(sanctioned_amount), 0) AS total_sanctioned FROM Sanctions;")
                total_sanctioned = cursor.fetchone()['total_sanctioned']

                cursor.execute("SELECT COALESCE(SUM(disbursed_amount), 0) AS total_disbursed FROM Disbursements;")
                total_disbursed = cursor.fetchone()['total_disbursed']

            # 5. Recent Applications
            if is_student:
                cursor.execute("""
                    SELECT 
                        a.application_id, a.application_year, a.status, a.submission_date,
                        s.student_id, CONCAT(s.first_name, ' ', s.last_name) AS student_name,
                        s.department,
                        sch.scheme_name, sch.max_amount
                    FROM Applications a
                    JOIN Students s ON a.student_id = s.student_id
                    JOIN Schemes sch ON a.scheme_id = sch.scheme_id
                    WHERE a.student_id = %s
                    ORDER BY a.submission_date DESC, a.application_id DESC
                    LIMIT 5;
                """, (stu_id,))
            else:
                cursor.execute("""
                    SELECT 
                        a.application_id, a.application_year, a.status, a.submission_date,
                        s.student_id, CONCAT(s.first_name, ' ', s.last_name) AS student_name,
                        s.department,
                        sch.scheme_name, sch.max_amount
                    FROM Applications a
                    JOIN Students s ON a.student_id = s.student_id
                    JOIN Schemes sch ON a.scheme_id = sch.scheme_id
                    ORDER BY a.submission_date DESC, a.application_id DESC
                    LIMIT 5;
                """)
            recent_apps = serialize_rows(cursor.fetchall())

            # 6. Top Schemes by Applications
            cursor.execute("""
                SELECT 
                    sch.scheme_name,
                    COUNT(a.application_id) AS app_count,
                    COALESCE(SUM(snc.sanctioned_amount), 0) AS total_sanctioned
                FROM Schemes sch
                LEFT JOIN Applications a ON sch.scheme_id = a.scheme_id
                LEFT JOIN Sanctions snc ON a.application_id = snc.application_id
                GROUP BY sch.scheme_id, sch.scheme_name
                ORDER BY app_count DESC;
            """)
            scheme_breakdown = serialize_rows(cursor.fetchall())

            return jsonify({
                "success": True,
                "data": {
                    "total_students": 1 if is_student else total_students,
                    "total_schemes": total_schemes,
                    "total_applications": app_stats['total_apps'] or 0,
                    "pending_applications": app_stats['pending_apps'] or 0,
                    "approved_applications": app_stats['approved_apps'] or 0,
                    "disbursed_applications": app_stats['disbursed_apps'] or 0,
                    "rejected_applications": app_stats['rejected_apps'] or 0,
                    "total_sanctioned": float(total_sanctioned),
                    "total_disbursed": float(total_disbursed),
                    "recent_applications": recent_apps,
                    "scheme_breakdown": scheme_breakdown
                }
            })
    except Error as err:
        return jsonify({"success": False, "message": f"Database error: {err.msg}"}), 500
    except Exception as ex:
        return jsonify({"success": False, "message": f"Server error: {str(ex)}"}), 500

# =====================================================================
# Students CRUD APIs
# =====================================================================

@app.route('/api/students', methods=['GET'])
@login_required
def api_get_students():
    try:
        department = request.args.get('department')
        year = request.args.get('year')
        search = request.args.get('search')

        query = """
            SELECT 
                s.student_id, s.first_name, s.last_name, s.email, s.department, s.current_year,
                b.bank_id, b.account_number, b.ifsc_code, b.bank_name,
                COUNT(a.application_id) AS total_applications
            FROM Students s
            LEFT JOIN Bank_Details b ON s.student_id = b.student_id
            LEFT JOIN Applications a ON s.student_id = a.student_id
            WHERE 1=1
        """
        params = []
        if session.get('role') == 'student' and session.get('student_id'):
            query += " AND s.student_id = %s"
            params.append(session.get('student_id'))

        if department:
            query += " AND s.department = %s"
            params.append(department)
        if year:
            query += " AND s.current_year = %s"
            params.append(int(year))
        if search:
            query += " AND (s.first_name LIKE %s OR s.last_name LIKE %s OR s.email LIKE %s OR s.department LIKE %s)"
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param, search_param])

        query += " GROUP BY s.student_id, b.bank_id ORDER BY s.student_id DESC;"

        with get_db_cursor() as cursor:
            cursor.execute(query, params)
            students = serialize_rows(cursor.fetchall())
            return jsonify({"success": True, "data": students})
    except Error as err:
        return jsonify({"success": False, "message": f"Database error: {err.msg}"}), 500

@app.route('/api/students/<int:student_id>', methods=['GET'])
@login_required
def api_get_student_detail(student_id):
    if session.get('role') == 'student' and session.get('student_id') != student_id:
        return jsonify({"success": False, "message": "Access Denied: You may only view your own student record."}), 403
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT s.*, b.bank_id, b.account_number, b.ifsc_code, b.bank_name
                FROM Students s
                LEFT JOIN Bank_Details b ON s.student_id = b.student_id
                WHERE s.student_id = %s;
            """, (student_id,))
            student = cursor.fetchone()
            if not student:
                return jsonify({"success": False, "message": "Student not found"}), 404

            # Fetch applications for this student
            cursor.execute("""
                SELECT 
                    a.application_id, a.application_year, a.status, a.submission_date,
                    sch.scheme_name, sch.max_amount,
                    snc.sanctioned_amount, dsb.disbursed_amount
                FROM Applications a
                JOIN Schemes sch ON a.scheme_id = sch.scheme_id
                LEFT JOIN Sanctions snc ON a.application_id = snc.application_id
                LEFT JOIN Disbursements dsb ON snc.sanction_id = dsb.sanction_id
                WHERE a.student_id = %s
                ORDER BY a.submission_date DESC;
            """, (student_id,))
            student['applications'] = serialize_rows(cursor.fetchall())
            return jsonify({"success": True, "data": serialize_row(student)})
    except Error as err:
        return jsonify({"success": False, "message": f"Database error: {err.msg}"}), 500

@app.route('/api/students', methods=['POST'])
@admin_required
def api_create_student():
    data = request.get_json() or {}
    first_name = (data.get('first_name') or '').strip()
    last_name = (data.get('last_name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    department = (data.get('department') or '').strip()
    current_year = data.get('current_year')

    # Bank details optional upon creation
    account_number = (data.get('account_number') or '').strip()
    ifsc_code = (data.get('ifsc_code') or '').strip().upper()
    bank_name = (data.get('bank_name') or '').strip()

    # Validations
    if not first_name or not last_name or not email or not department:
        return jsonify({"success": False, "message": "First name, last name, email, and department are required."}), 400

    try:
        current_year = int(current_year)
        if current_year < 1 or current_year > 5:
            return jsonify({"success": False, "message": "Current year must be between 1 and 5."}), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Valid current year (1-5) is required."}), 400

    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO Students (first_name, last_name, email, department, current_year)
                VALUES (%s, %s, %s, %s, %s);
            """, (first_name, last_name, email, department, current_year))
            student_id = cursor.lastrowid

            # If bank details provided, insert into Bank_Details
            if account_number and ifsc_code and bank_name:
                cursor.execute("""
                    INSERT INTO Bank_Details (student_id, account_number, ifsc_code, bank_name)
                    VALUES (%s, %s, %s, %s);
                """, (student_id, account_number, ifsc_code, bank_name))

            return jsonify({
                "success": True,
                "message": "Student profile created successfully!",
                "student_id": student_id
            }), 201

    except Error as err:
        if err.errno == errorcode.ER_DUP_ENTRY:
            if 'email' in err.msg.lower():
                return jsonify({"success": False, "message": "A student with this email address already exists."}), 409
            if 'account_number' in err.msg.lower():
                return jsonify({"success": False, "message": "This bank account number is already registered."}), 409
        return jsonify({"success": False, "message": f"Database error: {err.msg}"}), 500

@app.route('/api/students/<int:student_id>', methods=['PUT'])
@admin_required
def api_update_student(student_id):
    data = request.get_json() or {}
    first_name = (data.get('first_name') or '').strip()
    last_name = (data.get('last_name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    department = (data.get('department') or '').strip()
    current_year = data.get('current_year')

    account_number = (data.get('account_number') or '').strip()
    ifsc_code = (data.get('ifsc_code') or '').strip().upper()
    bank_name = (data.get('bank_name') or '').strip()

    if not first_name or not last_name or not email or not department:
        return jsonify({"success": False, "message": "All student demographic fields are required."}), 400

    try:
        current_year = int(current_year)
        if current_year < 1 or current_year > 5:
            return jsonify({"success": False, "message": "Current year must be between 1 and 5."}), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Valid current year (1-5) is required."}), 400

    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                UPDATE Students 
                SET first_name = %s, last_name = %s, email = %s, department = %s, current_year = %s
                WHERE student_id = %s;
            """, (first_name, last_name, email, department, current_year, student_id))

            if account_number and ifsc_code and bank_name:
                cursor.execute("""
                    INSERT INTO Bank_Details (student_id, account_number, ifsc_code, bank_name)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                        account_number = VALUES(account_number),
                        ifsc_code = VALUES(ifsc_code),
                        bank_name = VALUES(bank_name);
                """, (student_id, account_number, ifsc_code, bank_name))

            return jsonify({"success": True, "message": "Student profile updated successfully!"})

    except Error as err:
        if err.errno == errorcode.ER_DUP_ENTRY:
            return jsonify({"success": False, "message": "Email or Bank Account number already exists."}), 409
        return jsonify({"success": False, "message": f"Database error: {err.msg}"}), 500

@app.route('/api/students/<int:student_id>', methods=['DELETE'])
@admin_required
def api_delete_student(student_id):
    try:
        with get_db_cursor(commit=True) as cursor:
            # 1. Check student exists
            cursor.execute("SELECT student_id FROM Students WHERE student_id = %s;", (student_id,))
            if not cursor.fetchone():
                return jsonify({"success": False, "message": "Student not found."}), 404

            # 2. Get applications for student to cascade disbursements and sanctions
            cursor.execute("SELECT application_id FROM Applications WHERE student_id = %s;", (student_id,))
            apps = cursor.fetchall()
            app_ids = [a['application_id'] for a in apps]

            if app_ids:
                fmt_apps = ','.join(['%s'] * len(app_ids))
                cursor.execute(f"SELECT sanction_id FROM Sanctions WHERE application_id IN ({fmt_apps});", tuple(app_ids))
                sanctions = cursor.fetchall()
                sanction_ids = [s['sanction_id'] for s in sanctions]

                if sanction_ids:
                    fmt_sanctions = ','.join(['%s'] * len(sanction_ids))
                    cursor.execute(f"DELETE FROM Disbursements WHERE sanction_id IN ({fmt_sanctions});", tuple(sanction_ids))
                    cursor.execute(f"DELETE FROM Sanctions WHERE sanction_id IN ({fmt_sanctions});", tuple(sanction_ids))

                cursor.execute(f"DELETE FROM Applications WHERE application_id IN ({fmt_apps});", tuple(app_ids))

            # 3. Delete Bank Details and Student
            cursor.execute("DELETE FROM Bank_Details WHERE student_id = %s;", (student_id,))
            cursor.execute("DELETE FROM Students WHERE student_id = %s;", (student_id,))

            return jsonify({"success": True, "message": "Student record and associated aid data deleted successfully."})
    except Error as err:
        return jsonify({"success": False, "message": f"Database constraint error: {err.msg}"}), 500

# =====================================================================
# Schemes CRUD APIs
# =====================================================================

@app.route('/api/schemes', methods=['GET'])
@login_required
def api_get_schemes():
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    sch.scheme_id, sch.scheme_name, sch.max_amount,
                    COUNT(a.application_id) AS total_applicants,
                    COALESCE(SUM(snc.sanctioned_amount), 0) AS total_sanctioned_amount,
                    COALESCE(SUM(dsb.disbursed_amount), 0) AS total_disbursed_amount
                FROM Schemes sch
                LEFT JOIN Applications a ON sch.scheme_id = a.scheme_id
                LEFT JOIN Sanctions snc ON a.application_id = snc.application_id
                LEFT JOIN Disbursements dsb ON snc.sanction_id = dsb.sanction_id
                GROUP BY sch.scheme_id
                ORDER BY sch.scheme_id ASC;
            """)
            schemes = serialize_rows(cursor.fetchall())
            return jsonify({"success": True, "data": schemes})
    except Error as err:
        return jsonify({"success": False, "message": f"Database error: {err.msg}"}), 500

@app.route('/api/schemes', methods=['POST'])
@admin_required
def api_create_scheme():
    data = request.get_json() or {}
    scheme_name = (data.get('scheme_name') or '').strip()
    max_amount = data.get('max_amount')

    if not scheme_name:
        return jsonify({"success": False, "message": "Scheme name is required."}), 400

    try:
        max_amount = float(max_amount)
        if max_amount <= 0:
            return jsonify({"success": False, "message": "Maximum amount must be greater than zero."}), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Valid maximum award amount is required."}), 400

    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO Schemes (scheme_name, max_amount)
                VALUES (%s, %s);
            """, (scheme_name, max_amount))
            return jsonify({
                "success": True,
                "message": "Scholarship scheme added successfully!",
                "scheme_id": cursor.lastrowid
            }), 201
    except Error as err:
        if err.errno == errorcode.ER_DUP_ENTRY:
            return jsonify({"success": False, "message": "A scheme with this name already exists."}), 409
        return jsonify({"success": False, "message": f"Database error: {err.msg}"}), 500

@app.route('/api/schemes/<int:scheme_id>', methods=['PUT'])
@admin_required
def api_update_scheme(scheme_id):
    data = request.get_json() or {}
    scheme_name = (data.get('scheme_name') or '').strip()
    max_amount = data.get('max_amount')

    if not scheme_name:
        return jsonify({"success": False, "message": "Scheme name is required."}), 400

    try:
        max_amount = float(max_amount)
        if max_amount <= 0:
            return jsonify({"success": False, "message": "Maximum amount must be greater than zero."}), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Valid maximum award amount is required."}), 400

    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                UPDATE Schemes 
                SET scheme_name = %s, max_amount = %s
                WHERE scheme_id = %s;
            """, (scheme_name, max_amount, scheme_id))
            return jsonify({"success": True, "message": "Scholarship scheme updated successfully!"})
    except Error as err:
        if err.errno == errorcode.ER_DUP_ENTRY:
            return jsonify({"success": False, "message": "A scheme with this name already exists."}), 409
        return jsonify({"success": False, "message": f"Database error: {err.msg}"}), 500

@app.route('/api/schemes/<int:scheme_id>', methods=['DELETE'])
@admin_required
def api_delete_scheme(scheme_id):
    try:
        with get_db_cursor(commit=True) as cursor:
            # Check if applications reference this scheme
            cursor.execute("SELECT COUNT(*) AS count FROM Applications WHERE scheme_id = %s;", (scheme_id,))
            if cursor.fetchone()['count'] > 0:
                return jsonify({
                    "success": False, 
                    "message": "Cannot delete scheme because existing applications are linked to it. Please archive or reassign applications first."
                }), 409

            cursor.execute("DELETE FROM Schemes WHERE scheme_id = %s;", (scheme_id,))
            return jsonify({"success": True, "message": "Scholarship scheme deleted successfully!"})
    except Error as err:
        return jsonify({"success": False, "message": f"Database error: {err.msg}"}), 500

# =====================================================================
# Applications CRUD APIs
# =====================================================================

@app.route('/api/applications', methods=['GET'])
@login_required
def api_get_applications():
    try:
        status_filter = request.args.get('status')
        scheme_id = request.args.get('scheme_id')
        year = request.args.get('year')
        search = request.args.get('search')

        query = """
            SELECT 
                a.application_id, a.application_year, a.status, a.submission_date,
                s.student_id, CONCAT(s.first_name, ' ', s.last_name) AS student_name,
                s.email AS student_email, s.department, s.current_year,
                sch.scheme_id, sch.scheme_name, sch.max_amount,
                b.account_number, b.ifsc_code, b.bank_name,
                snc.sanction_id, snc.sanctioned_amount, snc.sanction_date,
                dsb.disbursement_id, dsb.disbursed_amount, dsb.disbursement_date, dsb.transaction_ref
            FROM Applications a
            JOIN Students s ON a.student_id = s.student_id
            JOIN Schemes sch ON a.scheme_id = sch.scheme_id
            LEFT JOIN Bank_Details b ON s.student_id = b.student_id
            LEFT JOIN Sanctions snc ON a.application_id = snc.application_id
            LEFT JOIN Disbursements dsb ON snc.sanction_id = dsb.sanction_id
            WHERE 1=1
        """
        params = []

        # Role-based restriction: students can only see their own applications
        if session.get('role') == 'student' and session.get('student_id'):
            query += " AND a.student_id = %s"
            params.append(session.get('student_id'))

        if status_filter:
            if status_filter == 'Disbursed':
                query += " AND dsb.disbursement_id IS NOT NULL"
            elif status_filter == 'Approved':
                query += " AND a.status = 'Approved' AND dsb.disbursement_id IS NULL"
            else:
                query += " AND a.status = %s"
                params.append(status_filter)
        if scheme_id:
            query += " AND a.scheme_id = %s"
            params.append(int(scheme_id))
        if year:
            query += " AND a.application_year = %s"
            params.append(int(year))
        if search:
            query += " AND (s.first_name LIKE %s OR s.last_name LIKE %s OR s.email LIKE %s OR sch.scheme_name LIKE %s)"
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param, search_param])

        query += " ORDER BY a.submission_date DESC, a.application_id DESC;"

        with get_db_cursor() as cursor:
            cursor.execute(query, params)
            apps = serialize_rows(cursor.fetchall())
            return jsonify({"success": True, "data": apps})
    except Error as err:
        return jsonify({"success": False, "message": f"Database error: {err.msg}"}), 500

@app.route('/api/applications', methods=['POST'])
@admin_required
def api_create_application():
    data = request.get_json() or {}
    student_id = data.get('student_id')
    scheme_id = data.get('scheme_id')
    application_year = data.get('application_year')
    submission_date = data.get('submission_date') or datetime.date.today().isoformat()
    status = data.get('status') or 'Pending'

    if not student_id or not scheme_id or not application_year:
        return jsonify({"success": False, "message": "Student, Scheme, and Application Year are required."}), 400

    try:
        student_id = int(student_id)
        scheme_id = int(scheme_id)
        application_year = int(application_year)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid IDs or academic year provided."}), 400

    try:
        with get_db_cursor(commit=True) as cursor:
            # 1. Enforce student existence
            cursor.execute("SELECT student_id FROM Students WHERE student_id = %s;", (student_id,))
            if not cursor.fetchone():
                return jsonify({"success": False, "message": "Selected student does not exist."}), 404

            # 2. Enforce scheme existence
            cursor.execute("SELECT scheme_id, max_amount FROM Schemes WHERE scheme_id = %s;", (scheme_id,))
            scheme = cursor.fetchone()
            if not scheme:
                return jsonify({"success": False, "message": "Selected scholarship scheme does not exist."}), 404

            # 3. Insert Application (Database UNIQUE constraint handles race condition, but we check explicitly too)
            cursor.execute("""
                SELECT application_id FROM Applications 
                WHERE student_id = %s AND scheme_id = %s AND application_year = %s;
            """, (student_id, scheme_id, application_year))
            if cursor.fetchone():
                return jsonify({
                    "success": False, 
                    "message": f"Duplicate Application: This student has already applied for this scheme in the year {application_year}."
                }), 409

            cursor.execute("""
                INSERT INTO Applications (student_id, scheme_id, application_year, status, submission_date)
                VALUES (%s, %s, %s, %s, %s);
            """, (student_id, scheme_id, application_year, status, submission_date))
            
            return jsonify({
                "success": True,
                "message": "Application submitted successfully!",
                "application_id": cursor.lastrowid
            }), 201

    except Error as err:
        if err.errno == errorcode.ER_DUP_ENTRY:
            return jsonify({
                "success": False, 
                "message": "Business Rule Violation: Only one application per scheme per academic year is permitted for a student."
            }), 409
        return jsonify({"success": False, "message": f"Database error: {err.msg}"}), 500

@app.route('/api/applications/<int:app_id>/status', methods=['PUT'])
@admin_required
def api_update_application_status(app_id):
    data = request.get_json() or {}
    new_status = data.get('status')
    if new_status not in ['Pending', 'Verified', 'Approved', 'Rejected']:
        return jsonify({"success": False, "message": "Invalid status value."}), 400

    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("UPDATE Applications SET status = %s WHERE application_id = %s;", (new_status, app_id))
            if cursor.rowcount == 0:
                return jsonify({"success": False, "message": "Application not found."}), 404
            return jsonify({"success": True, "message": f"Application status updated to '{new_status}'."})
    except Error as err:
        return jsonify({"success": False, "message": f"Database error: {err.msg}"}), 500

@app.route('/api/applications/<int:app_id>', methods=['DELETE'])
@admin_required
def api_delete_application(app_id):
    try:
        with get_db_cursor(commit=True) as cursor:
            # 1. Check application exists
            cursor.execute("SELECT application_id FROM Applications WHERE application_id = %s;", (app_id,))
            if not cursor.fetchone():
                return jsonify({"success": False, "message": "Application not found."}), 404

            # 2. Delete linked sanction and its disbursement
            cursor.execute("SELECT sanction_id FROM Sanctions WHERE application_id = %s;", (app_id,))
            sanction = cursor.fetchone()
            if sanction:
                cursor.execute("DELETE FROM Disbursements WHERE sanction_id = %s;", (sanction['sanction_id'],))
                cursor.execute("DELETE FROM Sanctions WHERE sanction_id = %s;", (sanction['sanction_id'],))

            # 3. Delete Application
            cursor.execute("DELETE FROM Applications WHERE application_id = %s;", (app_id,))
            return jsonify({"success": True, "message": "Application record deleted successfully."})
    except Error as err:
        return jsonify({"success": False, "message": f"Database error: {err.msg}"}), 500

# =====================================================================
# Sanctions & Disbursements Workflow APIs
# =====================================================================

@app.route('/api/applications/<int:app_id>/sanction', methods=['POST'])
@admin_required
def api_sanction_application(app_id):
    """Approves an application and issues an institutional sanction record."""
    data = request.get_json() or {}
    sanctioned_amount = data.get('sanctioned_amount')
    sanction_date = data.get('sanction_date') or datetime.date.today().isoformat()

    try:
        sanctioned_amount = float(sanctioned_amount)
        if sanctioned_amount <= 0:
            return jsonify({"success": False, "message": "Sanctioned amount must be greater than zero."}), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Valid numerical sanction amount required."}), 400

    try:
        with get_db_cursor(commit=True) as cursor:
            # Verify application and scheme maximum cap
            cursor.execute("""
                SELECT a.application_id, a.status, sch.max_amount, sch.scheme_name
                FROM Applications a
                JOIN Schemes sch ON a.scheme_id = sch.scheme_id
                WHERE a.application_id = %s;
            """, (app_id,))
            app_record = cursor.fetchone()
            if not app_record:
                return jsonify({"success": False, "message": "Application not found."}), 404

            if sanctioned_amount > float(app_record['max_amount']):
                return jsonify({
                    "success": False, 
                    "message": f"Sanctioned amount (${sanctioned_amount:,.2f}) cannot exceed scheme maximum limit (${float(app_record['max_amount']):,.2f})."
                }), 400

            # Insert or update Sanction
            cursor.execute("""
                INSERT INTO Sanctions (application_id, sanctioned_amount, sanction_date)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    sanctioned_amount = VALUES(sanctioned_amount),
                    sanction_date = VALUES(sanction_date);
            """, (app_id, sanctioned_amount, sanction_date))
            
            # Update application status to 'Approved'
            cursor.execute("UPDATE Applications SET status = 'Approved' WHERE application_id = %s;", (app_id,))

            return jsonify({
                "success": True, 
                "message": f"Application #{app_id} sanctioned for ${sanctioned_amount:,.2f} and marked as Approved!"
            })
    except Error as err:
        return jsonify({"success": False, "message": f"Database error: {err.msg}"}), 500

@app.route('/api/sanctions/<int:sanction_id>/disburse', methods=['POST'])
@admin_required
def api_disburse_sanction(sanction_id):
    """Executes a financial payout/disbursement for an approved sanction."""
    data = request.get_json() or {}
    disbursed_amount = data.get('disbursed_amount')
    disbursement_date = data.get('disbursement_date') or datetime.date.today().isoformat()
    transaction_ref = (data.get('transaction_ref') or '').strip()

    if not transaction_ref:
        # Generate auto transaction reference if not supplied
        transaction_ref = f"TXN{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"

    try:
        disbursed_amount = float(disbursed_amount)
        if disbursed_amount <= 0:
            return jsonify({"success": False, "message": "Disbursed amount must be greater than zero."}), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Valid numerical disbursement amount required."}), 400

    try:
        with get_db_cursor(commit=True) as cursor:
            # Verify sanction details
            cursor.execute("""
                SELECT snc.sanction_id, snc.sanctioned_amount, snc.application_id,
                       a.student_id, b.account_number, b.bank_name
                FROM Sanctions snc
                JOIN Applications a ON snc.application_id = a.application_id
                LEFT JOIN Bank_Details b ON a.student_id = b.student_id
                WHERE snc.sanction_id = %s;
            """, (sanction_id,))
            sanction = cursor.fetchone()
            if not sanction:
                return jsonify({"success": False, "message": "Sanction record not found."}), 404

            # Verify student bank details exist
            if not sanction['account_number']:
                return jsonify({
                    "success": False, 
                    "message": "Cannot disburse funds: Student does not have registered bank account details."
                }), 400

            if disbursed_amount > float(sanction['sanctioned_amount']):
                return jsonify({
                    "success": False, 
                    "message": f"Disbursed amount cannot exceed sanctioned amount (${float(sanction['sanctioned_amount']):,.2f})."
                }), 400

            # Insert disbursement
            cursor.execute("""
                INSERT INTO Disbursements (sanction_id, disbursed_amount, disbursement_date, transaction_ref)
                VALUES (%s, %s, %s, %s);
            """, (sanction_id, disbursed_amount, disbursement_date, transaction_ref))

            return jsonify({
                "success": True, 
                "message": f"Disbursement of ${disbursed_amount:,.2f} recorded under Ref: {transaction_ref}!",
                "transaction_ref": transaction_ref
            })
    except Error as err:
        if err.errno == errorcode.ER_DUP_ENTRY:
            return jsonify({"success": False, "message": "Transaction Reference must be globally unique."}), 409
        return jsonify({"success": False, "message": f"Database error: {err.msg}"}), 500

@app.route('/api/disbursements', methods=['GET'])
@login_required
def api_get_disbursements():
    try:
        query = """
            SELECT 
                dsb.disbursement_id, dsb.disbursed_amount, dsb.disbursement_date, dsb.transaction_ref,
                snc.sanction_id, snc.sanctioned_amount, snc.sanction_date,
                a.application_id, a.application_year,
                s.student_id, CONCAT(s.first_name, ' ', s.last_name) AS student_name,
                s.department,
                sch.scheme_name,
                b.bank_name, b.account_number, b.ifsc_code
            FROM Disbursements dsb
            JOIN Sanctions snc ON dsb.sanction_id = snc.sanction_id
            JOIN Applications a ON snc.application_id = a.application_id
            JOIN Students s ON a.student_id = s.student_id
            JOIN Schemes sch ON a.scheme_id = sch.scheme_id
            LEFT JOIN Bank_Details b ON s.student_id = b.student_id
            WHERE 1=1
        """
        params = []

        # Role-based restriction: students can only see their own disbursements
        if session.get('role') == 'student' and session.get('student_id'):
            query += " AND a.student_id = %s"
            params.append(session.get('student_id'))

        query += " ORDER BY dsb.disbursement_date DESC, dsb.disbursement_id DESC;"

        with get_db_cursor() as cursor:
            cursor.execute(query, params)
            disbursements = serialize_rows(cursor.fetchall())
            return jsonify({"success": True, "data": disbursements})
    except Error as err:
        return jsonify({"success": False, "message": f"Database error: {err.msg}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Config.PORT, debug=Config.DEBUG)
