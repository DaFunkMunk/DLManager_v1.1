from flask import Flask, send_from_directory, jsonify, request, session, redirect, url_for, render_template
import pyodbc
import os
import datetime
import subprocess
from datetime import timedelta
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None

from adapters.base import DirectoryAdapter
from adapters.standard_adapter import StandardAdapter
from adapters.demo_adapter import DemoAdapter

#python app.py 
#start chrome --app=http://127.0.0.1:5000

if load_dotenv:
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = Flask(__name__)
app.secret_key = 'your-secret-key'  # Required for sessions
app.permanent_session_lifetime = timedelta(minutes=10)  # Auto-expire after 10 minutes

# Hardcoded users (add more here)
USERS = {
    "jdoe": "password123",
    "admin": "adminpass"
}

# SQL Server connection string
conn_str = (
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=HOU-SQLOP-P1;"
    "Database=DListDB;"
    "Trusted_Connection=yes;"
)

# Absolute path to the log file
LOG_FILE = os.path.join(os.path.dirname(__file__), "log.txt")

MODE_STANDARD = "standard"
MODE_DEMO = "demo"
MODE_DEFAULT = os.getenv("DEFAULT_MODE", MODE_STANDARD).lower()

standard_adapter = StandardAdapter(conn_str=conn_str)
_demo_adapter: Optional[DirectoryAdapter] = None


def _get_demo_adapter() -> Optional[DirectoryAdapter]:
    global _demo_adapter
    if _demo_adapter is not None:
        return _demo_adapter

    mongo_uri = os.getenv("DEMO_MONGO_URI")
    if not mongo_uri:
        if MODE_DEFAULT == MODE_DEMO:
            print("DEFAULT_MODE is set to 'demo' but DEMO_MONGO_URI is missing in the environment.")
        return None

    db_name = os.getenv("DEMO_MONGO_DB", "dl_demo")
    try:
        adapter = DemoAdapter(mongo_uri=mongo_uri, db_name=db_name)
    except NotImplementedError:
        print("DemoAdapter is not implemented; ensure demo adapter support is available.")
        return None
    except Exception as exc:  # pragma: no cover - defensive
        print(f"Failed to initialise DemoAdapter: {exc}")
        return None

    _demo_adapter = adapter
    return _demo_adapter


def _resolve_mode() -> str:
    mode = request.headers.get("X-Mode") or request.args.get("mode") or MODE_DEFAULT
    return str(mode).lower()


def get_directory_adapter() -> DirectoryAdapter:
    mode = _resolve_mode()
    if mode == MODE_DEMO:
        demo_adapter = _get_demo_adapter()
        if demo_adapter is not None:
            return demo_adapter
        print("Demo adapter unavailable; defaulting to standard adapter.")
    return standard_adapter

@app.before_request
def require_login():
    session.permanent = True
    if 'user' in session:
        return

    if request.endpoint in ('login', 'get_log_file', 'api_me', 'api_logout', 'static', 'serve_banner'):
        return

    if request.path.startswith('/api/'):
        return jsonify({"error": "auth_required"}), 401

    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in USERS and USERS[username] == password:
            session['user'] = username
            return redirect('/')
        else:
            return render_template("login.html", error="Invalid username or password")
    return render_template("login.html", error=None)

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')

def append_to_log(entry):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception as e:
        print("Failed to write to log.txt:", str(e))

@app.route('/api/logs')
def get_log_file():
    if not os.path.exists(LOG_FILE):
        return "", 200
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return f.read(), 200


@app.route('/api/me')
def api_me():
    user = session.get('user')
    if not user:
        return jsonify({"authenticated": False}), 401
    return jsonify({"authenticated": True, "user": user})


@app.route('/api/group-members')
def api_group_members():
    group_ref = (request.args.get('group') or '').strip()
    if not group_ref:
        return jsonify({'error': 'Group is required.'}), 400

    adapter = get_directory_adapter()
    memberships_fn = getattr(adapter, 'group_memberships', None)
    if not callable(memberships_fn):
        return jsonify({'error': 'Group membership lookup is not supported in this mode.'}), 501
    try:
        members = memberships_fn(group_ref)
    except NotImplementedError:
        return jsonify({'error': 'Group membership lookup is not supported in this mode.'}), 501
    except Exception as exc:  # pragma: no cover - defensive
        return jsonify({'error': str(exc)}), 500

    return jsonify(members)


@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.pop('user', None)
    return jsonify({"ok": True})

# @app.route('/Coterra-Logo.png')
# def serve_banner():
#     return send_from_directory('.', 'Coterra-Logo.png')

@app.route('/')
def serve_homepage():
    return send_from_directory('.', 'DLWebApp.html')

@app.route('/styles.css')
def serve_css():
    return send_from_directory('.', 'styles.css')

@app.route('/app.js')
def serve_js():
    return send_from_directory('.', 'app.js')


@app.route('/api/users')
def api_users():
    adapter = get_directory_adapter()
    query = request.args.get("q")
    try:
        users = adapter.list_users(query)
    except NotImplementedError:
        return jsonify({"error": "Not supported in current mode."}), 501
    except Exception as exc:  # pragma: no cover - defensive
        return jsonify({"error": str(exc)}), 500
    return jsonify(users)


@app.route('/api/groups')
def api_groups():
    adapter = get_directory_adapter()
    query = request.args.get("q")
    try:
        groups = adapter.list_groups(query)
    except NotImplementedError:
        return jsonify({"error": "Not supported in current mode."}), 501
    except Exception as exc:  # pragma: no cover - defensive
        return jsonify({"error": str(exc)}), 500
    return jsonify(groups)


@app.route('/api/propose', methods=['POST'])
def api_propose():
    adapter = get_directory_adapter()
    intent = request.get_json(force=True, silent=True) or {}
    try:
        result = adapter.propose(intent)
    except NotImplementedError:
        return jsonify({"error": "Not supported in current mode."}), 501
    except Exception as exc:  # pragma: no cover - defensive
        return jsonify({"error": str(exc)}), 500
    if "error" in result:
        return jsonify(result), 400

    return jsonify(result)


@app.route('/api/apply', methods=['POST'])
def api_apply():
    adapter = get_directory_adapter()
    payload = request.get_json(force=True, silent=True) or {}
    diff_id = payload.get("diffId")
    actor = session.get("user", "anonymous")
    if not diff_id:
        return jsonify({"error": "diffId is required."}), 400
    try:
        result = adapter.apply(diff_id, actor)
    except NotImplementedError:
        return jsonify({"error": "Not supported in current mode."}), 501
    except Exception as exc:  # pragma: no cover - defensive
        return jsonify({"error": str(exc)}), 500
    if "error" in result:
        return jsonify(result), 400

    summary = result.get("summary") or {}
    timestamp = datetime.datetime.now().strftime("%d/%b/%Y %H:%M:%S")
    group_name = summary.get("groupName") or summary.get("groupId") or "(unknown)"
    rule = summary.get("rule") or {}
    rule_label = rule.get("label") or rule.get("type") or "Rule"
    rule_value = rule.get("expression") or rule.get("value") or "(none)"
    added = summary.get("added") or {}
    removed = summary.get("removed") or {}
    added_count = added.get("count", 0)
    removed_count = removed.get("count", 0)
    added_names = ", ".join(added.get("names", [])) or "-"
    removed_names = ", ".join(removed.get("names", [])) or "-"
    policy_notes = summary.get("policyNotes") or []
    policy_text = "; ".join(policy_notes) if policy_notes else "None"

    log_lines = [
        f'Group: {group_name}',
        f'Rule: {rule_label} -> {rule_value}',
        f'Added: {added_count} ({added_names})',
        f'Removed: {removed_count} ({removed_names})',
        f'Audit: {result.get("auditId", "-")}',
        f'Policy Notes: {policy_text}',
    ]
    log_entry = (
        f'{actor} @ 127.0.0.1 - - [{timestamp}] "POST /api/apply HTTP/1.1" 200 - SUCCESS\n'
        + "\n".join(f"  {line}" for line in log_lines)
    )
    append_to_log(log_entry)

    return jsonify(result)



@app.route('/api/expression/validate', methods=['POST'])
def api_validate_expression():
    adapter = get_directory_adapter()
    body = request.get_json(force=True, silent=True) or {}
    expression = (body.get('expression') or '').strip()
    if not expression:
        return jsonify({'error': 'Expression is required.'}), 400
    validate = getattr(adapter, 'validate_expression', None)
    if not callable(validate):
        return jsonify({'error': 'Expression validation not supported in current mode.'}), 501
    try:
        result = validate(expression)
    except NotImplementedError:
        return jsonify({'error': 'Expression validation not supported in current mode.'}), 501
    except Exception as exc:  # pragma: no cover - defensive
        return jsonify({'error': str(exc)}), 500
    return jsonify(result)

@app.route('/api/audit')
def api_audit():
    adapter = get_directory_adapter()
    try:
        entries = adapter.audit()
    except NotImplementedError:
        return jsonify({"error": "Not supported in current mode."}), 501
    except Exception as exc:  # pragma: no cover - defensive
        return jsonify({"error": str(exc)}), 500
    return jsonify(entries)

@app.route('/api/lists')
def get_dl_lists():
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT DL_NAME FROM DL_Header")
    rows = cursor.fetchall()
    conn.close()
    list_names = [row.DL_NAME for row in rows]
    return jsonify(list_names)

@app.route('/api/rules/<dl_name>')
def get_rules_for_dl(dl_name):
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute("SELECT DLID FROM DL_Header WHERE DL_NAME = ?", dl_name)
    row = cursor.fetchone()
    if not row:
        return jsonify([])

    dlid = row.DLID
    cursor.execute(
        '''
        SELECT TYPE_FLAG AS Flag, 'Location' AS RuleType, '' AS Value
        FROM dbo.DL_RULE_LOC 
        WHERE DLID = ?
        UNION 
        SELECT TYPE_FLAG AS Flag, 'Tree' AS RuleType, E.EmployeeName AS Value
        FROM dbo.PS_DL_RULE_TREE T
        JOIN dbo.Employee_List E ON T.EMP_NAME = E.EmployeeName 
        WHERE T.DLID = ?
        UNION 
        SELECT TYPE_FLAG AS Flag, 'User' AS RuleType, E.EmployeeName AS Value
        FROM dbo.PS_DL_RULE_USER U
        JOIN dbo.Employee_List E ON U.EMP_NAME = E.EmployeeName 
        WHERE U.DLID = ?
        ''',
        dlid, dlid, dlid
    )
    rows = cursor.fetchall()
    conn.close()
    rule_data = [{"Flag": r.Flag, "RuleType": r.RuleType, "Value": r.Value} for r in rows]
    return jsonify(rule_data)

@app.route('/api/preview/<dl_name>')
def get_preview_for_dl(dl_name):
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute("SELECT DLID FROM DL_Header WHERE DL_NAME = ?", dl_name)
    row = cursor.fetchone()
    if not row:
        return jsonify([])

    dlid = row.DLID
    try:
        cursor.execute("{CALL LIST_PREVIEW (?)}", dlid)
        preview_rows = cursor.fetchall()
        conn.close()
        names = [r[0] for r in preview_rows]
        return jsonify(names)
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/treepreview/<dl_name>/<manager>')
def tree_preview(dl_name, manager):
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute("SELECT DLID FROM DL_Header WHERE DL_NAME = ?", dl_name)
    row = cursor.fetchone()
    if not row:
        return jsonify([])

    dlid = row.DLID
    try:
        cursor.execute("{CALL TREE_PREVIEW (?, ?)}", manager, dlid)
        rows = cursor.fetchall()
        conn.close()
        names = [r[0] for r in rows]
        return jsonify(names)
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/employees')
def get_employee_names():
    adapter = get_directory_adapter()
    mode = _resolve_mode()
    try:
        if mode == MODE_DEMO and isinstance(adapter, DemoAdapter):
            users = adapter.list_users()
            return jsonify([{"name": user["name"], "id": user["email"]} for user in users])

        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        cursor.execute("SELECT EmployeeName, EmployeeID FROM dbo.Employee_List ORDER BY EmployeeName ASC")
        rows = cursor.fetchall()
        conn.close()
        return jsonify([{"name": row.EmployeeName, "id": row.EmployeeID} for row in rows])
    except Exception as exc:
        if mode == MODE_DEMO:
            return jsonify({"error": str(exc)}), 500
        raise

@app.route('/api/addrule', methods=['POST'])
def add_rule():
    data = request.get_json()
    flag = data['flag']
    rule_type = data['type']
    value = data['value']
    dl_name = data['dlName']
    user = session.get('user', 'anonymous')

    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute("SELECT DLID FROM DL_Header WHERE DL_NAME = ?", dl_name)
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "error": "DL not found"}), 400

    dlid = row.DLID
    try:
        if rule_type == 'Location':
            cursor.execute("INSERT INTO dbo.DL_RULE_LOC VALUES (?, ?, ?)", dlid, value, flag)
        elif rule_type == 'Tree':
            cursor.execute("INSERT INTO dbo.PS_DL_RULE_TREE VALUES (?, ?, ?)", dlid, value, flag)
        elif rule_type == 'User':
            cursor.execute("INSERT INTO dbo.PS_DL_RULE_USER VALUES (?, ?, ?)", dlid, value, flag)
        else:
            conn.close()
            return jsonify({"success": False, "error": "Invalid rule type"}), 400

        conn.commit()
        timestamp = datetime.datetime.now().strftime("%d/%b/%Y %H:%M:%S")
        log_entry = f'{user} @ 127.0.0.1 - - [{timestamp}] "POST /api/addrule HTTP/1.1" 200 -  → Details: flag={flag}, type={rule_type}, value={value}, dlName={dl_name}'
        append_to_log(log_entry)

        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        conn.close()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/deleterule', methods=['POST'])
def delete_rule():
    data = request.get_json()
    flag = data['flag']
    rule_type = data['type']
    value = data['value']
    dl_name = data['dlName']
    user = session.get('user', 'anonymous')

    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute("SELECT DLID FROM DL_Header WHERE DL_NAME = ?", dl_name)
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "error": "DL not found"}), 400

    dlid = row.DLID
    try:
        if rule_type == 'Location':
            cursor.execute("DELETE FROM dbo.DL_RULE_LOC WHERE DLID=? AND E_Location=?", dlid, value)
        elif rule_type == 'Tree':
            cursor.execute("DELETE FROM dbo.PS_DL_RULE_TREE WHERE DLID=? AND EMP_NAME=?", dlid, value)
        elif rule_type == 'User':
            cursor.execute("DELETE FROM dbo.PS_DL_RULE_USER WHERE DLID=? AND EMP_NAME=?", dlid, value)
        else:
            conn.close()
            return jsonify({"success": False, "error": "Invalid rule type"}), 400

        conn.commit()
        timestamp = datetime.datetime.now().strftime("%d/%b/%Y %H:%M:%S")
        log_entry = f'{user} @ 127.0.0.1 - - [{timestamp}] "POST /api/deleterule HTTP/1.1" 200 -  → Details: flag={flag}, type={rule_type}, value={value}, dlName={dl_name}'
        append_to_log(log_entry)

        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        conn.close()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/locations')
def get_locations():
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT E_Location FROM dbo.Employee_List WHERE E_Location NOT IN ('', '-') ORDER BY E_Location ASC")
    rows = cursor.fetchall()
    conn.close()
    return jsonify([row.E_Location for row in rows])

@app.route('/api/applyrules', methods=['POST'])
def apply_rules():
    user = session.get('user', 'anonymous')
    timestamp = datetime.datetime.now().strftime("%d/%b/%Y %H:%M:%S")

    script_path = r'\\cabotog.com\cogroot\corporate\prod\Procount\Distribution Lists\GroupUpload.ps1'
    command = ["powershell", "-ExecutionPolicy", "Bypass", "-File", script_path]

    try:
        result = subprocess.run(command, capture_output=True, text=True)
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        exit_code = result.returncode

        # Consider it failure if either:
        # - exit code is non-zero
        # - stderr contains anything significant
        error_occurred = exit_code != 0 or ("error" in stderr.lower() or stderr.strip())

        status = "FAILURE" if error_occurred else "SUCCESS"

        log_entry = (
            f'{user} @ 127.0.0.1 - - [{timestamp}] "POST /api/applyrules HTTP/1.1" {exit_code} - {status}\n'
            f'  → Command: {" ".join(command)}\n'
            f'  → Exit Code: {exit_code}\n'
            f'  → STDOUT:\n{stdout or "(empty)"}\n'
            f'  → STDERR:\n{stderr or "(empty)"}'
        )
        append_to_log(log_entry)

        if error_occurred:
            return jsonify({
                "success": False,
                "error": "Script error detected.",
                "details": stderr
            }), 500

        return jsonify({"success": True, "message": stdout})
    except Exception as e:
        err_log = f'{user} @ 127.0.0.1 - - [{timestamp}] "POST /api/applyrules HTTP/1.1" 500 - ERROR\n  → Exception: {str(e)}'
        append_to_log(err_log)
        return jsonify({"success": False, "error": str(e)}), 500
    
@app.route('/api/refreshad', methods=['POST'])
def refresh_ad():
    user = session.get('user', 'anonymous')
    timestamp = datetime.datetime.now().strftime("%d/%b/%Y %H:%M:%S")

    script_path = r'\\cabotog.com\cogroot\corporate\prod\Procount\Distribution Lists\NewAdRefresh.ps1'
    command = ["powershell", "-ExecutionPolicy", "Bypass", "-File", script_path]

    try:
        result = subprocess.run(command, capture_output=True, text=True)
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        exit_code = result.returncode

        error_occurred = exit_code != 0 or ("error" in stderr.lower() or stderr.strip())

        status = "FAILURE" if error_occurred else "SUCCESS"

        log_entry = (
            f'{user} @ 127.0.0.1 - - [{timestamp}] "POST /api/refreshad HTTP/1.1" {exit_code} - {status}\n'
            f'  → Command: {" ".join(command)}\n'
            f'  → Exit Code: {exit_code}\n'
            f'  → STDOUT:\n{stdout or "(empty)"}\n'
            f'  → STDERR:\n{stderr or "(empty)"}'
        )
        append_to_log(log_entry)

        if error_occurred:
            return jsonify({
                "success": False,
                "error": "Refresh script error detected.",
                "details": stderr
            }), 500

        return jsonify({"success": True, "message": stdout})
    except Exception as e:
        err_log = f'{user} @ 127.0.0.1 - - [{timestamp}] "POST /api/refreshad HTTP/1.1" 500 - ERROR\n  → Exception: {str(e)}'
        append_to_log(err_log)
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
