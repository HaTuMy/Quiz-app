from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from pymongo.database import Database
from bson import ObjectId
import os
from datetime import datetime, timedelta
import random
import string
import re
from typing import Any, Optional, cast
import ssl
import certifi
from functools import wraps
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')

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
        # Create a new client and connect to the server with SSL configuration
        client = MongoClient(
            MONGODB_URI,
            tls=True,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            socketTimeoutMS=10000
        )
        
        # Send a ping to confirm a successful connection
        client.admin.command('ping')
        print("MongoDB connection successful!")
        
        # Get database
        db = cast(Database, client[MONGODB_DATABASE])
        
    except Exception as e:
        print(f"MongoDB connection error: {str(e)}")
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

# Utility functions and decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@app.route('/home')
def home():
    return render_template('home.html')

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
            start_time = datetime.strptime(request.form['start_time'], '%Y-%m-%dT%H:%M')
            end_time = datetime.strptime(request.form['end_time'], '%Y-%m-%dT%H:%M')
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
    
    if session['role'] == 'student':
        results = list(db.quiz_results.find({'student_id': ObjectId(session['user_id'])}).sort('_id', -1))
        return render_template('history.html', results=results, datetime=datetime)
    else:
        quizzes = list(db.quizzes.find({'teacher_id': ObjectId(session['user_id'])}).sort('_id', -1))
        return render_template('history.html', quizzes=quizzes, datetime=datetime)

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
            quiz['start_time'] = datetime.fromisoformat(request.form.get('start_time').replace('Z', '+00:00'))
            quiz['end_time'] = datetime.fromisoformat(request.form.get('end_time').replace('Z', '+00:00'))
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
    keyword = request.args.get('keyword', '')
    if not keyword:
        return redirect(url_for('home'))
    
    quizzes = list(db.quizzes.find({'title': {'$regex': keyword, '$options': 'i'}}))
    
    return render_template('search_results.html', 
                         quizzes=quizzes, 
                         keyword=keyword)

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

        current_time = datetime.now()
        if current_time < quiz['start_time']:
            flash('Bài kiểm tra chưa bắt đầu!', 'error')
            return redirect(url_for('join_quiz'))
        
        if current_time > quiz['end_time']:
            flash('Bài kiểm tra đã kết thúc!', 'error')
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
    if 'user_id' not in session:
        flash('Vui lòng đăng nhập để làm bài kiểm tra!', 'error')
        return redirect(url_for('login'))

    quiz = db.quizzes.find_one({'_id': ObjectId(quiz_id)})
    
    if session['role'] == 'student':
        if not quiz['is_public']:
            quiz_code = request.args.get('quiz_code')
            if not quiz_code or quiz_code != quiz['quiz_code']:
                flash('Bài kiểm tra này ở chế độ riêng tư. Vui lòng sử dụng mã bài kiểm tra để tham gia!', 'error')
                return redirect(url_for('join_quiz'))

    current_time = datetime.now()
    if current_time < quiz['start_time']:
        flash('Bài kiểm tra chưa bắt đầu!', 'error')
        return redirect(url_for('home'))
    
    if current_time > quiz['end_time']:
        flash('Bài kiểm tra đã kết thúc!', 'error')
        return redirect(url_for('home'))

    if quiz['max_attempts']:
        attempt_count = db.quiz_results.count_documents({'quiz_id': ObjectId(quiz['_id']), 'student_id': ObjectId(session['user_id'])})
        
        if attempt_count >= quiz['max_attempts']:
            flash(f'Bạn đã vượt quá số lần làm bài cho phép ({quiz["max_attempts"]} lần)!', 'error')
            return redirect(url_for('home'))

    questions = list(db.questions.find({'quiz_id': ObjectId(quiz['_id'])}))
    
    return render_template('take_quiz.html', quiz=quiz, questions=questions)

@app.route('/submit_quiz/<quiz_id>/<attempt_id>', methods=['POST'])
@login_required
def submit_quiz(quiz_id, attempt_id):
    try:
        quiz = db.quizzes.find_one({'_id': ObjectId(quiz_id)})
        attempt = db.quiz_attempts.find_one({
            '_id': ObjectId(attempt_id),
            'student_id': session['user_id']
        })
        
        if not quiz or not attempt:
            flash('Quiz or attempt not found', 'error')
            return redirect(url_for('student_dashboard'))
            
        if attempt['submitted']:
            flash('Quiz has already been submitted', 'error')
            return redirect(url_for('quiz_results', quiz_id=quiz_id, attempt_id=attempt_id))
            
        current_time = datetime.now()
        if current_time > quiz['end_time']:
            flash('Quiz has ended', 'error')
            return redirect(url_for('student_dashboard'))

        # Process answers
        answers = []
        score = 0
        for question in quiz['questions']:
            answer = request.form.get(f'answer_{question["_id"]}')
            if not answer:
                continue
                
            is_correct = answer == question['correct_answer']
            answers.append({
                'question_id': question['_id'],
                'answer': answer,
                'is_correct': is_correct
            })
            if is_correct:
                score += 1

        # Update attempt with answers and score
        result = db.quiz_attempts.update_one(
            {'_id': ObjectId(attempt_id)},
            {
                '$set': {
                    'answers': answers,
                    'score': score,
                    'submitted': True,
                    'submit_time': current_time
                }
            }
        )
        
        if result.modified_count == 0:
            flash('Failed to submit quiz', 'error')
            return redirect(url_for('take_quiz', quiz_id=quiz_id, attempt_id=attempt_id))
            
        flash('Quiz submitted successfully!', 'success')
        return redirect(url_for('quiz_results', quiz_id=quiz_id, attempt_id=attempt_id))
        
    except Exception as e:
        app.logger.error(f'Error submitting quiz: {str(e)}')
        flash('An error occurred while submitting the quiz', 'error')
        return redirect(url_for('student_dashboard'))

@app.route('/quiz_results/<quiz_id>')
@login_required
def quiz_results(quiz_id):
    try:
        quiz = db.quizzes.find_one({'_id': ObjectId(quiz_id)})
        if not quiz:
            flash('Bài kiểm tra không tồn tại', 'error')
            return redirect(url_for('manage_quizzes'))

        # Check if user is teacher and owns the quiz
        if session['role'] == 'teacher':
            if str(quiz['teacher_id']) != session['user_id']:
                flash('Bạn không có quyền xem kết quả của bài kiểm tra này', 'error')
                return redirect(url_for('manage_quizzes'))
            
            # Get all attempts for this quiz
            results = list(db.quiz_attempts.find({'quiz_id': ObjectId(quiz_id), 'submitted': True}))
            
            # Get student information for each attempt
            for result in results:
                student = db.users.find_one({'_id': ObjectId(result['student_id'])})
                result['student'] = student
                
            return render_template('quiz_results.html', 
                                quiz=quiz,
                                results=results)
        else:
            # For students, show only their attempts
            attempts = list(db.quiz_attempts.find({
                'quiz_id': ObjectId(quiz_id),
                'student_id': ObjectId(session['user_id']),
                'submitted': True
            }))
            
            if not attempts:
                flash('Bạn chưa làm bài kiểm tra này', 'info')
                return redirect(url_for('home'))
                
            return render_template('student_quiz_results.html',
                                quiz=quiz,
                                attempts=attempts)
                            
    except Exception as e:
        flash(f'Có lỗi xảy ra: {str(e)}', 'error')
        return redirect(url_for('manage_quizzes' if session['role'] == 'teacher' else 'home'))

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

def main():
    app.run(debug=True)

if __name__ == "__main__":
    main() 