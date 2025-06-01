from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from pymongo.database import Database
from bson import ObjectId
import os
from datetime import datetime, timedelta, timezone
import random
import string
import re
from typing import Any, Optional, cast
import certifi
from functools import wraps
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore, auth
import certifi
import sys
from time_utils import convert_utc_to_local, convert_local_to_utc
import secrets

load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')

#Mongodb config
# MongoDB configuration
MONGODB_USERNAME = os.environ.get('MONGODB_USERNAME', 'your_username')
MONGODB_PASSWORD = os.environ.get('MONGODB_PASSWORD', 'your_password')
MONGODB_CLUSTER = os.environ.get('MONGODB_CLUSTER', 'your_cluster.mongodb.net')
MONGODB_DATABASE = os.environ.get('MONGODB_DATABASE', 'quizapp')

# MongoDB connection string
MONGODB_URI = f"mongodb+srv://{MONGODB_USERNAME}:{MONGODB_PASSWORD}@{MONGODB_CLUSTER}/?retryWrites=true&w=majority"

# MongoDB setup with SSL
client: Optional[MongoClient] = None
db: Optional[Database] = None                                                   

def connect_db() -> None:
    global client, db
    try:
        print(f"Attempting to connect to MongoDB with URI: mongodb+srv://{MONGODB_USERNAME}:****@{MONGODB_CLUSTER}/?retryWrites=true&w=majority")
        # Create a new client and connect to the server with SSL configuration
        client = MongoClient(
            MONGODB_URI,
            tls=True,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=30000,
            connectTimeoutMS=30000,
            socketTimeoutMS=30000,
            retryWrites=True,
            w='majority'
        )
        
        # Send a ping to confirm a successful connection
        client.admin.command('ping')
        print("MongoDB connection successful!")
        
        # Get database
        db = cast(Database, client[MONGODB_DATABASE])
        print(f"Connected to database: {MONGODB_DATABASE}")
        
    except Exception as e:
        print(f"MongoDB connection error: {str(e)}")
        print(f"MongoDB URI: mongodb+srv://{MONGODB_USERNAME}:****@{MONGODB_CLUSTER}/?retryWrites=true&w=majority")
        if client:
            client.close()
        client = None
        db = None
        raise

# Initialize connection
connect_db()

# Initialize the database
def init_db() -> None:
    if db is not None:
        db.users.drop()
        db.quizzes.drop()
        db.attempts.drop()


# Khởi tạo Firebase Admin SDK
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)


# Configure session cookie settings
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)
app.config['SESSION_REFRESH_EACH_REQUEST'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Helper functions for MongoDB operations
def create_user(email: str, username: str, password: str, role: str) -> dict:
    user = {
        "email": email,
        "username": username,
        "password": password,
        "role": role,
        "created_at": datetime.utcnow()
    }
    result = db.users.insert_one(user)
    user["_id"] = result.inserted_id
    return user

def get_user_by_email(email: str) -> Optional[dict]:
    return db.users.find_one({"email": email})

def get_user_by_id(user_id: str) -> Optional[dict]:
    return db.users.find_one({"_id": ObjectId(user_id)})

def insert_quiz(title: str, teacher_id: str, start_time: datetime, end_time: datetime, 
                duration: int, max_attempts: Optional[int], is_public: bool) -> dict:
    quiz = {
        "title": title,
        "quiz_code": generate_quiz_code(),
        "teacher_id": ObjectId(teacher_id),
        "start_time": start_time,
        "end_time": end_time,
        "duration": duration,
        "max_attempts": max_attempts,
        "is_public": is_public,
        "questions": [],
        "created_at": datetime.utcnow()
    }
    result = db.quizzes.insert_one(quiz)
    quiz["_id"] = result.inserted_id
    return quiz

def get_quiz_by_id(quiz_id: str) -> Optional[dict]:
    return db.quizzes.find_one({"_id": ObjectId(quiz_id)})

def get_quiz_by_code(quiz_code: str) -> Optional[dict]:
    return db.quizzes.find_one({"quiz_code": quiz_code})

def create_question(quiz_id: str, question_text: str, question_type: str, 
                   correct_answer: str, answers: list = None) -> dict:
    question = {
        "quiz_id": ObjectId(quiz_id),
        "question_text": question_text,
        "question_type": question_type,
        "correct_answer": correct_answer,
        "answers": answers or [],
        "created_at": datetime.utcnow()
    }
    result = db.questions.insert_one(question)
    question["_id"] = result.inserted_id
    return question

def create_quiz_result(quiz_id: str, student_id: str, score: float) -> dict:
    result = {
        "quiz_id": ObjectId(quiz_id),
        "student_id": ObjectId(student_id),
        "score": score,
        "submitted_at": datetime.utcnow()
    }
    result_id = db.quiz_results.insert_one(result)
    result["_id"] = result_id.inserted_id
    return result

def create_student_answer(quiz_id: str, student_id: str, question_id: str, answer_text: str) -> dict:
    answer = {
        "quiz_id": ObjectId(quiz_id),
        "student_id": ObjectId(student_id),
        "question_id": ObjectId(question_id),
        "answer_text": answer_text,
        "submitted_at": datetime.utcnow()
    }
    result = db.student_answers.insert_one(answer)
    answer["_id"] = result.inserted_id
    return answer

def generate_quiz_code() -> str:
    while True:
        code = ''.join(random.choices(string.ascii_uppercase, k=4))
        if not get_quiz_by_code(code):
            return code

def create_user_profile(user_id: str, full_name: str = None) -> dict:
    profile = {
        "user_id": ObjectId(user_id),
        "full_name": full_name,
        "phone": None,
        "address": None,
        "bio": None,
        "avatar": None,
        "created_at": datetime.utcnow()
    }
    result = db.user_profiles.insert_one(profile)
    profile["_id"] = result.inserted_id
    return profile

def create_password_reset_token(user_id: str) -> dict:
    token = {
        "user_id": ObjectId(user_id),
        "token": ''.join(random.choices(string.ascii_letters + string.digits, k=32)),
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(hours=1),
        "used": False
    }
    result = db.password_reset_tokens.insert_one(token)
    token["_id"] = result.inserted_id
    return token

# Routes
@app.route('/')
@app.route('/home')
def home():
    return render_template('home.html')

# Thêm decorator login_required
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Vui lòng đăng nhập để tiếp tục!', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = db.users.find_one({'email': email})
        if user and check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id'])
            session['role'] = user['role']
            session['username'] = user['username']
            flash('Đăng nhập thành công!', "success")
            
            if user['role'] == 'teacher':
                return redirect(url_for('teacher_dashboard'))
            else:
                return redirect(url_for('home'))
        
        flash('Email hoặc mật khẩu không đúng!')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            email = request.form['email']
            username = request.form['username']
            password = request.form['password']
            role = request.form['role']

            # Check if username or email exists
            existing_user = db.users.find_one({'username': username})
            existing_email = db.users.find_one({'email': email})
            
            if existing_user:
                flash('Tên đăng nhập đã tồn tại. Vui lòng chọn tên đăng nhập khác!', 'error')
                return redirect(url_for('register'))
            if existing_email:
                flash('Email đã được sử dụng. Vui lòng dùng email khác!', 'error')
                return redirect(url_for('register'))

            # Hash password
            hashed_password = generate_password_hash(password)
            
            # Create new user
            user_id = db.users.insert_one({
                'email': email,
                'username': username,
                'password': hashed_password,
                'role': role
            }).inserted_id

            # Create user profile
            db.user_profiles.insert_one({
                'user_id': user_id,
                'full_name': username,
                'created_at': datetime.utcnow()
            })

            flash('Đăng ký thành công! Vui lòng đăng nhập.', 'success')
            return redirect(url_for('login'))

        except Exception as e:
            flash('Có lỗi xảy ra. Vui lòng thử lại!', 'error')
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# Thêm route mặc định để xử lý 404
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

@app.errorhandler(Exception)
def handle_exception(e):
    # Log the error
    app.logger.error(f'Unhandled exception: {str(e)}')
    return render_template('500.html'), 500

@app.before_request
def check_db_connection():
    if client is None or db is None:
        connect_db()  # Try to reconnect
        if client is None or db is None:
            return 'Database connection error. Please try again later.', 500
    try:
        # Verify database connection before each request
        client.admin.command('ping')
    except Exception as e:
        app.logger.error(f'Database connection error: {str(e)}')
        connect_db()  # Try to reconnect
        if client is None or db is None:
            return 'Database connection error. Please try again later.', 500

@app.route('/teacher/dashboard')
def teacher_dashboard():
    if 'user_id' not in session or session['role'] != 'teacher':
        flash('Bạn không có quyền truy cập trang này!')
        return redirect(url_for('home'))
    
    teacher_id = ObjectId(session['user_id'])
    
    # Get total number of quizzes
    total_quizzes = db.quizzes.count_documents({'teacher_id': teacher_id})
    
    # Get number of students who took the quizzes
    student_ids = db.quiz_results.distinct('student_id', {'quiz_id': {'$in': [q['_id'] for q in db.quizzes.find({'teacher_id': teacher_id})]}})
    total_students = len(student_ids)
    
    # Get 5 most recent quizzes
    recent_quizzes = list(db.quizzes.find({'teacher_id': teacher_id}).sort('_id', -1).limit(5))
    
    return render_template('teacher_dashboard.html',
                         total_quizzes=total_quizzes,
                         total_students=total_students,
                         recent_quizzes=recent_quizzes)

def generate_quiz_code():
    """Generate a random 4-character quiz code"""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase, k=4))
        if not db.quizzes.find_one({'quiz_code': code}):
            return code

@app.route('/create_quiz', methods=['GET', 'POST'])
def create_quiz():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = db.users.find_one({'_id': ObjectId(session['user_id'])})
    if user['role'] != 'teacher':
        flash('Only teachers can create quizzes')
        return redirect(url_for('home'))

    if request.method == 'POST':
        try:
            title = request.form['title']
            
            # Chuyển đổi thời gian đầu vào sang UTC
            start_time_local = datetime.strptime(request.form['start_time'], '%Y-%m-%dT%H:%M')
            end_time_local = datetime.strptime(request.form['end_time'], '%Y-%m-%dT%H:%M')
            
            # Chuyển đổi sang UTC để lưu vào database
            start_time = convert_local_to_utc(start_time_local)
            end_time = convert_local_to_utc(end_time_local)
            
            # In ra debug để kiểm tra
            print(f"Create quiz - Local start time: {start_time_local}")
            print(f"Create quiz - UTC start time: {start_time}")
            print(f"Create quiz - Local end time: {end_time_local}")
            print(f"Create quiz - UTC end time: {end_time}")
            
            duration = request.form['duration']
            max_attempts = request.form.get('max_attempts')
            is_public = request.form.get('is_public') == 'on'
            
            # Validate required fields
            if not all([title, start_time, end_time, duration]):
                flash('Vui lòng điền đầy đủ các trường bắt buộc', 'error')
                return redirect(url_for('create_quiz'))

            if start_time >= end_time:
                flash('Thời gian kết thúc phải sau thời gian bắt đầu', 'error')
                return redirect(url_for('create_quiz'))

            try:
                duration = int(duration)
                if duration <= 0:
                    flash('Thời gian làm bài phải lớn hơn 0', 'error')
                    return redirect(url_for('create_quiz'))
            except ValueError:
                flash('Thời gian làm bài phải là số nguyên', 'error')
                return redirect(url_for('create_quiz'))

            if max_attempts:
                try:
                    max_attempts = int(max_attempts)
                    if max_attempts <= 0:
                        flash('Số lần làm bài phải lớn hơn 0', 'error')
                        return redirect(url_for('create_quiz'))
                except ValueError:
                    flash('Số lần làm bài phải là số nguyên', 'error')
                    return redirect(url_for('create_quiz'))

            # Create quiz
            quiz_id = db.quizzes.insert_one({
                'title': title,
                'teacher_id': ObjectId(session['user_id']),
                'start_time': start_time,
                'end_time': end_time,
                'duration': duration,
                'max_attempts': max_attempts if max_attempts else None,
                'is_public': is_public,
                'quiz_code': generate_quiz_code(),
                'created_at': datetime.utcnow()
            }).inserted_id
            
            # Get questions data
            questions = request.form.getlist('questions[]')
            question_types = request.form.getlist('question_types[]')
            correct_answers = request.form.getlist('correct_answers[]')
            
            if not questions:
                flash('Vui lòng thêm ít nhất một câu hỏi', 'error')
                db.quizzes.delete_one({'_id': quiz_id})  # Delete the quiz if no questions
                return redirect(url_for('create_quiz'))

            # Create questions
            for i in range(len(questions)):
                question_id = db.questions.insert_one({
                    'quiz_id': quiz_id,
                    'question_text': questions[i],
                    'question_type': question_types[i],
                    'correct_answer': correct_answers[i]
                }).inserted_id
                
                if question_types[i] == 'multiple_choice':
                    for j in range(4):
                        option = request.form.getlist(f'option{j+1}[]')[i]
                        if option:
                            db.answers.insert_one({
                                'question_id': question_id,
                                'answer_text': option
                            })
            
            flash('Tạo bài kiểm tra thành công!', 'success')
            return redirect(url_for('manage_quizzes'))
            
        except Exception as e:
            flash(f'Có lỗi xảy ra: {str(e)}', 'error')
            return redirect(url_for('create_quiz'))

    return render_template('create_quiz.html')

@app.route('/manage-quizzes')
def manage_quizzes():
    if 'user_id' not in session or session['role'] != 'teacher':
        flash('Bạn không có quyền truy cập trang này!')
        return redirect(url_for('home'))
    
    teacher_id = ObjectId(session['user_id'])
    quizzes = list(db.quizzes.find({'teacher_id': teacher_id}).sort('_id', -1))
    
    return render_template('manage_quizzes.html', quizzes=quizzes)

@app.route('/history')
def history():
    if 'user_id' not in session:
        flash('Vui lòng đăng nhập để xem lịch sử!')
        return redirect(url_for('login'))
    
    try:
        if session['role'] == 'student':
            results = list(db.quiz_results.find({'student_id': ObjectId(session['user_id'])}).sort('_id', -1))
            
            # Lấy thông tin quiz cho mỗi kết quả
            for result in results:
                quiz = db.quizzes.find_one({'_id': result['quiz_id']})
                if quiz:
                    result['quiz'] = quiz
                else:
                    result['quiz'] = {'title': 'Bài kiểm tra đã bị xóa'}
                
                # Chuyển đổi thời gian UTC sang thời gian địa phương
                if 'submitted_at' in result:
                    result['local_submitted_at'] = convert_utc_to_local(result['submitted_at'])
            
            return render_template('history.html', results=results, datetime=datetime)
        else:
            quizzes = list(db.quizzes.find({'teacher_id': ObjectId(session['user_id'])}).sort('_id', -1))
            
            # Chuyển đổi thời gian UTC sang thời gian địa phương
            for quiz in quizzes:
                quiz['local_start_time'] = convert_utc_to_local(quiz['start_time'])
                quiz['local_end_time'] = convert_utc_to_local(quiz['end_time'])
                
            # Thêm thông tin số kết quả cho mỗi bài kiểm tra
            for quiz in quizzes:
                quiz['results'] = list(db.quiz_results.find({'quiz_id': ObjectId(quiz['_id'])}))
                
                # Chuyển đổi thời gian cho mỗi kết quả
                for result in quiz['results']:
                    if 'submitted_at' in result:
                        result['local_submitted_at'] = convert_utc_to_local(result['submitted_at'])
            
            return render_template('history.html', quizzes=quizzes, datetime=datetime)
    except Exception as e:
        app.logger.error(f'Error in history route: {str(e)}')
        flash('Có lỗi xảy ra khi tải lịch sử. Vui lòng thử lại sau.', 'error')
        return redirect(url_for('home'))

@app.route('/view-quiz/<quiz_id>')
def view_quiz(quiz_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    quiz = db.quizzes.find_one({'_id': ObjectId(quiz_id)})
    user = db.users.find_one({'_id': ObjectId(session['user_id'])})
    
    if user['role'] != 'teacher' or str(quiz['teacher_id']) != session['user_id']:
        flash('Bạn không có quyền truy cập bài kiểm tra này!')
        return redirect(url_for('home'))
    
    questions = list(db.questions.find({'quiz_id': ObjectId(quiz['_id'])}))
    
    # Lấy danh sách đáp án cho mỗi câu hỏi
    for question in questions:
        question['answers'] = list(db.answers.find({'question_id': question['_id']}))
    
    return render_template('view_quiz.html', quiz=quiz, questions=questions)

@app.route('/quiz/edit/<quiz_id>', methods=['GET', 'POST'])
def edit_quiz(quiz_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        flash('Bạn không có quyền truy cập trang này!')
        return redirect(url_for('home'))
    
    quiz = db.quizzes.find_one({'_id': ObjectId(quiz_id)})
    
    if str(quiz['teacher_id']) != session['user_id']:
        flash('Bạn không có quyền chỉnh sửa bài kiểm tra này!')
        return redirect(url_for('manage_quizzes'))
    
    if request.method == 'POST':
        try:
            quiz['title'] = request.form.get('title')
            
            # Đảm bảo lưu trữ thời gian ở dạng UTC
            start_time_str = request.form.get('start_time')
            end_time_str = request.form.get('end_time')
            
            # Xử lý trường hợp start_time_str
            if 'T' in start_time_str:
                # Định dạng ISO từ input datetime-local
                start_time_local = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M')
            else:
                # Định dạng từ chuỗi đã được format
                start_time_local = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S')
                
            # Xử lý trường hợp end_time_str
            if 'T' in end_time_str:
                # Định dạng ISO từ input datetime-local
                end_time_local = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
            else:
                # Định dạng từ chuỗi đã được format
                end_time_local = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S')
            
            # Chuyển đổi sang UTC để lưu vào database
            quiz['start_time'] = convert_local_to_utc(start_time_local)
            quiz['end_time'] = convert_local_to_utc(end_time_local)
            
            # In thông tin debug
            print(f"Edit quiz - Local start time: {start_time_local}")
            print(f"Edit quiz - UTC start time: {quiz['start_time']}")
            print(f"Edit quiz - Local end time: {end_time_local}")
            print(f"Edit quiz - UTC end time: {quiz['end_time']}")
            
            quiz['duration'] = int(request.form.get('duration'))
            max_attempts = request.form.get('max_attempts')
            quiz['max_attempts'] = int(max_attempts) if max_attempts else None
            db.quizzes.update_one({'_id': ObjectId(quiz['_id'])}, {'$set': quiz})
            
            # Delete old questions and answers
            question_ids = [q['_id'] for q in db.questions.find({'quiz_id': ObjectId(quiz['_id'])})]
            db.answers.delete_many({'question_id': {'$in': question_ids}})
            db.questions.delete_many({'quiz_id': ObjectId(quiz['_id'])})
            
            # Add new questions
            questions = request.form.getlist('questions[]')
            question_types = request.form.getlist('question_types[]')
            correct_answers = request.form.getlist('correct_answers[]')
            
            for i in range(len(questions)):
                # Create question
                question_id = db.questions.insert_one({
                    'quiz_id': ObjectId(quiz['_id']),
                    'question_text': questions[i],
                    'question_type': question_types[i],
                    'correct_answer': correct_answers[i]
                }).inserted_id
                
                if question_types[i] == 'multiple_choice':
                    for j in range(4):
                        option = request.form.getlist(f'option{j+1}[]')[i]
                        if option:
                            db.answers.insert_one({
                                'question_id': question_id,
                                'answer_text': option
                            })
            
            flash('Cập nhật bài kiểm tra thành công!', 'success')
            return redirect(url_for('manage_quizzes'))
            
        except Exception as e:
            flash(f'Có lỗi xảy ra khi cập nhật bài kiểm tra: {str(e)}', 'error')
            return redirect(url_for('edit_quiz', quiz_id=quiz_id))
    
    # Lấy danh sách câu hỏi của bài kiểm tra
    questions = list(db.questions.find({'quiz_id': ObjectId(quiz_id)}))
    
    # Lấy đáp án cho mỗi câu hỏi
    for question in questions:
        question['answers'] = list(db.answers.find({'question_id': question['_id']}))
    
    # Thêm danh sách câu hỏi vào quiz để hiển thị trong template
    quiz['questions'] = questions
    
    return render_template('edit_quiz.html', quiz=quiz)

@app.route('/delete-quiz/<quiz_id>')
def delete_quiz(quiz_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        flash('Bạn không có quyền truy cập trang này!')
        return redirect(url_for('home'))
    
    quiz = db.quizzes.find_one({'_id': ObjectId(quiz_id)})
    
    if str(quiz['teacher_id']) != session['user_id']:
        flash('Bạn không có quyền xóa bài kiểm tra này!')
        return redirect(url_for('manage_quizzes'))
    
    try:
        # Delete quiz results
        db.quiz_results.delete_many({'quiz_id': ObjectId(quiz['_id'])})
        
        # Delete questions and answers
        question_ids = [q['_id'] for q in db.questions.find({'quiz_id': ObjectId(quiz['_id'])})]
        db.answers.delete_many({'question_id': {'$in': question_ids}})
        db.questions.delete_many({'quiz_id': ObjectId(quiz['_id'])})
        
        # Delete quiz
        db.quizzes.delete_one({'_id': ObjectId(quiz['_id'])})
        
        flash('Xóa bài kiểm tra thành công!')
    except Exception as e:
        flash(f'Có lỗi xảy ra khi xóa bài kiểm tra: {str(e)}')
    
    return redirect(url_for('manage_quizzes'))

@app.route('/search')
def search_quiz():
    try:
        keyword = request.args.get('keyword', '')
        if not keyword:
            return redirect(url_for('home'))
        
        # Tìm tất cả các bài kiểm tra có tiêu đề khớp với từ khóa (chỉ lấy bài công khai nếu là học sinh)
        query = {'title': {'$regex': keyword, '$options': 'i'}}
        
        # Nếu người dùng là học sinh, chỉ hiển thị bài kiểm tra công khai
        if 'role' in session and session['role'] == 'student':
            query['is_public'] = True
        
        quizzes = list(db.quizzes.find(query))
        
        # Thêm thông tin giáo viên cho mỗi bài kiểm tra
        for quiz in quizzes:
            teacher = db.users.find_one({'_id': quiz['teacher_id']})
            if teacher:
                quiz['teacher'] = {
                    'username': teacher['username'],
                    'id': str(teacher['_id'])
                }
            else:
                quiz['teacher'] = {'username': 'Unknown', 'id': ''}
            
            # Chuyển ObjectId thành chuỗi để có thể serialized thành JSON
            quiz['id'] = str(quiz['_id'])
        
        return render_template('search_results.html', 
                             quizzes=quizzes, 
                             keyword=keyword)
    except Exception as e:
        app.logger.error(f'Lỗi tìm kiếm: {str(e)}')
        flash(f'Có lỗi xảy ra khi tìm kiếm: {str(e)}', 'error')
        return redirect(url_for('home'))

@app.route('/join_quiz', methods=['GET', 'POST'])
def join_quiz():
    if 'user_id' not in session:
        flash('Vui lòng đăng nhập để tham gia bài kiểm tra!', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        quiz_code = request.form.get('quiz_code')
        quiz = db.quizzes.find_one({'quiz_code': quiz_code})

        if not quiz:
            flash('Mã bài kiểm tra không tồn tại!', 'error')
            return redirect(url_for('join_quiz'))

        # Lấy thời gian hiện tại theo UTC để so sánh với dữ liệu trong DB
        current_time = datetime.utcnow()
        
        # In ra debug để kiểm tra
        print(f"Join quiz - Current UTC time: {current_time}")
        print(f"Join quiz - Quiz UTC start time: {quiz['start_time']}")
        print(f"Join quiz - Quiz UTC end time: {quiz['end_time']}")
        
        # Kiểm tra thời gian bắt đầu
        if current_time < quiz['start_time']:
            # Chuyển múi giờ về địa phương để hiển thị thông báo
            local_start_time = convert_utc_to_local(quiz['start_time'])
            formatted_start = local_start_time.strftime('%d/%m/%Y %H:%M')
            
            flash(f'Bài kiểm tra chưa bắt đầu! Bài kiểm tra sẽ bắt đầu vào lúc {formatted_start}', 'error')
            return redirect(url_for('join_quiz'))
        
        # Kiểm tra thời gian kết thúc
        if current_time > quiz['end_time']:
            # Chuyển múi giờ về địa phương để hiển thị thông báo
            local_end_time = convert_utc_to_local(quiz['end_time'])
            formatted_end = local_end_time.strftime('%d/%m/%Y %H:%M')
            
            flash(f'Bài kiểm tra đã kết thúc vào lúc {formatted_end}!', 'error')
            return redirect(url_for('join_quiz'))

        if quiz['max_attempts']:
            attempt_count = db.quiz_results.count_documents({'quiz_id': ObjectId(quiz['_id']), 'student_id': ObjectId(session['user_id'])})
            
            if attempt_count >= quiz['max_attempts']:
                flash(f'Bạn đã vượt quá số lần làm bài cho phép ({quiz["max_attempts"]} lần)!', 'error')
                return redirect(url_for('join_quiz'))

        return redirect(url_for('take_quiz', quiz_id=str(quiz['_id']), quiz_code=quiz_code))

    return render_template('join_quiz.html')

@app.route('/take_quiz/<quiz_id>')
def take_quiz(quiz_id):
    try:
        if 'user_id' not in session:
            flash('Vui lòng đăng nhập để làm bài kiểm tra!', 'error')
            return redirect(url_for('login'))

        quiz = db.quizzes.find_one({'_id': ObjectId(quiz_id)})

        if not quiz:
            flash('Bài kiểm tra không tồn tại!', 'error')
            return redirect(url_for('home'))

        # Ensure the user is allowed to take this quiz
        if session['role'] == 'student':
            quiz_code_param = request.args.get('quiz_code')  # Lấy từ URL parameter
            if not quiz['is_public']:
                if not quiz_code_param or quiz_code_param != quiz['quiz_code']:
                    flash('Bài kiểm tra này ở chế độ riêng tư. Vui lòng sử dụng mã bài kiểm tra để tham gia!', 'error')
                    return redirect(url_for('join_quiz'))

        # Check time validation
        current_time = datetime.utcnow()
        if current_time < quiz['start_time']:
            local_start_time = convert_utc_to_local(quiz['start_time'])
            formatted_start = local_start_time.strftime('%d/%m/%Y %H:%M')
            flash(f'Bài kiểm tra chưa bắt đầu! Bài kiểm tra sẽ bắt đầu vào lúc {formatted_start}', 'error')
            return redirect(url_for('home'))

        if current_time > quiz['end_time']:
            local_end_time = convert_utc_to_local(quiz['end_time'])
            formatted_end = local_end_time.strftime('%d/%m/%Y %H:%M')
            flash(f'Bài kiểm tra đã kết thúc vào lúc {formatted_end}!', 'error')
            return redirect(url_for('home'))

        if quiz.get('max_attempts'):
            attempt_count = db.quiz_results.count_documents({'quiz_id': ObjectId(quiz['_id']), 'student_id': ObjectId(session['user_id'])})
            if attempt_count >= quiz['max_attempts']:
                flash(f'Bạn đã vượt quá số lần làm bài cho phép ({quiz["max_attempts"]} lần)!', 'error')
                return redirect(url_for('home'))

        questions = list(db.questions.find({'quiz_id': ObjectId(quiz['_id'])}))
        if not questions:
            flash('Bài kiểm tra này chưa có câu hỏi!', 'error')
            return redirect(url_for('home'))
            
        # Lấy đáp án cho các câu hỏi trắc nghiệm
        for question in questions:
            question['answers'] = list(db.answers.find({'question_id': question['_id']}))
            
        # Create a new attempt for this quiz
        attempt = db.quiz_attempts.insert_one({
            'quiz_id': ObjectId(quiz['_id']),
            'student_id': ObjectId(session['user_id']),
            'start_time': current_time,
            'submitted': False,
            'answers': [],
            'score': 0
        })
        
        # Get the created attempt
        attempt_doc = db.quiz_attempts.find_one({'_id': attempt.inserted_id})

        return render_template('take_quiz.html', quiz=quiz, questions=questions, attempt=attempt_doc)
    
    except Exception as e:
        app.logger.error(f'Error in take_quiz route: {str(e)}')
        flash('Đã xảy ra lỗi khi tải bài kiểm tra.', 'error')
        return redirect(url_for('home'))  # Redirect về trang chủ thay vì hiển thị 500

@app.route('/submit_quiz/<quiz_id>/<attempt_id>', methods=['POST'])
@login_required
def submit_quiz(quiz_id, attempt_id):
    try:
        quiz = db.quizzes.find_one({'_id': ObjectId(quiz_id)})
        attempt = db.quiz_attempts.find_one({
            '_id': ObjectId(attempt_id),
            'student_id': ObjectId(session['user_id'])
        })
        
        if not quiz or not attempt:
            flash('Bài kiểm tra hoặc lần làm bài không tồn tại', 'error')
            return redirect(url_for('home'))
            
        if attempt['submitted']:
            flash('Bài kiểm tra đã được nộp rồi', 'error')
            return redirect(url_for('quiz_results', quiz_id=quiz_id))
            
        # Sử dụng UTC để so sánh thời gian
        current_time = datetime.utcnow()
        print(f"Submit quiz - Current time: {current_time}")
        print(f"Submit quiz - Quiz end time: {quiz['end_time']}")
        
        if current_time > quiz['end_time']:
            # Chuyển múi giờ về địa phương để hiển thị thông báo
            local_end_time = convert_utc_to_local(quiz['end_time'])
            formatted_end = local_end_time.strftime('%d/%m/%Y %H:%M')
            
            flash(f'Bài kiểm tra đã kết thúc vào lúc {formatted_end}!', 'error')
            return redirect(url_for('home'))

        # Lấy tất cả câu hỏi từ bài kiểm tra
        questions = list(db.questions.find({'quiz_id': ObjectId(quiz_id)}))
        
        # Xử lý câu trả lời
        answers = []
        score = 0
        total_questions = len(questions)
        
        for question in questions:
            answer_key = f"answer_{question['_id']}"
            user_answer = request.form.get(answer_key)
            
            if not user_answer:
                continue
                
            # Kiểm tra câu trả lời
            is_correct = False
            
            if question['question_type'] == 'multiple_choice':
                # Với câu hỏi trắc nghiệm, cần so sánh với đáp án đúng
                correct_answer_id = question['correct_answer']  # Correct answer is stored as ObjectId
                is_correct = (user_answer == str(correct_answer_id))  # Compare with the submitted answer ID
            else:
                # Với câu hỏi điền, so sánh trực tiếp
                is_correct = (user_answer.lower().strip() == question['correct_answer'].lower().strip())
            
            # Lưu câu trả lời
            answers.append({
                'question_id': question['_id'],
                'user_answer': user_answer,
                'is_correct': is_correct
            })
            
            if is_correct:
                score += 1

        # Tính điểm
        final_score = (score / total_questions) * 10 if total_questions > 0 else 0
        
        # Cập nhật attempt
        db.quiz_attempts.update_one(
            {'_id': ObjectId(attempt_id)},
            {
                '$set': {
                    'answers': answers,
                    'score': final_score,
                    'submitted': True,
                    'submit_time': current_time
                }
            }
        )
        
        # Tạo kết quả bài kiểm tra
        db.quiz_results.insert_one({
            'quiz_id': ObjectId(quiz_id),
            'student_id': ObjectId(session['user_id']),
            'attempt_id': ObjectId(attempt_id),
            'score': final_score,
            'submitted_at': current_time
        })
            
        flash('Nộp bài kiểm tra thành công!', 'success')
        return redirect(url_for('quiz_results', quiz_id=quiz_id))
        
    except Exception as e:
        app.logger.error(f'Error submitting quiz: {str(e)}')
        flash(f'Có lỗi xảy ra khi nộp bài: {str(e)}', 'error')
        return redirect(url_for('home'))

@app.route('/quiz_results/<quiz_id>')
@login_required
def quiz_results(quiz_id):
    try:
        quiz = db.quizzes.find_one({'_id': ObjectId(quiz_id)})
        if not quiz:
            flash('Bài kiểm tra không tồn tại', 'error')
            return redirect(url_for('manage_quizzes') if session.get('role') == 'teacher' else url_for('home'))

        # Chuyển đổi thời gian UTC sang thời gian địa phương
        quiz['local_start_time'] = convert_utc_to_local(quiz['start_time'])
        quiz['local_end_time'] = convert_utc_to_local(quiz['end_time'])

        # Check if user is teacher and owns the quiz
        if session['role'] == 'teacher':
            if str(quiz['teacher_id']) != session['user_id']:
                flash('Bạn không có quyền xem kết quả của bài kiểm tra này', 'error')
                return redirect(url_for('manage_quizzes'))
            
            # Lấy tất cả các lần làm bài cho bài kiểm tra này
            results = list(db.quiz_results.find({'quiz_id': ObjectId(quiz_id)}).sort('submitted_at', -1))
            
            # Chuyển đổi thời gian cho mỗi kết quả
            for result in results:
                if 'submitted_at' in result:
                    result['local_submit_time'] = convert_utc_to_local(result['submitted_at'])
            
            # Lấy thông tin học sinh cho mỗi kết quả
            for result in results:
                student = db.users.find_one({'_id': ObjectId(result['student_id'])})
                result['student'] = student
                
                # Lấy thông tin chi tiết về câu trả lời
                if 'attempt_id' in result:
                    attempt = db.quiz_attempts.find_one({'_id': ObjectId(result['attempt_id'])})
                    if attempt and 'answers' in attempt:
                        result['answers'] = attempt['answers']
                
            return render_template('quiz_results.html', 
                                quiz=quiz,
                                results=results)
        else:
            # Đối với học sinh, chỉ hiển thị các lần làm bài của họ
            results = list(db.quiz_results.find({
                'quiz_id': ObjectId(quiz_id),
                'student_id': ObjectId(session['user_id'])
            }).sort('submitted_at', -1))
            
            # Chuyển đổi thời gian cho mỗi kết quả
            for result in results:
                if 'submitted_at' in result:
                    result['local_submit_time'] = convert_utc_to_local(result['submitted_at'])
            
            # Lấy chi tiết về các câu trả lời
            for result in results:
                if 'attempt_id' in result:
                    attempt = db.quiz_attempts.find_one({'_id': ObjectId(result['attempt_id'])})
                    if attempt and 'answers' in attempt:
                        result['answers'] = attempt['answers']
            
            if not results:
                flash('Bạn chưa làm bài kiểm tra này', 'info')
                return redirect(url_for('home'))
                
            # Lấy danh sách câu hỏi để hiển thị đáp án đúng
            questions = list(db.questions.find({'quiz_id': ObjectId(quiz_id)}))
            
            # Lấy các đáp án cho câu hỏi trắc nghiệm
            for question in questions:
                question['answers'] = list(db.answers.find({'question_id': question['_id']}))
                
            return render_template('student_quiz_results.html',
                                quiz=quiz,
                                results=results,
                                questions=questions)
                            
    except Exception as e:
        app.logger.error(f'Error in quiz_results route: {str(e)}')
        flash(f'Có lỗi xảy ra: {str(e)}', 'error')
        return redirect(url_for('manage_quizzes') if session['role'] == 'teacher' else url_for('home'))

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = db.users.find_one({'_id': ObjectId(session['user_id'])})
    user_profile = db.user_profiles.find_one({'user_id': ObjectId(session['user_id'])})
    
    if not user_profile:
        user_profile = db.user_profiles.insert_one({
            'user_id': ObjectId(session['user_id']),
            'created_at': datetime.utcnow()
        })

    return render_template('profile.html', user=user, profile=user_profile)

@app.route('/profile/edit', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = db.users.find_one({'_id': ObjectId(session['user_id'])})
    profile = db.user_profiles.find_one({'user_id': ObjectId(session['user_id'])})
    
    if request.method == 'POST':
        # Cập nhật thông tin profile
        profile['full_name'] = request.form.get('full_name')
        profile['phone'] = request.form.get('phone')
        profile['address'] = request.form.get('address')
        profile['bio'] = request.form.get('bio')
        
        db.user_profiles.update_one({'_id': ObjectId(profile['_id'])}, {'$set': profile})
        flash('Cập nhật thông tin thành công!')
        return redirect(url_for('profile'))
    
    return render_template('edit_profile.html', user=user, profile=profile)

@app.route('/settings')
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = db.users.find_one({'_id': ObjectId(session['user_id'])})
    return render_template('settings.html', user=user)

@app.route('/settings/password', methods=['POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = db.users.find_one({'_id': ObjectId(session['user_id'])})
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not check_password_hash(user['password'], current_password):
        flash('Mật khẩu hiện tại không đúng!')
        return redirect(url_for('settings'))
    
    if new_password != confirm_password:
        flash('Mật khẩu mới không khớp!')
        return redirect(url_for('settings'))
    
    hashed_password = generate_password_hash(new_password)
    db.users.update_one({'_id': ObjectId(session['user_id'])}, {'$set': {'password': hashed_password}})
    flash('Đổi mật khẩu thành công!')
    return redirect(url_for('settings'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = db.users.find_one({'email': email})
        
        if user:
            # Generate a unique token
            token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
            expires_at = datetime.utcnow() + timedelta(hours=1)  # Token expires in 1 hour
            
            # Create password reset token
            db.password_reset_tokens.insert_one({
                'user_id': ObjectId(user['_id']),
                'token': token,
                'created_at': datetime.utcnow(),
                'expires_at': expires_at
            })
            
            # Redirect directly to reset password page
            return redirect(url_for('reset_password', token=token))
        
        flash('Email không tồn tại trong hệ thống.', 'error')
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    reset_token = db.password_reset_tokens.find_one({'token': token, 'used': False})
    
    if not reset_token:
        flash('Link đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.', 'error')
        return redirect(url_for('forgot_password'))
    
    if datetime.utcnow() > reset_token['expires_at']:
        flash('Link đặt lại mật khẩu đã hết hạn.', 'error')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Mật khẩu xác nhận không khớp.', 'error')
            return render_template('reset_password.html')
        
        # Update user's password
        hashed_password = generate_password_hash(password)
        db.users.update_one({'_id': ObjectId(reset_token['user_id'])}, {'$set': {'password': hashed_password}})
        db.password_reset_tokens.update_one({'_id': ObjectId(reset_token['_id'])}, {'$set': {'used': True}})
        
        flash('Mật khẩu đã được đặt lại thành công. Vui lòng đăng nhập.', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html')

@app.route('/quiz/<quiz_id>/toggle-visibility')
def toggle_quiz_visibility(quiz_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        flash('Bạn không có quyền thực hiện hành động này!')
        return redirect(url_for('home'))
    
    quiz = db.quizzes.find_one({'_id': ObjectId(quiz_id)})
    
    # Kiểm tra quyền truy cập
    if str(quiz['teacher_id']) != session['user_id']:
        flash('Bạn không có quyền thay đổi trạng thái bài kiểm tra này!')
        return redirect(url_for('manage_quizzes'))
    
    # Đảo ngược trạng thái công khai
    db.quizzes.update_one({'_id': ObjectId(quiz_id)}, {'$set': {'is_public': not quiz['is_public']}})
    
    status = "công khai" if not quiz['is_public'] else "riêng tư"
    flash(f'Trạng thái bài kiểm tra đã được thay đổi thành {status}!')
    return redirect(url_for('manage_quizzes'))

@app.route('/firebase-login', methods=['POST'])
def firebase_login():
    data = request.get_json()
    id_token = data.get('idToken')

    if not id_token:
        return jsonify({"error": "No ID token provided"}), 400

    try:
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        email = decoded_token.get('email')
        name = decoded_token.get('name', email.split('@')[0])
        
        # Tìm user trong database theo email
        user = get_user_by_email(email)
        if not user:
            # Tạo user mới nếu chưa tồn tại
            random_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            hashed_password = generate_password_hash(random_password)
            
            user = create_user(
                email=email,
                username=email.split('@')[0],
                password=hashed_password,
                role='student'
            )

        # Tạo session
        session['user_id'] = str(user['_id'])
        session['username'] = user['username']
        session['role'] = user['role']

        return jsonify({"message": "Đăng nhập thành công"})
    except Exception as e:
        print(f"Lỗi xác thực token Firebase: {e}")
        return jsonify({"error": "Token không hợp lệ"}), 401

@app.route('/health')
def health_check():
    """Health check endpoint for Cloud Run."""
    try:
        # Kiểm tra kết nối đến database
        if client and db:
            client.admin.command('ping')
            return jsonify({"status": "ok"}), 200
        else:
            return jsonify({"status": "error", "message": "Database connection failed"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def main():
    try:
        port = int(os.environ.get('PORT', 8080))
        print(f"Starting server on port {port}")
        # Đặt threaded=True để xử lý đồng thời nhiều request
        # Đặt debug=False cho môi trường production
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
    except Exception as e:
        print(f"Error starting server: {str(e)}")
        sys.exit(1)  # Exit with error code


if __name__ == "__main__":
    main()

# Chỉnh sửa template context processor để thêm hàm đổi múi giờ cho tất cả template
@app.context_processor
def utility_processor():
    return {
        'convert_utc_to_local': convert_utc_to_local,
        'convert_local_to_utc': convert_local_to_utc,
        'format_datetime': lambda dt, fmt='%d/%m/%Y %H:%M': convert_utc_to_local(dt).strftime(fmt) if dt else ""
    }
