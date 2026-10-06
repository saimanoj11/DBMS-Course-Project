import json
from app import app

def run_tests():
    client = app.test_client()
    print("=" * 60)
    print("SCHOLARSHIP MANAGEMENT SYSTEM: RBAC & FUNCTIONAL VERIFICATION")
    print("=" * 60)

    # 1. Unauthenticated checks
    print("\n--- 1. Testing Unauthenticated Access Guards ---")
    res = client.get('/')
    print(f"GET / (unauthenticated) -> Status {res.status_code} (Redirected to: {res.headers.get('Location')})")
    assert res.status_code == 302
    assert '/login' in res.headers.get('Location', '')

    res = client.get('/api/dashboard/stats')
    print(f"GET /api/dashboard/stats (unauthenticated) -> Status {res.status_code}")
    assert res.status_code == 401

    res = client.get('/api/students')
    print(f"GET /api/students (unauthenticated) -> Status {res.status_code}")
    assert res.status_code == 401

    # 2. Student Login & Isolation
    print("\n--- 2. Testing Student Role: sai.manoj@univ.edu (Student ID: 5) ---")
    res = client.post('/login', json={'username': 'sai.manoj@univ.edu', 'password': 'student123'})
    data = res.get_json()
    print(f"POST /login -> Status {res.status_code}, Role: {data.get('role')}, Welcome: {data.get('message')}")
    assert res.status_code == 200
    assert data.get('role') == 'student'

    # Student accessing students list (should only see their own record)
    res = client.get('/api/students')
    stu_data = res.get_json()['data']
    print(f"GET /api/students -> Returned {len(stu_data)} student(s). ID: {stu_data[0]['student_id']}, Name: {stu_data[0]['first_name']} {stu_data[0]['last_name']}")
    assert len(stu_data) == 1
    assert stu_data[0]['student_id'] == 5

    # Student accessing applications (should only see applications for student 5)
    res = client.get('/api/applications')
    app_data = res.get_json()['data']
    print(f"GET /api/applications -> Returned {len(app_data)} application(s) for student #5")
    for a in app_data:
        assert a['student_id'] == 5

    # Student attempting mutation operations (MUST return 403 Forbidden)
    print("\n--- Testing Student Write Restrictions (Should be 403 Forbidden) ---")
    mutations = [
        ('POST /api/students', client.post('/api/students', json={'first_name': 'Hacker', 'last_name': 'Test', 'email': 'hack@univ.edu', 'department': 'CS', 'current_year': 1})),
        ('POST /api/schemes', client.post('/api/schemes', json={'scheme_name': 'Hack Scheme', 'max_amount': 99999})),
        ('POST /api/applications', client.post('/api/applications', json={'student_id': 5, 'scheme_id': 1, 'application_year': 2026})),
        ('PUT /api/applications/1/status', client.put('/api/applications/1/status', json={'status': 'Approved'})),
        ('DELETE /api/students/1', client.delete('/api/students/1')),
        ('POST /api/applications/1/sanction', client.post('/api/applications/1/sanction', json={'sanctioned_amount': 50000})),
        ('POST /api/sanctions/1/disburse', client.post('/api/sanctions/1/disburse', json={'disbursed_amount': 50000}))
    ]

    for label, res in mutations:
        json_res = res.get_json()
        print(f"  * {label} -> Status {res.status_code} | Msg: {json_res.get('message')}")
        assert res.status_code == 403, f"Expected 403 for {label} but got {res.status_code}"

    # 3. Admin Login & Full CRUD Permissions
    print("\n--- 3. Testing Admin Role: admin (Full CRUD) ---")
    client.get('/logout') # clear student session
    res = client.post('/login', json={'username': 'admin', 'password': 'admin123'})
    data = res.get_json()
    print(f"POST /login -> Status {res.status_code}, Role: {data.get('role')}")
    assert res.status_code == 200
    assert data.get('role') == 'admin'

    # Admin accessing all students
    res = client.get('/api/students')
    all_students = res.get_json()['data']
    print(f"GET /api/students as Admin -> Returned {len(all_students)} total student records")
    assert len(all_students) >= 5

    # Admin accessing all applications
    res = client.get('/api/applications')
    all_apps = res.get_json()['data']
    print(f"GET /api/applications as Admin -> Returned {len(all_apps)} total applications")
    assert len(all_apps) >= 5

    # Admin dashboard metrics
    res = client.get('/api/dashboard/stats')
    stats = res.get_json()['data']
    print(f"GET /api/dashboard/stats as Admin -> Total Students: {stats['total_students']}, Total Schemes: {stats['total_schemes']}, Sanctioned: INR {stats['total_sanctioned']:,.2f}, Disbursed: INR {stats['total_disbursed']:,.2f}")
    assert stats['total_students'] >= 5

    # Admin creating and deleting a temporary test scheme to verify CRUD
    print("\n--- Admin Mutation Verification (Create & Delete Test Scheme) ---")
    res = client.post('/api/schemes', json={'scheme_name': 'Test Verification Scheme 2026', 'max_amount': 75000})
    print(f"POST /api/schemes -> Status {res.status_code}, Msg: {res.get_json().get('message')}")
    assert res.status_code == 201
    scheme_id = res.get_json()['scheme_id']

    res = client.delete(f'/api/schemes/{scheme_id}')
    print(f"DELETE /api/schemes/{scheme_id} -> Status {res.status_code}, Msg: {res.get_json().get('message')}")
    assert res.status_code == 200

    print("\n" + "=" * 60)
    print("ALL RBAC AND DATA ISOLATION TESTS PASSED SUCCESSFULLY! (100% OK)")
    print("=" * 60)

if __name__ == '__main__':
    run_tests()
