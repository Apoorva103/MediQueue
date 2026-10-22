import os
import csv
import sqlite3
from io import StringIO
from flask import Flask, render_template, request, redirect, url_for, session, Response

app = Flask(__name__)
# Secret key required for Flask session management
app.secret_key = "mediqueue_super_secret_key_123"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'hospital.db')

STAFF_PASSWORD = "admin"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/")
def home():
    search_query = request.args.get("search", "").strip()
    conn = get_db_connection()
    cursor = conn.cursor()

    if search_query:
        cursor.execute("""
            SELECT * FROM patients 
            WHERE token_number LIKE ? OR name LIKE ?
            ORDER BY CASE WHEN urgency = 'Emergency' THEN 0 ELSE 1 END, id ASC
        """, (f"%{search_query}%", f"%{search_query}%"))
    else:
        cursor.execute("""
            SELECT * FROM patients 
            WHERE status != 'Completed' AND status != 'Cancelled'
            ORDER BY CASE WHEN urgency = 'Emergency' THEN 0 ELSE 1 END, id ASC
        """)
    
    patients_raw = cursor.fetchall()

    avg_consultation_minutes = 15
    department_waiting_counts = {}
    
    patients = []
    for p in patients_raw:
        p_dict = dict(p)
        dept = p_dict['department']
        
        if p_dict['status'] == 'Waiting':
            ahead_count = department_waiting_counts.get(dept, 0)
            p_dict['est_wait'] = f"{ahead_count * avg_consultation_minutes} mins"
            department_waiting_counts[dept] = ahead_count + 1
        else:
            p_dict['est_wait'] = "In Progress"
            
        patients.append(p_dict)

    cursor.execute("SELECT COUNT(*) FROM patients")
    total_registered = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM patients WHERE status = 'Waiting'")
    waiting_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM patients WHERE status = 'In Consultation'")
    consultation_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM patients WHERE status = 'Completed'")
    completed_count = cursor.fetchone()[0]

    conn.close()

    # Check if staff is logged in
    is_logged_in = session.get("logged_in", False)

    return render_template(
        "index.html",
        patients=patients,
        total_registered=total_registered,
        waiting_count=waiting_count,
        consultation_count=consultation_count,
        completed_count=completed_count,
        search_query=search_query,
        is_logged_in=is_logged_in
    )

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        password = request.form.get("password")
        if password == STAFF_PASSWORD:
            session["logged_in"] = True
            session.modified = True  # Force Flask to save the session cookie
            return redirect(url_for("home"))
        else:
            error = "Invalid Staff Password! Try 'admin'."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("home"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        age = request.form.get("age")
        department = request.form.get("department")
        reason = request.form.get("reason")
        urgency = request.form.get("urgency", "Normal")

        if not name or not age or not department or not reason:
            return "Error: All fields are required!", 400

        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM patients WHERE department = ?", (department,))
        count = cursor.fetchone()[0] + 1
        
        dept_prefix = department[:4].upper()
        token_number = f"{dept_prefix}-{100 + count}"

        cursor.execute('''
            INSERT INTO patients (token_number, name, age, department, reason, urgency, status)
            VALUES (?, ?, ?, ?, ?, ?, 'Waiting')
        ''', (token_number, name, int(age), department, reason, urgency))

        conn.commit()
        conn.close()

        return redirect(url_for('home'))

    return render_template("register.html")

@app.route("/toggle_urgency/<int:patient_id>", methods=["POST"])
def toggle_urgency(patient_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT urgency FROM patients WHERE id = ?", (patient_id,))
    patient = cursor.fetchone()
    
    if patient:
        new_urgency = "Emergency" if patient["urgency"] == "Normal" else "Normal"
        cursor.execute("UPDATE patients SET urgency = ? WHERE id = ?", (new_urgency, patient_id))
        conn.commit()
    
    conn.close()
    return redirect(url_for('home'))

@app.route("/update_status/<int:patient_id>/<string:new_status>", methods=["POST"])
def update_status(patient_id, new_status):
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    if new_status in ['Waiting', 'In Consultation', 'Completed', 'Cancelled']:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE patients SET status = ? WHERE id = ?", (new_status, patient_id))
        conn.commit()
        conn.close()
    return redirect(url_for('home'))

@app.route("/export_report")
def export_report():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT token_number, name, age, department, urgency, status, registration_time FROM patients")
    rows = cursor.fetchall()
    conn.close()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Token Number', 'Name', 'Age', 'Department', 'Urgency', 'Status', 'Registration Time'])
    
    for row in rows:
        cw.writerow(list(row))

    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=MediQueue_Daily_Report.csv"}
    )

if __name__ == "__main__":
    app.run(debug=True)