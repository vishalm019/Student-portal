import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from flask import Flask, request, jsonify
from pydantic import BaseModel, EmailStr
import random
from db_config import DB_CONFIG
import string

app = Flask(__name__)


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


# User Endpoints
@app.route('/insert_user', methods=['POST'])
def insert_user():
    try:
        name = request.json.get('name')
        email = request.json.get('email')
        password = request.json.get('password')
        pwd = ''.join(random.choices(string.ascii_letters, k=5))
        query = "INSERT INTO users (name, email, password) VALUES (%s, %s, %s) RETURNING userid"
        params = (name,email,password,)
        result = execute_query(query, params, fetch=True, get_one=True, as_dict=True)
        if result:
            return jsonify({"status_code": 200, "status": "User added", "userid": result[0][0]})
        else:
            return jsonify({"status_code": 500, "status": "Failed to add user"})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"})

@app.route('/get_users', methods=['GET'])
def get_users():
    try:
        query = "SELECT userid, name, email FROM users"
        users = execute_query(query, fetch=True, as_dict=True)
        return jsonify({"status": "Users fetched", "data": users[0][0]})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"})

@app.route('/update_user', methods=['POST'])
def update_user():
    try:
        userid = request.json.get('userid')
        name = request.json.get('name')
        email = request.json.get('email')
        password = request.json.get('password')
        check_query = "SELECT userid FROM users WHERE userid = %s"
        params = (userid,)
        user_exists = execute_query(check_query,params,fetch=True,get_one=True)
        if not user_exists:
            return jsonify({"status_code": 404, "status": "User not found"})
        
        query = "UPDATE users SET name = %s, email = %s,password = %s WHERE userid = %s"
        params = (name,email,password,userid,)
        execute_query(query, params)
        return jsonify({"status_code":200,"status": "User updated successfully"})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"})

@app.route('/delete_user', methods=['POST'])
def delete_user():
    try:
        userid = request.json.get('userid')
        check_query = "SELECT userid FROM users WHERE userid = %s"
        params = (userid,)
        user_exists = execute_query(check_query,params, fetch=True, get_one=True)
        if not user_exists:
            return jsonify({"status_code": 404, "status": "User not found"})
        query = "DELETE FROM users WHERE userid = %s"
        execute_query(query,params)
        return jsonify({"status_code":200,"status": "User deleted successfully"})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"})

# Task Endpoints
@app.route('/add_task', methods=['POST'])
def add_task():
    try:
        userid = request.json.get('userid')
        title = request.json.get('title')
        description = request.json.get('description')
        due_date = request.json.get('due_date')
        priority = request.json.get('priority')
        status = request.json.get('status')
        user_exists_query = "SELECT userid FROM users WHERE userid = %s"
        params = (userid,)
        user_exists = execute_query(user_exists_query,params, fetch=True, get_one=True)
        if not user_exists:
            return jsonify({"status_code": 404, "status": "User not found"})
        query = "INSERT INTO tasks (userid, title, description, due_date, priority, status) VALUES (%s, %s, %s, %s, %s, %s)"
        params = (userid,title,description,due_date,priority,status)
        execute_query(query, params)
        return jsonify({"status": "Successfully added task"})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"})

@app.route('/get_task', methods=['POST'])
def get_task():
    try:
        userid = request.json.get('userid')
        user_exists_query = "SELECT userid FROM users WHERE userid = %s"
        params = (userid,)
        user_exists = execute_query(user_exists_query,params, fetch=True, get_one=True)
        if not user_exists:
            return jsonify({"status_code": 404, "status": "User not found"})
        query = "SELECT task_id, title, description, priority, status, due_date FROM tasks WHERE userid = %s"
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
def all_tasks():
    try:
        # priority = request.json.get('priority')
        # status = request.json.get('status')
        # due_date = request.json.get('due_date')
        # description = request.json.get('description')
        # title = request.json.get('title')
        data = request.get_json()
        query = "SELECT task_id, title, description, priority, status, due_date FROM tasks WHERE 1=1"
        params = []
        if data.priority:
            query += " AND priority = %s"
            params.append(data.priority)
        if data.status:
            query += " AND status = %s"
            params.append(data.status)
        if data.description:
            query += " AND due_date >= %s"
            params.append(data.description)
            
        if data.title:
            query += "AND title = %s"
            params.append(data.title)
        
        tasks = execute_query(query, tuple(params), fetch=True, as_dict=True)
        if not tasks:
            return jsonify({"status_code": 404, "status": "Task data does not exist"})
            
        for task in tasks:
            if isinstance(task.get('due_date'), datetime):
                task['due_date'] = task['due_date'].isoformat()
        
        return jsonify({"status": "Successfully fetched tasks", "details": tasks})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"})

@app.route('/edit_task', methods=['POST'])
def edit_task():
    try:
        userid = request.json.get('userid')
        priority = request.json.get('priority')
        status = request.json.get('status')
        due_date = request.json.get('due_date')
        description = request.json.get('description')
        title = request.json.get('title')
        task_id = request.json.get('task_id')
        check_query = "SELECT userid FROM users WHERE userid = %s"
        params = (userid,)
        user_exists = execute_query(check_query,params, fetch=True, get_one=True)
        if not user_exists:
            return jsonify({"status_code": 404, "status": "User not found"})
        
        query = "UPDATE tasks SET title = %s, description = %s, due_date = %s, priority = %s, status = %s WHERE task_id = %s AND userid = %s"
        params = (title,description,due_date,priority,status,task_id,userid)
        execute_query(query, params)
        return jsonify({"status": "Successfully updated task"})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"})

@app.route('/delete_task', methods=['POST'])
def delete_task():
    try:
        taskid = request.json.get('taskid')
        query = "DELETE FROM tasks WHERE task_id = %s"
        params = (taskid,)
        execute_query(query,params)
        return jsonify({"status_code": 200, "status": "Successfully deleted task"})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"})

# Notes Endpoints
@app.route('/add_notes', methods=['POST'])
def add_notes():
    try:
        userid = request.json.get('userid')
        title = request.json.get('title')
        body = request.json.get('body')
        user_exists_query = "SELECT s_id FROM users WHERE userid = %s"
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

@app.route('/get_notes', methods=['POST'])
def get_notes():
    try:
        userid = request.json.get(userid,)
        s_id = request.json.get('s_id')
        query = "SELECT title, body FROM notes WHERE s_id = %s AND userid = %s"
        params = (s_id,userid,)
        note = execute_query(query,params, fetch=True, get_one=True, as_dict=True)
        if not note:
            return jsonify({"status_code": 404, "status": "Notes data does not exist"})
        return jsonify({"status_code": 200, "status": "Successfully fetched notes", "details": note})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"})

@app.route('/all_notes', methods=['GET'])
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
def edit_notes():
    try:
        userid = request.json.get('userid')
        title = request.json.get('title')
        body = request.json.get('body')
        s_id = request.json.get('s_id')
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
def delete_note():
    try:
        s_id = request.json.get('s_id')
        userid = request.json.get('userid')
        query = "DELETE FROM notes WHERE s_id = %s AND userid = %s"
        params = (s_id,userid)
        execute_query(query,params)
        return jsonify({"status_code": 200, "status": "Successfully deleted Note"})
    except Exception as e:
        return jsonify({"status_code": 500, "status": f"Internal server error: {str(e)}"})

# Combined Endpoints
@app.route('/user/<int:userid>/details', methods=['GET'])
def user_details(userid: int):
    try:
        user_query = "SELECT userid, name, email FROM users WHERE userid = %s"
        user = execute_query(user_query, (userid,), fetch=True, get_one=True, as_dict=True)
        if not user:
            return jsonify({"status_code": 404, "status": "User not found"}), 404

        tasks_query = "SELECT title, description, due_date, priority, status FROM tasks WHERE userid = %s"
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
def alluser_details():
    try:
        users_query = "SELECT userid, name, email FROM users"
        users = execute_query(users_query, fetch=True, as_dict=True)
        if not users:
            return jsonify({"status_code": 404, "status": "No users found"}), 404

        result = []
        for user in users:
            tasks_query = "SELECT title, description, due_date, priority, status FROM tasks WHERE userid = %s"
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

if __name__ == '__main__':
    app.run(debug=True)