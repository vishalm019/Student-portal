import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime,timedelta,timezone
from flask import Flask, request, jsonify,send_file
import random
import os
from db_config import DB_CONFIG,parent_dir
import string
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt,create_refresh_token
from functools import wraps
from werkzeug.security import generate_password_hash,check_password_hash
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

def validate(required_fields):
    payload = request.form
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

@app.route('/admin_login', methods=['POST'])
def admin_login():
    username = request.json.get('username')
    password = request.json.get('password')
    query = "SELECT userid,password FROM user_table WHERE email = %s AND password = %s"
    params = (username,password,)
    result = execute_query(query,params, fetch=True, get_one=True)
    if result is None:
        return jsonify({"status": "Invalid credentials"}),500
    access_token = create_access_token(identity=result[0])
    refresh_token = create_refresh_token(identity=result[0])   
    return jsonify({"status": "success", "token": access_token,"refresh_token":refresh_token})

@app.route('/login', methods=['POST'])
def login():
    username = request.json.get('username')
    password = request.json.get('password')
    query = "SELECT userid,password FROM user_table WHERE email = %s"
    params = (username,)
    result = execute_query(query,params, fetch=True, get_one=True)
    if not result or not check_password_hash(result[1], password):
        return jsonify({"status": "Invalid credentials"}), 401
    if result is None:
        return jsonify({"status": "Invalid credentials"}),500
    access_token = create_access_token(identity=result[0])
    refresh_token = create_refresh_token(identity=result[0])   
    return jsonify({"status": "success", "token": access_token,"refresh_token":refresh_token})


# User Endpoints
@app.route('/insert_user', methods=['POST'])
@jwt_required()
def insert_user():
    try:
        userid = get_jwt_identity()
        name = request.json.get('name')
        email = request.json.get('email')
        user_type = request.json.get('user_type')
        pwd = ''.join(random.choices(string.ascii_letters, k=5))
        print(userid,'userid')
        hashed_pwd = generate_password_hash(pwd)
        validate = ["name","email"]
        missing = json_validate(validate)
        if missing:
            return jsonify({'status': 'Failed','message':"Please fill these fields:{value}".format(value=missing)}),400
        
        chck = """SELECT user_type FROM user_table WHERE userid = %s"""
        params = (userid,)
        verify = execute_query(chck,params,fetch=True,get_one=True)
        if verify is None:
            return jsonify({'status_code':500,'status':'Invalid userid'})
        if verify[0] != 'A':
            return jsonify({'status':'Forbidden access'}),403
        query = "INSERT INTO user_table (name, email, password,user_type) VALUES (%s, %s, %s,%s) RETURNING userid"
        params = (name,email,hashed_pwd,user_type)
        result = execute_query(query, params, fetch=True, get_one=True, as_dict=False)
        if result is not None:
            return jsonify({"status": "User added", "userid": result[0],"password":pwd})
    except Exception as e:
        return jsonify({"status": f"Internal server error: {str(e)}"}),500

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
        return jsonify({"status": f"Internal server error: {str(e)}"}),500

@app.route('/update_user', methods=['POST'])
@jwt_required()
def update_user():
    try:
        userid = get_jwt_identity()
        of_user = request.json.get('of_user')
        name = request.json.get('name')
        email = request.json.get('email')
        password = request.json.get('password')
        payload = request.get_json()
        validate = ["of_user"]
        missing = json_validate(validate)
        if missing:
            return jsonify({'status': 'Failed','message':"Please fill these fields:{value}".format(value=missing)}),400
        

        chck = """SELECT user_type FROM user_table WHERE userid = %s"""
        params = (userid,)
        verify = execute_query(chck,params,fetch=True,get_one=True)
        if verify is None:
            return jsonify({'status_code':500,'status':'Invalid userid'})
        if verify[0] != 'A':
            return jsonify({'status':'Forbidden access'}),403
        new_payload = {i:k for i,k in payload.items() if i != 'of_user' and k not in [None,""]}
        if new_payload['password']:
            hashed_pwd = generate_password_hash(password)
            new_payload['password'] = hashed_pwd
        update = ", ".join([f"{k} = %s" for k in new_payload.keys()])
        query = "UPDATE user_table SET {update} WHERE userid = %s".format(update=update)
        params = list(new_payload.values()) + [of_user]
        execute_query(query,params)
        return jsonify({"status_code":200,"status": "User updated successfully"})
    except Exception as e:
        return jsonify({"status": f"Internal server error: {str(e)}"}),500

@app.route('/delete_user', methods=['POST'])
@jwt_required()
def delete_user():
    try:
        userid = get_jwt_identity()
        delete_id = request.json.get('delete_id')
        validate = ["delete_id"]
        missing = json_validate(validate)
        if missing:
            return jsonify({'status': 'Failed','message':"Please fill these fields:{value}".format(value=missing)}),400
        chck = """SELECT user_type FROM user_table WHERE userid = %s"""
        params = (userid,)
        verify = execute_query(chck,params,fetch=True,get_one=True)
        if verify is None:
            return jsonify({'status_code':500,'status':'Invalid userid'})
        if verify[0] != 'A':
            return jsonify({'status':'Forbidden access'}),403
        query2 = "DELETE FROM task WHERE userid = %s"
        params = (delete_id,)
        execute_query(query2,params)
        query = "DELETE FROM user_table WHERE userid = %s"
        execute_query(query,params)
        return jsonify({"status_code":200,"status": "User deleted successfully"})
    except Exception as e:
        return jsonify({"status": f"Internal server error: {str(e)}"}),500

# Task Endpoints
@app.route('/add_task', methods=['POST'])
@jwt_required()
def add_task():
    try:
        print('helo')
        userid = get_jwt_identity()
        to_user = request.form.get('to_user')
        title = request.form.get('title')
        description = request.form.get('description')
        due_date = request.form.get('due_date')
        priority = request.form.get('priority')
        status = request.form.get('status')
        filename = request.form.get('filename')
        total = request.files
        validation = ["to_user","title","description","due_date","priority","status"]
        missing = validate(validation)
        if missing:
            return jsonify({'status': 'Failed','message':"Please fill these fields:{value}".format(value=missing)}),400
        chck = """SELECT user_type FROM user_table WHERE userid = %s"""
        params = (to_user,)
        verify = execute_query(chck,params,fetch=True,get_one=True)
        if verify is None:
            return jsonify({'status_code':500,'status':'Invalid to_user'})
        chck = """SELECT user_type FROM user_table WHERE userid = %s"""
        params = (userid,)
        verify = execute_query(chck,params,fetch=True,get_one=True)
        if verify is None:
            return jsonify({'status_code':500,'status':'Invalid userid'})
        if verify[0] != 'A':
            return jsonify({'status':'Forbidden access'}),403
        query = "INSERT INTO task (userid, title, description, due_date, priority, status) VALUES (%s, %s, %s, %s, %s, %s) RETURNING task_id"
        params = (to_user,title,description,due_date,priority,status)
        taskid = execute_query(query, params,fetch=True,get_one=True)
        path_name = 'Task'
        check1 = parent_dir + '/' + path_name
        bool1 = os.path.exists(check1)
        if bool1 is False:
            os.makedirs(check1)
        check2 = check1 + '/' + to_user
        bool2 = os.path.exists(check2)
        if bool2 is False:
            os.makedirs(check2)
        check3 = check2 + '/' + str(taskid[0])
        bool3 = os.path.exists(check3)
        if bool3 is False:
            os.makedirs(check3)
        final_path = os.path.join(check3,filename)
        file = total.get(filename)
        file.save(final_path)
        query2 = "UPDATE task SET file_save = %s WHERE task_id = %s"
        params = (final_path,taskid[0],)
        execute_query(query2,params)
        return jsonify({"status": "Successfully added task"})
    except Exception as e:
        return jsonify({"status": f"Internal server error: {str(e)}"}),500

@app.route('/task_image', methods=['POST'])
@jwt_required()
def task_image():
    try:
        user = get_jwt_identity()
        taskid = request.json.get('taskid')
        validate = ["taskid"]
        missing = json_validate(validate)
        if missing:
            return jsonify({'status': 'Failed','message':"Please fill these fields:{value}".format(value=missing)}),400
        user_exists_query = "SELECT userid FROM user_table WHERE userid = %s"
        params = (user,)
        user_exists = execute_query(user_exists_query,params, fetch=True, get_one=True)
        if not user_exists:
            return jsonify({"status": "User not found"}),404
        task_exists_query = "SELECT task_id,file_save FROM task WHERE task_id = %s"
        params = (taskid,)
        task_exists = execute_query(task_exists_query,params, fetch=True, get_one=True)
        if not task_exists:
            return jsonify({"status": "Task not found"}),404
        if task_exists[1]:
            bool1 = os.path.exists(task_exists[1])
            if bool1 is True:
                filename = task_exists[1].split('/')
                ext = filename[-1].split('.')
                if ext[-1] == 'jpg'or ext[-1] == 'jpeg' or ext[-1] == 'png':
                    return send_file(task_exists[1],download_name=filename[-1],as_attachment=True,mimetype='image/jpeg')
                elif ext[-1] == 'pdf':
                    return send_file(task_exists[1],download_name=filename[-1],as_attachment=True,mimetype='application/pdf')
                elif ext[-1] == 'csv':
                    return send_file(task_exists[1],download_name=filename[-1],as_attachment=True,mimetype='text/csv')
            else:
                return jsonify({"status": "No such file exists"}),404
        else:
            return jsonify({"status_code": 404, "status": "There is not file stored for this task"})
        return jsonify({"status": "Successfully fetched tasks"})
    except Exception as e:
        return jsonify({"status": f"Internal server error: {str(e)}"}),500

@app.route('/get_task', methods=['POST'])
@jwt_required()
def get_task():
    try:
        userid = get_jwt_identity()
        user = request.json.get('user')
        validate = ["user"]
        missing = json_validate(validate)
        if missing:
            return jsonify({'status': 'Failed','message':"Please fill these fields:{value}".format(value=missing)}),400
        user_exists_query = "SELECT userid FROM user_table WHERE userid = %s"
        params = (user,)
        user_exists = execute_query(user_exists_query,params, fetch=True, get_one=True)
        if not user_exists:
            return jsonify({"status": "User not found"}),404
        query = "SELECT task_id, title, description, priority, status, due_date FROM task WHERE userid = %s"
        params = (user,)
        tasks = execute_query(query,params, fetch=True, as_dict=True)
        if not tasks:
            return jsonify({"status_code": 404, "status": "Task data does not exist"})
        
        for task in tasks:
            if isinstance(task.get('due_date'), datetime):
                task['due_date'] = task['due_date'].isoformat()
            
        return jsonify({"status": "Successfully fetched tasks", "details": tasks})
    except Exception as e:
        return jsonify({"status": f"Internal server error: {str(e)}"}),500

@app.route('/all_tasks', methods=['GET'])
@jwt_required()
def all_tasks():
    try:
        priority = request.args.get('priority')
        status = request.args.get('status')
        due_date = request.args.get('due_date')
        description = request.args.get('description')
        title = request.args.get('title')
        userid = get_jwt_identity()
        chck = """SELECT user_type FROM user_table WHERE userid = %s"""
        params = (userid,)
        verify = execute_query(chck,params,fetch=True,get_one=True)
        if verify is None:
            return jsonify({'status_code':500,'status':'Invalid userid'})
        if verify[0] != 'A':
            return jsonify({'status':'Forbidden access'}),403
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
            params.append(description)
        if title:
            query += "AND title = %s"
            params.append(title)
        
        tasks = execute_query(query, tuple(params), fetch=True, as_dict=True)
        if not tasks:
            return jsonify({"status_code": 404, "status": "Task data does not exist"})
        
        return jsonify({"status": "Successfully fetched tasks", "details": tasks})
    except Exception as e:
        return jsonify({"status": f"Internal server error: {str(e)}"}),500

@app.route('/edit_task', methods=['POST'])
@jwt_required()
def edit_task():
    try:
        userid = get_jwt_identity()
        task_id = request.json.get('task_id')
        
        payload = request.get_json()
        chck = """SELECT user_type FROM user_table WHERE userid = %s"""
        params = (userid,)
        verify = execute_query(chck,params,fetch=True,get_one=True)
        if verify is None:
            return jsonify({'status_code':500,'status':'Invalid userid'})
        new_payload = {i:k for i,k in payload.items() if i != 'task_id' and k not in [None,""]}
        update = ", ".join([f"{k} = %s" for k in new_payload.keys()])
        query = "UPDATE task SET {update} WHERE task_id = %s".format(update=update)
        params = list(new_payload.values()) + [task_id]
        execute_query(query, params)
        return jsonify({"status": "Successfully updated task"}),200
    except Exception as e:
        return jsonify({"status": f"Internal server error: {str(e)}"}),500

@app.route('/delete_task', methods=['POST'])
@jwt_required()
def delete_task():
    try:
        userid = get_jwt_identity()
        taskid = request.json.get('taskid')
        validate = ["taskid"]
        missing = json_validate(validate)
        if missing:
            return jsonify({'status': 'Failed','message':"Please fill these fields:{value}".format(value=missing)}),400
        chck = """SELECT user_type FROM user_table WHERE userid = %s"""
        params = (userid,)
        verify = execute_query(chck,params,fetch=True,get_one=True)
        if verify is None:
            return jsonify({'status_code':500,'status':'Invalid userid'})
        if verify[0] != 'A':
            return jsonify({'status':'Forbidden access'}),403

        query = "DELETE FROM task WHERE task_id = %s"
        params = (taskid,)
        execute_query(query,params)
        return jsonify({"status": "Successfully deleted task"}),200
    except Exception as e:
        return jsonify({"status": f"Internal server error: {str(e)}"}),500

# Notes Endpoints
@app.route('/add_notes', methods=['POST'])
@jwt_required()
def add_notes():
    try:
        to_user = request.json.get('to_user')
        title = request.json.get('title')
        body = request.json.get('body')
        validate = ["title","body","to_user"]
        missing = json_validate(validate)
        if missing:
            return jsonify({'status': 'Failed','message':"Please fill these fields:{value}".format(value=missing)}),400
        
        user_exists_query = "SELECT userid FROM user_table WHERE userid = %s"
        params = (to_user,)
        user_exists = execute_query(user_exists_query,params, fetch=True, get_one=True)
        if not user_exists:
            return jsonify({"status": "User not found"}),404
        
        query = "INSERT INTO notes (userid, title, body) VALUES (%s, %s, %s)"
        params = (to_user,title,body,)
        execute_query(query, params)
        return jsonify({"status": "Successfully added notes"}),200
    except Exception as e:
        return jsonify({"status": f"Internal server error: {str(e)}"}),500

@app.route('/get_notes', methods=['GET'])
@jwt_required()
def get_notes():
    try:
        of_user = request.json.get('of_user')
        s_id = request.json.get('s_id') 
        validate = ["s_id","of_user"]
        dummy = []
        missing = json_validate(validate)
        if missing: 
            return jsonify({'status': 'Failed','message':"Please fill these fields:{value}".format(value=missing)}),400
        query = "SELECT title, body FROM notes WHERE s_id = %s AND userid = %s"
        params = (s_id,of_user,)
        note = execute_query(query,params, fetch=True, as_dict=True)
        if not note:
            return jsonify({"status_code": 404, "status": "Notes data does not exist"})
        for i in note:
            dummy.append(i)
        return jsonify({"status": "Successfully fetched notes", "details":dummy}),200
    except Exception as e:
        return jsonify({"status": f"Internal server error: {str(e)}"}),500

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
        return jsonify({"status": f"Internal server error: {str(e)}"}),500, 500

@app.route('/edit_notes', methods=['POST'])
@jwt_required()
def edit_notes():
    try:
        userid = get_jwt_identity()
        title = request.json.get('title')
        body = request.json.get('body')
        s_id = request.json.get('s_id')
        validate = ["title","body","s_id"]
        missing = json_validate(validate)
        if missing:
            return jsonify({'status': 'Failed','message':"Please fill these fields:{value}".format(value=missing)}),400
        
        query = "UPDATE notes SET title = %s, body = %s WHERE s_id = %s AND userid = %s"
        params = (title,body,s_id,userid)
        execute_query(query, params)
        return jsonify({"status": "Successfully updated notes"})
    except Exception as e:
        return jsonify({"status": f"Internal server error: {str(e)}"}),500

@app.route('/delete_note', methods=['POST'])
@jwt_required()
def delete_note():
    try:
        s_id = request.json.get('s_id')
        userid = get_jwt_identity()
        validate = ["s_id"]
        missing = json_validate(validate)
        if missing:
            return jsonify({'status': 'Failed','message':"Please fill these fields:{value}".format(value=missing)}),400
        query = "DELETE FROM notes WHERE s_id = %s AND userid = %s"
        params = (s_id,userid)
        execute_query(query,params)
        return jsonify({"status": "Successfully deleted Note"}),200
    except Exception as e:
        return jsonify({"status": f"Internal server error: {str(e)}"}),500

# Combined Endpoints
@app.route('/user/<int:getid>/details', methods=['GET'])
@jwt_required()
def user_details(getid: int):
    try:
        userid = get_jwt_identity()
        chck = """SELECT user_type FROM user_table WHERE userid = %s"""
        params = (userid,)
        verify = execute_query(chck,params,fetch=True,get_one=True)
        if verify is None:
            return jsonify({'status_code':500,'status':'Invalid userid'})
        if verify[0] != 'A':
            return jsonify({'status':'Forbidden access'}),403
        user_query = "SELECT userid, name, email FROM user_table WHERE userid = %s"
        user = execute_query(user_query, (getid,), fetch=True, get_one=True, as_dict=True)
        if not user:
            return jsonify({"status": "User not found"}),404, 404

        tasks_query = "SELECT title, description, due_date, priority, status FROM task WHERE userid = %s"
        user_tasks = execute_query(tasks_query, (getid,), fetch=True, as_dict=True)
        print(user_tasks,'sks')
        notes_query = "SELECT title, body FROM notes WHERE userid = %s"
        user_notes = execute_query(notes_query, (getid,), fetch=True, as_dict=True)

        if user_tasks:
            for task in user_tasks:
                if isinstance(task.get('due_date'), datetime):
                    task['due_date'] = task['due_date'].isoformat()

        user['tasks'] = user_tasks
        user['notes'] = user_notes
        
        return jsonify({"status": "User details fetched successfully", "details": user}),200
    except Exception as e:
        return jsonify({"status": f"Internal server error: {str(e)}"}),500

@app.route('/alluser_details', methods=['GET'])
@jwt_required()
def alluser_details():
    try:
        userid = get_jwt_identity()
        chck = """SELECT user_type FROM user_table WHERE userid = %s"""
        params = (userid,)
        verify = execute_query(chck,params,fetch=True,get_one=True)
        if verify is None:
            return jsonify({'status_code':500,'status':'Invalid userid'})
        if verify[0] != 'A':
            return jsonify({'status':'Forbidden access'}),403

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
            
        return jsonify({"status": "User details fetched successfully", "details": result}),200
    except Exception as e:
        return jsonify({"status": f"Internal server error: {str(e)}"}),500, 500

if __name__ == "__main__":
    app.run(host="0.0.0.0",debug=True, port=5000)