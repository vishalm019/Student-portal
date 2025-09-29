# Student Portal API

## Overview

This is a REST API built with `Flask` and `PostgreSQL` for a Student Portal.
It handles JWT-based authentication, admin/user role-based access control, and CRUD operations for users, tasks, notes, plus combined endpoints for analytics.

It’s designed to be Docker-ready and deployable on AWS EBS/EC2 (optional).

## Tech Stack

| Layer            | Technology                 |
| ---------------- | -------------------------- |
| Backend          | Python (Flask)             |
| Database         | PostgreSQL (psycopg2)      |
| Authentication   | JWT (Flask-JWT-Extended)   |
| Password Hashing | werkzeug.security (scrypt) |
| Containerization | Docker                     |

Features

- JWT authentication with access & refresh tokens

- Password hashing and secure login

- Role-based access (Admin vs User)

- File upload support for tasks (Admins can attach files while creating a task).

- Download attached files for tasks.

API Endpoints:

| Module   | Method | Endpoint                                 | Description                                 | Auth Required |
| -------- | ------ | ---------------------------------------- | ------------------------------------------- | ------------- |
| Auth     | POST   | /login                                   | User login (returns access & refresh token) | No            |
| Auth     | POST   | /admin_login                             | Admin login for initial users               | No            |
| Auth     | POST   | /refresh                                 | Refresh access token                        | Yes           |
| Users    | POST   | /insert_user                             | Add a new user                              | Admin         |
| Users    | POST   | /update_user                             | Update an existing user                     | Admin         |
| Users    | POST   | /delete_user                             | Delete a user                               | Admin         |
| Users    | GET    | /get_users                               | Fetch all users                             | Admin         |
| Tasks    | POST   | /add_task                                | Add task(accepts form-data with file)       | JWT           |
| Tasks    | POST   | /get_task                                | Fetch tasks for a user                      | JWT           |
| Tasks    | POST   | /edit_task                               | Edit a task                                 | JWT           |
| Tasks    | GET    | /all_tasks                               | Fetch all tasks (Admin only)                | Admin         |
| Tasks    | GET    | /task_file                               | Download attached file for a task           | JWT           |
| Tasks    | POST   | /delete_task                             | Delete a task                               | JWT           |
| Notes    | POST   | /add_notes                               | Add notes                                   | JWT           |
| Notes    | GET    | /get_notes                               | Fetch notes for a user                      | JWT           |
| Notes    | GET    | /all_notes                               | Fetch all notes                             | Admin         |
| Notes    | POST   | /edit_notes                              | Edit notes                                  | JWT           |
| Notes    | POST   | /delete_note                             | Delete note                                 | JWT           |
| Combined | GET    | `/user/[int:user_id](int:user_id)/details` | Fetch a user's details with tasks + notes   | JWT           |
| Combined | GET    | /alluser_details                         | Fetch all users’ details with tasks + notes | Admin         |

## Setup (Run Locally)

Prerequisites:

- Python 3.9+

- PostgreSQL

- Docker (optional, only if using containerization)

## 1. Clone the repository:
``` bash
    git clone https://github.com/<your-username>/student-portal-api.git
    cd student-portal-api
```

## 2. Create a virtual environment & install dependencies
``` bash    

python -m venv .venv

Windows:

.venv\Scripts\activate

Linux / macOS:

source .venv/bin/activate

Install dependencies:

pip install -r requirements.txt
```
## 3. Configure your database connection

Open db_config.py and update DB_CONFIG:

```    DB_CONFIG = {
        "host": "localhost",          # Use 'host.docker.internal' if running Flask in Docker
        "port": 5432,
        "user": "postgres",
        "password": "yourpassword",
        "dbname": "yourdbname"
        } 
```

If PostgreSQL is running in a separate Docker container, make sure both containers share a Docker network.

### Link to PostgreSQL:

- Local DB: use localhost (or host.docker.internal if inside Docker).

- Separate container DB: connect both containers via a Docker network.

## 4. Run the app locally

``` bash

python app.py

```
The API will be available at:

```http://localhost:5000 ```

# Docker Deployment

## 1. Dockerfile:

    # Use a lightweight Python image
    FROM python:3.11-slim

    # Set working directory
    WORKDIR /app

    # Copy requirements and install dependencies
    COPY requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt

    # Copy all project files into the container
    COPY . .

    # Command to run the Flask app
    CMD ["python", "app.py", "--host", "0.0.0.0", "--port", "5000"]


### Notes:

 - host 0.0.0.0 makes the app accessible outside the container.

 - port 5000 exposes Flask on port 5000.

 - no-cache-dir avoids extra pip cache files in the container.

## 2. Build the Docker image

``` bash

docker build -t student-portal .

```

## 3. Run the container

Production-style (stable, no auto-reload):

``` bash

docker run -d -p 5000:5000 --name student-portal student-portal

```

Development-style (reflect local code changes instantly):

``` bash

docker run -p 5000:5000 -v ${PWD}:/app student-portal

```
Make sure app.py has:

`app.run(host="0.0.0.0", port=5000, debug=True) `

debug=True enables auto-reload when files change.

The API will be available at:

```   http://localhost:5000 ```


### Postman Collection

You can import the Postman collection from:

```postman/student-portal.postman_collection.json ```

This allows you to test all APIs with pre-configured endpoints.

# AWS Deployment

## 1.Push Docker Image to ECR

1.Create a repository in ECR (Elastic Container Registry).

2.Authenticate Docker with ECR:
    
Run the following command to authenticate Docker to your ECR registry:
`aws ecr get-login-password --region <your-region> | docker login --username AWS --password-stdin <account-id>.dkr.ecr.<region>.amazonaws.com `

3.Tag your Docker image for ECR:

`docker tag student-portal:latest <account-id>.dkr.ecr.<region>.amazonaws.com/student-portal:latest`

4.Push the image:

`docker push <account-id>.dkr.ecr.<region>.amazonaws.com/student-portal:latest`

## 2. Create RDS PostgreSQL Instance

### 1. Navigate to the RDS Console:

Go to the RDS console.

### 2. Launch a New Database:

 - Choose "Create database" and select PostgreSQL. Configure the instance with the following settings:

- DB Instance Identifier: student-portal-db

- Master Username: admin

- Master Password: yourpassword

- VPC: Select your existing VPC

- Publicly Accessible: Yes

- VPC Security Groups: Create a new security group or select an existing one that allows inbound traffic on port 5432 from your ECS tasks.

### 3. Note the Endpoint:

After the instance is created, note the endpoint (example:student-portal-db.c36oee8i0x0q.ap-south-1.rds.amazonaws.com).

### 4. Update db_config.py:

` 
DB_CONFIG = {
    "host": "<your-rds-endpoint>",
    "port": 5432,
    "user": "<master-username>",
    "password": "<password>",
    "dbname": "<database-name>"
} ` 

## 3. Create ECS Cluster (Fargate)

### 1. Navigate to ECS Console:

Go to the ECS console.

### 2. Create a New Cluster:

- Choose "Networking only" and configure the cluster:

- Cluster Name: student-portal-cluster

- VPC: Select your existing VPC

- Subnets: Select at least two subnets in different Availability Zones

    - Security Groups: Create a new security group or select an existing one that allows inbound traffic on port 5000.

## 4. Create Task Definition

### 1. Navigate to Task Definitions:

In the ECS console, go to "Task Definitions" and click "Create new Task Definition".

### 2. Configure the Task Definition:

- Launch Type: Fargate

- Task Name: student-portal-task

- Task Role: Create a new role or select an existing one with the necessary permissions

- Execution Role: Create a new role or select an existing one with the necessary permissions

### 3. Add a Container:

- Container Name: student-portal

- Image: <aws_account_id>.dkr.ecr.ap-south-1.amazonaws.com/student-portal:latest

- Port Mappings: 5000

- Environment Variables: Add any necessary environment variables, such as the database connection details.

### 4. Save the Task Definition.


[task definition](screenshots/ecs_cluster_task_definition.png)

## 5. Create a Service

### 1. Navigate to Services:

In the ECS console, go to "Services" and click "Create".

### 2. Configure the Service:

Launch Type: Fargate

Cluster: student-portal-cluster

Service Name: student-portal-service

- Task Definition: student-portal-task

- Desired Tasks: 1

- Network Configuration:

    1. VPC: Select your existing VPC

    2. Subnets: Select the subnets you chose earlier

    3. Security Groups: Select the security group you created or selected earlier

### 3. Create the Service.

[ECS cluster service](screenshots/ecs_cluster_service.png)

## 6. Access the API

After the service is running, you can access the API by navigating to the public IP address of the load balancer associated with your ECS service. The API will be available at:

``` http://<load_balancer_dns>:5000 ```

