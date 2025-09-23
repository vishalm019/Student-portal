import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime,timedelta,timezone
from flask import Flask, request, jsonify
import random
from db_config import DB_CONFIG
import string
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt,create_refresh_token
from functools import wraps

app = Flask(__name__)
app.secret_key = 'my_key'
app.config["JWT_SECRET_KEY"] = 'my_jwt_secret_key'
jwt = JWTManager(app)

def json_validate(required_fields):
    payload = request.json
    missing = []
    for field in required_fields:
        value = payload.get(field)
        if value is None or str(value).strip() == "":
            missing.append(field)
    return missing


def execute_query(query, params=None, fetch=False, get_one=False, as_dict=False):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor_factory = RealDictCursor if as_dict else None
    cur = conn.cursor(cursor_factory=cursor_factory)
    try:
        print(query,params)
        cur.execute(query, params)
        conn.commit()
        if fetch:
            if get_one:
                result = cur.fetchone()
            else:
                result = cur.fetchall()
        else:
            result = None
        return result
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

@app.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    new_access_token = create_access_token(identity=identity)
    return {"access_token": new_access_token}

@app.route('/login', methods=['POST'])
def login():
    username = request.json.get('username')
    password = request.json.get('password')
    query = "SELECT email FROM user_table WHERE email = %s AND password = %s"
    params = (username,password)
    result = execute_query(query,params, fetch=True, get_one=True)
    print(result)
    if result is None:
        return jsonify({"status_code":500,"status": "Invalid credentials"})
    access_token = create_access_token(identity=result[0])
    refresh_token = create_refresh_token(identity=result[0])   
    return jsonify({"status": "success", "token": access_token,"refresh_token":refresh_token})


# User Endpoints
@app.route('/insert_user', methods=['POST'])
@jwt_required()
def insert_user():
    try:
        userid = request.json.get('userid')
        name = request.json.get('name')
        email = request.json.get('email')
        user_type = request.json.get('user_type')
        pwd = ''.join(random.choices(string.ascii_letters, k=5))

        validate = ["name","email","userid"]
        missing = json_validate(validate)
        if missing:
            return jsonify({'status_code': 400,'status': 'Failed','message':"Please fill these fields:{value}".format(value=missing)})
        
        chck = """SELECT user_type FROM user_table WHERE userid = %s"""
        params = (userid,)
        verify = execute_query(chck,params,fetch=True,get_one=True)
        if verify is None:
            return jsonify({'status_code':500,'status':'Invalid userid'})
        if verify[0] != 'A':
            return jsonify({'status_code':403,'status':'Forbidden access'})
        query = "INSERT INTO user_table (name, email, password,user_type) VALUES (%s, %s, %s,%s) RETURNING userid"
        params = (name,email,pwd,user_type)
        result = execute_query(query, params, fetch=True, get_one=True, as_dict=False)
        print(result,'result')
        if result is not None:
            return jsonify({"status_code": 200, "status": "User added", "userid": result[0]})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"})

@app.route('/get_users', methods=['GET'])
@jwt_required()
def get_users():
    try:
        dummy = []
        query = "SELECT userid, name, email FROM user_table"
        users = execute_query(query, fetch=True, as_dict=True)
        for i in users:
            dummy.append(i)
        return jsonify({"status": "Users fetched", "data": dummy})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"})

@app.route('/update_user', methods=['POST'])
@jwt_required()
def update_user():
    try:
        userid = request.json.get('userid')
        name = request.json.get('name')
        email = request.json.get('email')
        password = request.json.get('password')
        validate = ["name","email","userid","password"]
        missing = json_validate(validate)
        if missing:
            return jsonify({'status_code': 400,'status': 'Failed','message':"Please fill these fields:{value}".format(value=missing)})
        chck = """SELECT user_type FROM user_table WHERE userid = %s"""
        params = (userid,)
        verify = execute_query(chck,params,fetch=True,get_one=True)
        if verify is None:
            return jsonify({'status_code':500,'status':'Invalid userid'})
        if verify[0] != 'A':
            return jsonify({'status_code':403,'status':'Forbidden access'})
        query = "UPDATE user_table SET name = %s, email = %s,password = %s WHERE userid = %s"
        params = (name,email,password,userid,)
        execute_query(query, params)
        return jsonify({"status_code":200,"status": "User updated successfully"})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"})

@app.route('/delete_user', methods=['POST'])
@jwt_required()
def delete_user():
    try:
        userid = request.json.get('userid')
        validate = ["userid"]
        missing = json_validate(validate)
        if missing:
            return jsonify({'status_code': 400,'status': 'Failed','message':"Please fill these fields:{value}".format(value=missing)})
        
        chck = """SELECT user_type FROM user_table WHERE userid = %s"""
        params = (userid,)
        verify = execute_query(chck,params,fetch=True,get_one=True)
        if verify is None:
            return jsonify({'status_code':500,'status':'Invalid userid'})
        if verify[0] != 'A':
            return jsonify({'status_code':403,'status':'Forbidden access'})
        query2 = "DELETE FROM task WHERE userid = %s"
        params = (userid,)
        execute_query(query2,params)
        query = "DELETE FROM user_table WHERE userid = %s"
        execute_query(query,params)
        return jsonify({"status_code":200,"status": "User deleted successfully"})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"})

# Task Endpoints
@app.route('/add_task', methods=['POST'])
@jwt_required()
def add_task():
    try:
        userid = request.json.get('userid')
        title = request.json.get('title')
        description = request.json.get('description')
        due_date = request.json.get('due_date')
        priority = request.json.get('priority')
        status = request.json.get('status')
        validate = ["userid","title","description","due_date","priority","status"]
        missing = json_validate(validate)
        if missing:
            return jsonify({'status_code': 400,'status': 'Failed','message':"Please fill these fields:{value}".format(value=missing)})
        
        chck = """SELECT user_type FROM user_table WHERE userid = %s"""
        params = (userid,)
        verify = execute_query(chck,params,fetch=True,get_one=True)
        if verify is None:
            return jsonify({'status_code':500,'status':'Invalid userid'})
        if verify[0] != 'A':
            return jsonify({'status_code':403,'status':'Forbidden access'})
        query = "INSERT INTO task (userid, title, description, due_date, priority, status) VALUES (%s, %s, %s, %s, %s, %s)"
        params = (userid,title,description,due_date,priority,status)
        execute_query(query, params)
        return jsonify({"status": "Successfully added task"})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"})

@app.route('/get_task', methods=['POST'])
@jwt_required()
def get_task():
    try:
        userid = request.json.get('userid')
        validate = ["userid"]
        missing = json_validate(validate)
        if missing:
            return jsonify({'status_code': 400,'status': 'Failed','message':"Please fill these fields:{value}".format(value=missing)})
        user_exists_query = "SELECT userid FROM user_table WHERE userid = %s"
        params = (userid,)
        user_exists = execute_query(user_exists_query,params, fetch=True, get_one=True)
        if not user_exists:
            return jsonify({"status_code": 404, "status": "User not found"})
        query = "SELECT task_id, title, description, priority, status, due_date FROM task WHERE userid = %s"
        params = (userid,)
        tasks = execute_query(query,params, fetch=True, as_dict=True)
        if not tasks:
            return jsonify({"status_code": 404, "status": "Task data does not exist"})
        
        for task in tasks:
            if isinstance(task.get('due_date'), datetime):
                task['due_date'] = task['due_date'].isoformat()
            
        return jsonify({"status": "Successfully fetched tasks", "details": tasks})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"})

@app.route('/all_tasks', methods=['GET'])
@jwt_required()
def all_tasks():
    try:
        priority = request.json.get('priority')
        status = request.json.get('status')
        due_date = request.json.get('due_date')
        description = request.json.get('description')
        title = request.json.get('title')
        userid = request.json.get('userid')
        validate = ["userid"]
        missing = json_validate(validate)
        if missing:
            return jsonify({'status_code': 400,'status': 'Failed','message':"Please fill these fields:{value}".format(value=missing)})
        chck = """SELECT user_type FROM user_table WHERE userid = %s"""
        params = (userid,)
        verify = execute_query(chck,params,fetch=True,get_one=True)
        if verify is None:
            return jsonify({'status_code':500,'status':'Invalid userid'})
        if verify[0] != 'A':
            return jsonify({'status_code':403,'status':'Forbidden access'})
        query = "SELECT task_id, title, description, priority, status, due_date FROM task WHERE 1=1"
        params = []
        if priority:
            query += " AND priority = %s"
            params.append(priority)
        if status:
            query += " AND status = %s"
            params.append(status)
        if due_date:
            query += " AND due_date >= %s"
            params.append(due_date)
        if description:
            query += " AND description = %s"
            params = (description)
        if title:
            query += "AND title = %s"
            params.append(title)
        
        tasks = execute_query(query, tuple(params), fetch=True, as_dict=True)
        if not tasks:
            return jsonify({"status_code": 404, "status": "Task data does not exist"})
        
        return jsonify({"status": "Successfully fetched tasks", "details": tasks})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"})

@app.route('/edit_task', methods=['POST'])
@jwt_required()
def edit_task():
    try:
        userid = request.json.get('userid')
        priority = request.json.get('priority')
        status = request.json.get('status')
        due_date = request.json.get('due_date')
        description = request.json.get('description')
        title = request.json.get('title')
        task_id = request.json.get('task_id')
        validate = ["userid"]
        missing = json_validate(validate)
        if missing:
            return jsonify({'status_code': 400,'status': 'Failed','message':"Please fill these fields:{value}".format(value=missing)})
        
        chck = """SELECT user_type FROM user_table WHERE userid = %s"""
        params = (userid,)
        verify = execute_query(chck,params,fetch=True,get_one=True)
        if verify is None:
            return jsonify({'status_code':500,'status':'Invalid userid'})
        if verify[0] != 'A':
            return jsonify({'status_code':403,'status':'Forbidden access'})
        
        query = "UPDATE task SET title = %s, description = %s, due_date = %s, priority = %s, status = %s WHERE task_id = %s AND userid = %s"
        params = (title,description,due_date,priority,status,task_id,userid)
        execute_query(query, params)
        return jsonify({"status": "Successfully updated task"})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"})

@app.route('/delete_task', methods=['POST'])
@jwt_required()
def delete_task():
    try:
        userid = request.json.get('userid')
        taskid = request.json.get('taskid')
        validate = ["taskid"]
        missing = json_validate(validate)
        if missing:
            return jsonify({'status_code': 400,'status': 'Failed','message':"Please fill these fields:{value}".format(value=missing)})
        chck = """SELECT user_type FROM user_table WHERE userid = %s"""
        params = (userid,)
        verify = execute_query(chck,params,fetch=True,get_one=True)
        if verify is None:
            return jsonify({'status_code':500,'status':'Invalid userid'})
        if verify[0] != 'A':
            return jsonify({'status_code':403,'status':'Forbidden access'})

        query = "DELETE FROM task WHERE task_id = %s"
        params = (taskid,)
        execute_query(query,params)
        return jsonify({"status_code": 200, "status": "Successfully deleted task"})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"})

# Notes Endpoints
@app.route('/add_notes', methods=['POST'])
@jwt_required()
def add_notes():
    try:
        userid = request.json.get('userid')
        title = request.json.get('title')
        body = request.json.get('body')
        validate = ["userid","title","body"]
        missing = json_validate(validate)
        if missing:
            return jsonify({'status_code': 400,'status': 'Failed','message':"Please fill these fields:{value}".format(value=missing)})
        
        user_exists_query = "SELECT userid FROM user_table WHERE userid = %s"
        params = (userid,)
        user_exists = execute_query(user_exists_query,params, fetch=True, get_one=True)
        if not user_exists:
            return jsonify({"status_code": 404, "status": "User not found"})
        
        query = "INSERT INTO notes (userid, title, body) VALUES (%s, %s, %s)"
        params = (userid,title,body,)
        execute_query(query, params)
        return jsonify({"status_code": 200, "status": "Successfully added notes"})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"})

@app.route('/get_notes', methods=['GET'])
@jwt_required()
def get_notes():
    try:
        userid = request.json.get('userid')
        s_id = request.json.get('s_id') 
        validate = ["userid","s_id"]
        dummy = []
        missing = json_validate(validate)
        if missing: 
            return jsonify({'status_code': 400,'status': 'Failed','message':"Please fill these fields:{value}".format(value=missing)})
        query = "SELECT title, body FROM notes WHERE s_id = %s AND userid = %s"
        params = (s_id,userid,)
        note = execute_query(query,params, fetch=True, as_dict=True)
        if not note:
            return jsonify({"status_code": 404, "status": "Notes data does not exist"})
        for i in note:
            dummy.append(i)
        return jsonify({"status_code": 200, "status": "Successfully fetched notes", "details":dummy})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"})

@app.route('/all_notes', methods=['GET'])
@jwt_required()
def all_notes():
    try:
        query = "SELECT title, body FROM notes"
        notes = execute_query(query, fetch=True, as_dict=True)
        if not notes:
            return jsonify({"status_code": 404, "status": "Notes data does not exist"})
        return jsonify({"status": "Successfully fetched Notes", "details": notes})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"}), 500

@app.route('/edit_notes', methods=['POST'])
@jwt_required()
def edit_notes():
    try:
        userid = request.json.get('userid')
        title = request.json.get('title')
        body = request.json.get('body')
        s_id = request.json.get('s_id')
        validate = ["userid","title","body","s_id"]
        missing = json_validate(validate)
        if missing:
            return jsonify({'status_code': 400,'status': 'Failed','message':"Please fill these fields:{value}".format(value=missing)})
        
        check_query = "SELECT userid FROM notes WHERE userid = %s"
        params = (userid,)
        user_exists = execute_query(check_query,userid, fetch=True, get_one=True)
        if not user_exists:
            return jsonify({"status_code": 404, "status": "User not found"})
        
        query = "UPDATE notes SET title = %s, body = %s WHERE s_id = %s AND userid = %s"
        params = (title,body,s_id,userid)
        execute_query(query, params)
        return jsonify({"status": "Successfully updated notes"})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"})

@app.route('/delete_note', methods=['POST'])
@jwt_required()
def delete_note():
    try:
        s_id = request.json.get('s_id')
        userid = request.json.get('userid')
        validate = ["s_id","userid"]
        missing = json_validate(validate)
        if missing:
            return jsonify({'status_code': 400,'status': 'Failed','message':"Please fill these fields:{value}".format(value=missing)})
        check_query = "SELECT userid FROM notes WHERE userid = %s"
        params = (userid,)
        user_exists = execute_query(check_query,userid, fetch=True, get_one=True)
        if not user_exists:
            return jsonify({"status_code": 404, "status": "User not found"})
        query = "DELETE FROM notes WHERE s_id = %s AND userid = %s"
        params = (s_id,userid)
        execute_query(query,params)
        return jsonify({"status_code": 200, "status": "Successfully deleted Note"})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"})

# Combined Endpoints
@app.route('/user/<int:userid>/details', methods=['GET'])
@jwt_required()
def user_details(userid: int):
    try:
        userid = request.json.get('userid')
        validate = ["userid"]
        missing = json_validate(validate)
        if missing:
            return jsonify({'status_code': 400,'status': 'Failed','message':"Please fill these fields:{value}".format(value=missing)})
        chck = """SELECT user_type FROM user_table WHERE userid = %s"""
        params = (userid,)
        verify = execute_query(chck,params,fetch=True,get_one=True)
        if verify is None:
            return jsonify({'status_code':500,'status':'Invalid userid'})
        if verify[0] != 'A':
            return jsonify({'status_code':403,'status':'Forbidden access'})
        user_query = "SELECT userid, name, email FROM user_table WHERE userid = %s"
        user = execute_query(user_query, (userid,), fetch=True, get_one=True, as_dict=True)
        if not user:
            return jsonify({"status_code": 404, "status": "User not found"}), 404

        tasks_query = "SELECT title, description, due_date, priority, status FROM task WHERE userid = %s"
        user_tasks = execute_query(tasks_query, (userid,), fetch=True, as_dict=True)

        notes_query = "SELECT title, body FROM notes WHERE userid = %s"
        user_notes = execute_query(notes_query, (userid,), fetch=True, as_dict=True)

        if user_tasks:
            for task in user_tasks:
                if isinstance(task.get('due_date'), datetime):
                    task['due_date'] = task['due_date'].isoformat()

        user['tasks'] = user_tasks
        user['notes'] = user_notes
        
        return jsonify({"status_code": 200, "status": "User details fetched successfully", "details": user})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"}), 500

@app.route('/alluser_details', methods=['GET'])
@jwt_required()
def alluser_details():
    try:
        userid = request.json.get('userid')
        validate = ["userid"]
        missing = json_validate(validate)
        if missing:
            return jsonify({'status_code': 400,'status': 'Failed','message':"Please fill these fields:{value}".format(value=missing)})
        chck = """SELECT user_type FROM user_table WHERE userid = %s"""
        params = (userid,)
        verify = execute_query(chck,params,fetch=True,get_one=True)
        if verify is None:
            return jsonify({'status_code':500,'status':'Invalid userid'})
        if verify[0] != 'A':
            return jsonify({'status_code':403,'status':'Forbidden access'})

        users_query = "SELECT userid, name, email FROM user_table"
        users = execute_query(users_query, fetch=True, as_dict=True)
        if not users:
            return jsonify({"status_code": 404, "status": "No users found"}), 404

        result = []
        for user in users:
            tasks_query = "SELECT title, description, due_date, priority, status FROM task WHERE userid = %s"
            user_tasks = execute_query(tasks_query, (user['userid'],), fetch=True, as_dict=True)

            notes_query = "SELECT title, body FROM notes WHERE userid = %s"
            user_notes = execute_query(notes_query, (user['userid'],), fetch=True, as_dict=True)
            
            if user_tasks:
                for task in user_tasks:
                    if isinstance(task.get('due_date'), datetime):
                        task['due_date'] = task['due_date'].isoformat()

            user['tasks'] = user_tasks
            user['notes'] = user_notes
            result.append(user)
            
        return jsonify({"status_code": 200, "status": "User details fetched successfully", "details": result})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0",debug=True, port=5000)