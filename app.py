from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import firebase_config
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from flask_migrate import Migrate
from sqlalchemy.exc import IntegrityError
import random
import string
import re
import firebase_admin
from firebase_admin import credentials, firestore, auth
import requests
import json

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mathquiz.db'
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Khởi tạo Firebase Admin SDK
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
firestore_client = firestore.client()

# Configure session cookie settings
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)
app.config['SESSION_REFRESH_EACH_REQUEST'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Models
class User(db.Model):
    id = db.Column(db.Integer , primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'teacher' or 'student'

class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    quiz_code = db.Column(db.String(10), unique=True, nullable=True, server_default=None)  # Make it nullable with default None
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    duration = db.Column(db.Integer, nullable=False)  # in minutes
    max_attempts = db.Column(db.Integer, nullable=True, default=None)  # Số lần làm bài tối đa
    is_public = db.Column(db.Boolean, default=False)  # Thêm trường is_public
    questions = db.relationship('Question', backref='quiz', lazy=True)
    teacher = db.relationship('User', backref='quizzes', lazy=True)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    question_text = db.Column(db.String(500), nullable=False)
    question_type = db.Column(db.String(20), nullable=False)  # 'multiple_choice' or other types
    correct_answer = db.Column(db.String(500), nullable=False)
    answers = db.relationship('Answer', backref='question', lazy=True)

class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    answer_text = db.Column(db.String(500), nullable=False)

class QuizResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    score = db.Column(db.Float, nullable=False)
    submitted_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    
    quiz = db.relationship('Quiz', backref='results', lazy=True)
    student = db.relationship('User', backref='quiz_results', lazy=True)

class UserProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    full_name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    bio = db.Column(db.Text)
    avatar = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='profile', lazy=True)

class PasswordResetToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    
    user = db.relationship('User', backref='reset_tokens', lazy=True)

class StudentAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    answer_text = db.Column(db.String(500), nullable=False)

    quiz = db.relationship('Quiz', backref='student_answers', lazy=True)
    student = db.relationship('User', backref='student_answers', lazy=True)
    question = db.relationship('Question', backref='student_answers', lazy=True)

def init_db():
    with app.app_context():
        # Drop all tables
        db.drop_all()
        # Create all tables
        db.create_all()
        print("Database tables created successfully!")

# Routes
@app.route('/')
@app.route('/home')  # Thêm route này
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['role'] = user.role
            session['username'] = user.username
            flash('Đăng nhập thành công!',"success")
            
            # Chuyển hướng dựa trên role
            if user.role == 'teacher':
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

            # Kiểm tra username và email đã tồn tại
            existing_user = User.query.filter_by(username=username).first()
            existing_email = User.query.filter_by(email=email).first()
            
            if existing_user:
                flash('Tên đăng nhập đã tồn tại. Vui lòng chọn tên đăng nhập khác!', 'error')
                return redirect(url_for('register'))
            if existing_email:
                flash('Email đã được sử dụng. Vui lòng dùng email khác!', 'error')
                return redirect(url_for('register'))

            # Mã hóa mật khẩu
            hashed_password = generate_password_hash(password)
            
            # Tạo user mới
            new_user = User(
                email=email,
                username=username,
                password=hashed_password,
                role=role
            )
            db.session.add(new_user)
            db.session.flush()

            # Tạo profile cho user
            profile = UserProfile(
                user_id=new_user.id,
                full_name=username
            )
            db.session.add(profile)
            db.session.commit()

            flash('Đăng ký thành công! Vui lòng đăng nhập.', 'success')
            return redirect(url_for('login'))

        except Exception as e:
            db.session.rollback()
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

@app.route('/teacher/dashboard')
def teacher_dashboard():
    if 'user_id' not in session or session['role'] != 'teacher':
        flash('Bạn không có quyền truy cập trang này!')
        return redirect(url_for('home'))
    
    # Lấy thông tin thực tế từ database
    teacher_id = session['user_id']
    
    # Lấy tổng số bài kiểm tra của giáo viên
    total_quizzes = Quiz.query.filter_by(teacher_id=teacher_id).count()
    
    # Lấy số lượng học sinh đã tham gia các bài kiểm tra
    total_students = QuizResult.query.join(Quiz, QuizResult.quiz_id == Quiz.id)\
        .filter(Quiz.teacher_id == teacher_id)\
        .distinct(QuizResult.student_id)\
        .count()
    
    # Lấy 5 bài kiểm tra gần đây nhất
    recent_quizzes = Quiz.query.filter_by(teacher_id=teacher_id).order_by(Quiz.id.desc()).limit(5).all()
    
    return render_template('teacher_dashboard.html',
                         total_quizzes=total_quizzes,
                         total_students=total_students,
                         recent_quizzes=recent_quizzes)

def generate_quiz_code():
    """Generate a random 4-character quiz code"""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase, k=4))
        if not Quiz.query.filter_by(quiz_code=code).first():
            return code

@app.route('/create_quiz', methods=['GET', 'POST'])
def create_quiz():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if user.role != 'teacher':
        flash('Only teachers can create quizzes')
        return redirect(url_for('home'))

    if request.method == 'POST':
        try:
            # Tạo bài kiểm tra mới
            title = request.form['title']
            start_time = datetime.strptime(request.form['start_time'], '%Y-%m-%dT%H:%M')
            end_time = datetime.strptime(request.form['end_time'], '%Y-%m-%dT%H:%M')
            duration = int(request.form['duration'])
            max_attempts = request.form.get('max_attempts')  # Lấy giá trị max_attempts từ form
            is_public = request.form.get('is_public') == 'on'  # Lấy giá trị is_public từ form
            
            quiz = Quiz(
                title=title,
                teacher_id=session['user_id'],
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                max_attempts=int(max_attempts) if max_attempts else None,  # Chuyển đổi sang số nếu có giá trị
                is_public=is_public,  # Thêm trường is_public
                quiz_code=generate_quiz_code()
            )
            
            db.session.add(quiz)
            db.session.flush()
            
            # Lấy dữ liệu từ form
            questions = request.form.getlist('questions[]')
            question_types = request.form.getlist('question_types[]')
            correct_answers = request.form.getlist('correct_answers[]')
            
            # Thêm câu hỏi và câu trả lời
            for i in range(len(questions)):
                question = Question(
                    quiz_id=quiz.id,
                    question_text=questions[i],
                    question_type=question_types[i],
                    correct_answer=correct_answers[i]
                )
                db.session.add(question)
                db.session.flush()
                
                if question_types[i] == 'multiple_choice':
                    for j in range(4):
                        option = request.form.getlist(f'option{j+1}[]')[i]
                        if option:
                            answer = Answer(
                                question_id=question.id,
                                answer_text=option
                            )
                            db.session.add(answer)
            
            db.session.commit()
            flash(f'Quiz created successfully! Quiz Code: {quiz.quiz_code}')
            return redirect(url_for('manage_quizzes'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra khi tạo bài kiểm tra: {str(e)}')
            return redirect(url_for('create_quiz'))
    
    return render_template('create_quiz.html')

@app.route('/teacher/manage-quizzes')
def manage_quizzes():
    if 'user_id' not in session or session['role'] != 'teacher':
        flash('Bạn không có quyền truy cập trang này!')
        return redirect(url_for('home'))
    
    # Lấy danh sách bài kiểm tra của giáo viên từ database
    teacher_id = session['user_id']
    quizzes = Quiz.query.filter_by(teacher_id=teacher_id).order_by(Quiz.id.desc()).all()
    
    return render_template('manage_quizzes.html', quizzes=quizzes)

# Lịch sử bài kiểm tra
@app.route('/history')
def history():
    if 'user_id' not in session:
        flash('Vui lòng đăng nhập để xem lịch sử!')
        return redirect(url_for('login'))
    
    if session['role'] == 'student':
        results = QuizResult.query.filter_by(student_id=session['user_id']).all()
        return render_template('history.html', results=results, datetime=datetime)
    else:
        quizzes = Quiz.query.filter_by(teacher_id=session['user_id']).all()
        return render_template('history.html', quizzes=quizzes, datetime=datetime)

@app.route('/view-quiz/<int:quiz_id>')
def view_quiz(quiz_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    quiz = Quiz.query.get_or_404(quiz_id)
    user = User.query.get(session['user_id'])
    
    # Kiểm tra quyền truy cập
    if user.role != 'teacher' or quiz.teacher_id != user.id:
        flash('Bạn không có quyền truy cập bài kiểm tra này!')
        return redirect(url_for('home'))
    
    # Lấy danh sách câu hỏi của bài kiểm tra
    questions = Question.query.filter_by(quiz_id=quiz_id).all()
    
    return render_template('view_quiz.html', quiz=quiz, questions=questions)

@app.route('/quiz/edit/<int:quiz_id>', methods=['GET', 'POST'])
def edit_quiz(quiz_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        flash('Bạn không có quyền truy cập trang này!')
        return redirect(url_for('home'))
    
    # Lấy thông tin bài kiểm tra
    quiz = Quiz.query.get_or_404(quiz_id)
    
    # Kiểm tra quyền truy cập
    if quiz.teacher_id != session['user_id']:
        flash('Bạn không có quyền chỉnh sửa bài kiểm tra này!')
        return redirect(url_for('manage_quizzes'))
    
    if request.method == 'POST':
        try:
            # Cập nhật thông tin cơ bản của bài kiểm tra
            quiz.title = request.form.get('title')
            quiz.start_time = datetime.fromisoformat(request.form.get('start_time').replace('Z', '+00:00'))
            quiz.end_time = datetime.fromisoformat(request.form.get('end_time').replace('Z', '+00:00'))
            quiz.duration = int(request.form.get('duration'))
            max_attempts = request.form.get('max_attempts')
            quiz.max_attempts = int(max_attempts) if max_attempts else None
            
            # Lưu thay đổi thông tin cơ bản
            db.session.commit()
            
            # Lấy dữ liệu từ form
            questions = request.form.getlist('questions[]')
            question_types = request.form.getlist('question_types[]')
            correct_answers = request.form.getlist('correct_answers[]')
            
            # Xóa câu hỏi và câu trả lời cũ
            for old_question in quiz.questions:
                Answer.query.filter_by(question_id=old_question.id).delete()
            Question.query.filter_by(quiz_id=quiz.id).delete()
            db.session.commit()
            
            # Thêm câu hỏi mới
            for i in range(len(questions)):
                question = Question(
                    quiz_id=quiz.id,
                    question_text=questions[i],
                    question_type=question_types[i],
                    correct_answer=correct_answers[i]
                )
                db.session.add(question)
                db.session.flush()  # Để lấy được ID của câu hỏi mới
                
                # Nếu là câu hỏi trắc nghiệm, thêm các lựa chọn
                if question_types[i] == 'multiple_choice':
                    for j in range(4):
                        option = request.form.getlist(f'option{j+1}[]')[i]
                        if option:  # Chỉ thêm option nếu có giá trị
                            answer = Answer(
                                question_id=question.id,
                                answer_text=option
                            )
                            db.session.add(answer)
            
            # Lưu tất cả thay đổi
            db.session.commit()
            flash('Cập nhật bài kiểm tra thành công!', 'success')
            return redirect(url_for('manage_quizzes'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Có lỗi xảy ra khi cập nhật bài kiểm tra: {str(e)}', 'error')
            return redirect(url_for('edit_quiz', quiz_id=quiz_id))
    
    # GET request - hiển thị form chỉnh sửa
    return render_template('edit_quiz.html', quiz=quiz)

@app.route('/delete-quiz/<int:quiz_id>')
def delete_quiz(quiz_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        flash('Bạn không có quyền truy cập trang này!')
        return redirect(url_for('home'))
    
    # Lấy thông tin bài kiểm tra
    quiz = Quiz.query.get_or_404(quiz_id)
    
    # Kiểm tra xem người dùng có phải là chủ sở hữu của bài kiểm tra không
    if quiz.teacher_id != session['user_id']:
        flash('Bạn không có quyền xóa bài kiểm tra này!')
        return redirect(url_for('manage_quizzes'))
    
    try:
        # Xóa các kết quả bài kiểm tra trước
        QuizResult.query.filter_by(quiz_id=quiz_id).delete()
        
        # Lấy danh sách câu hỏi của bài kiểm tra
        questions = Question.query.filter_by(quiz_id=quiz_id).all()
        
        # Xóa các câu trả lời và câu hỏi
        for question in questions:
            Answer.query.filter_by(question_id=question.id).delete()
        
        Question.query.filter_by(quiz_id=quiz_id).delete()
        
        # Xóa bài kiểm tra
        db.session.delete(quiz)
        db.session.commit()
        
        flash('Xóa bài kiểm tra thành công!')
    except Exception as e:
        db.session.rollback()
        flash(f'Có lỗi xảy ra khi xóa bài kiểm tra: {str(e)}')
    
    return redirect(url_for('manage_quizzes'))

@app.route('/search')
def search_quiz():
    keyword = request.args.get('keyword', '')
    if not keyword:
        return redirect(url_for('home'))
    
    # Tìm kiếm tất cả bài kiểm tra
    quizzes = Quiz.query.join(User, Quiz.teacher_id == User.id)\
                       .filter(Quiz.title.ilike(f'%{keyword}%'))\
                       .all()
    
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
        quiz = Quiz.query.filter_by(quiz_code=quiz_code).first()

        if not quiz:
            flash('Mã bài kiểm tra không tồn tại!', 'error')
            return redirect(url_for('join_quiz'))

        # Kiểm tra thời gian
        current_time = datetime.now()  # Sử dụng datetime.now() thay vì utcnow()
        if current_time < quiz.start_time:
            flash('Bài kiểm tra chưa bắt đầu!', 'error')
            return redirect(url_for('join_quiz'))
        
        if current_time > quiz.end_time:
            flash('Bài kiểm tra đã kết thúc!', 'error')
            return redirect(url_for('join_quiz'))

        # Kiểm tra số lần làm bài
        if quiz.max_attempts:
            attempt_count = QuizResult.query.filter_by(
                quiz_id=quiz.id,
                student_id=session['user_id']
            ).count()
            
            if attempt_count >= quiz.max_attempts:
                flash(f'Bạn đã vượt quá số lần làm bài cho phép ({quiz.max_attempts} lần)!', 'error')
                return redirect(url_for('join_quiz'))

        # Chuyển hướng đến trang làm bài với mã bài kiểm tra
        return redirect(url_for('take_quiz', quiz_id=quiz.id, quiz_code=quiz_code))

    return render_template('join_quiz.html')

@app.route('/take_quiz/<int:quiz_id>')
def take_quiz(quiz_id):
    if 'user_id' not in session:
        flash('Vui lòng đăng nhập để làm bài kiểm tra!', 'error')
        return redirect(url_for('login'))

    quiz = Quiz.query.get_or_404(quiz_id)
    
    # Kiểm tra quyền truy cập
    if session['role'] == 'student':
        if not quiz.is_public:
            # Nếu là bài kiểm tra riêng tư, kiểm tra mã
            quiz_code = request.args.get('quiz_code')
            if not quiz_code or quiz_code != quiz.quiz_code:
                flash('Bài kiểm tra này ở chế độ riêng tư. Vui lòng sử dụng mã bài kiểm tra để tham gia!', 'error')
                return redirect(url_for('join_quiz'))

    # Kiểm tra thời gian
    current_time = datetime.now()  # Sử dụng datetime.now() thay vì utcnow()
    if current_time < quiz.start_time:
        flash('Bài kiểm tra chưa bắt đầu!', 'error')
        return redirect(url_for('home'))
    
    if current_time > quiz.end_time:
        flash('Bài kiểm tra đã kết thúc!', 'error')
        return redirect(url_for('home'))

    # Kiểm tra số lần làm bài
    if quiz.max_attempts:
        attempt_count = QuizResult.query.filter_by(
            quiz_id=quiz.id,
            student_id=session['user_id']
        ).count()
        
        if attempt_count >= quiz.max_attempts:
            flash(f'Bạn đã vượt quá số lần làm bài cho phép ({quiz.max_attempts} lần)!', 'error')
            return redirect(url_for('home'))

    # Lấy danh sách câu hỏi của bài kiểm tra
    questions = Question.query.filter_by(quiz_id=quiz_id).all()
    
    # Debug: In ra số lượng câu hỏi
    print(f"Number of questions: {len(questions)}")
    for q in questions:
        print(f"Question {q.id}: {q.question_text}")
        print(f"Type: {q.question_type}")
        if q.question_type == 'multiple_choice':
            print("Answers:")
            for a in q.answers:
                print(f"- {a.answer_text}")

    return render_template('take_quiz.html', quiz=quiz, questions=questions)

@app.route('/quiz/submit/<int:quiz_id>', methods=['POST'])
def submit_quiz(quiz_id):
    if 'user_id' not in session or session['role'] != 'student':
        flash('Bạn không có quyền thực hiện hành động này!')
        return redirect(url_for('home'))
    
    quiz = Quiz.query.get_or_404(quiz_id)
    
    # Kiểm tra thời gian
    now = datetime.now()
    if now > quiz.end_time:
        flash('Bài kiểm tra đã kết thúc!')
        return redirect(url_for('home'))
    
    # Lấy câu trả lời từ form
    answers = {}
    score = 0
    total_questions = len(quiz.questions)
    
    for question in quiz.questions:
        answer = request.form.get(f'answer_{question.id}')
        #answers[question.id] = answer
        print(f"Câu hỏi {question.id} - Câu trả lời nhận được: {answer}")  # Debug
        if answer is None:
            print(f"LỖI: Câu trả lời cho câu hỏi {question.id} không nhận được từ form!")
        # Lưu câu trả lời vào database
        student_answer = StudentAnswer(
            quiz_id=quiz_id,
            student_id=session['user_id'],
            question_id=question.id,
            answer_text=answer or ""
        )
        db.session.add(student_answer)
        
        # Kiểm tra đáp án
        if question.question_type == 'multiple_choice':
            #selected_answer = Answer.query.get(int(answer)) if answer else None
            selected_answer = db.session.get(Answer, int(answer)) if answer else None

            if selected_answer and selected_answer.answer_text.strip() == question.correct_answer.strip():
                score += 1
        else:  # fill_in_blank
            if answer and answer.strip().lower() == question.correct_answer.strip().lower():
                score += 1
    
    # Tính điểm theo thang 10
    final_score = (score / total_questions) * 10 if total_questions > 0 else 0

    
    # Lưu kết quả vào database
    quiz_result = QuizResult(
        quiz_id=quiz_id,
        student_id=session['user_id'],
        score=final_score
    )
    db.session.add(quiz_result)
    db.session.commit()
    #saved_result = QuizResult.query.filter_by(quiz_id=quiz_id, student_id=session['user_id']).first()
    #print(f"Điểm lưu vào DB: {saved_result.score if saved_result else 'Không tìm thấy'}")

    

    return redirect(url_for('results_page', quiz_id=quiz_id))
    
   
@app.route('/results/<int:quiz_id>')
def results_page(quiz_id):
    if 'user_id' not in session:
        flash('Bạn cần đăng nhập để xem kết quả!')
        return redirect(url_for('login'))

    quiz = Quiz.query.get_or_404(quiz_id)

    # Lấy kết quả của user
    result = QuizResult.query.filter_by(
        quiz_id=quiz_id, 
        student_id=session['user_id']
    ).order_by(QuizResult.id.desc()).first()
    
    if not result:
        flash('Không tìm thấy kết quả bài kiểm tra của bạn.')
        return redirect(url_for('home'))

    # Lấy danh sách câu hỏi
    questions = Question.query.filter_by(quiz_id=quiz_id).all()

    # Lấy câu trả lời của học sinh
    student_answers = StudentAnswer.query.filter_by(
        quiz_id=quiz_id, 
        student_id=session["user_id"]
    ).all()
    
    # Chuyển đổi dữ liệu thành dictionary {question_id: answer_text}
    student_answers_dict = {}
    for answer in student_answers:
        question = Question.query.get(answer.question_id)
        if question:  # Kiểm tra xem câu hỏi có tồn tại không
            if question.question_type == 'multiple_choice':
                # Lấy text của câu trả lời từ bảng Answer
                selected_answer = Answer.query.get(int(answer.answer_text))
                student_answers_dict[answer.question_id] = selected_answer.answer_text if selected_answer else "Chưa trả lời"
            else:
                # Với câu điền vào chỗ trống, lấy trực tiếp answer_text
                student_answers_dict[answer.question_id] = answer.answer_text

    # Chuẩn bị dữ liệu cho template    
    results = []
    for question in questions:
        user_answer = student_answers_dict.get(question.id, "Chưa trả lời")
        is_correct = False
        
        if question.question_type == 'multiple_choice':
            is_correct = user_answer.strip() == question.correct_answer.strip() if user_answer != "Chưa trả lời" else False
        else:  # fill_in_blank
            is_correct = user_answer.strip().lower() == question.correct_answer.strip().lower() if user_answer != "Chưa trả lời" else False
            
        results.append((question.question_text, user_answer, question.correct_answer, is_correct, question.question_type))

    return render_template(
        'results_after.html', 
        quiz=quiz, 
        score=result.score, 
        total_questions=len(questions),
        results=results
    )


@app.route('/quiz/<int:quiz_id>/results')
def quiz_results(quiz_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        flash('Bạn không có quyền truy cập trang này!')
        return redirect(url_for('home'))
    
    # Lấy thông tin bài kiểm tra
    quiz = Quiz.query.get_or_404(quiz_id)
    
    # Kiểm tra quyền truy cập
    if quiz.teacher_id != session['user_id']:
        flash('Bạn không có quyền xem kết quả bài kiểm tra này!')
        return redirect(url_for('manage_quizzes'))
    
    # Lấy danh sách kết quả của học sinh
    results = QuizResult.query.filter_by(quiz_id=quiz_id)\
        .join(User, QuizResult.student_id == User.id)\
        .order_by(QuizResult.score.desc())\
        .all()
    
    return render_template('quiz_results.html', quiz=quiz, results=results)

@app.route('/quiz/<int:quiz_id>/students')
def quiz_students(quiz_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        flash('Bạn không có quyền truy cập trang này!')
        return redirect(url_for('home'))
    
    quiz = Quiz.query.get_or_404(quiz_id)
    
    # Kiểm tra quyền truy cập
    if quiz.teacher_id != session['user_id']:
        flash('Bạn không có quyền xem kết quả bài kiểm tra này!')
        return redirect(url_for('history'))
    
    # Lấy danh sách kết quả của học sinh
    results = QuizResult.query.filter_by(quiz_id=quiz_id)\
        .join(User, QuizResult.student_id == User.id)\
        .order_by(QuizResult.score.desc())\
        .all()
    
    return render_template('quiz_students.html', quiz=quiz, results=results)

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    user_profile = UserProfile.query.filter_by(user_id=user.id).first()
    
    if not user_profile:
        user_profile = UserProfile(user_id=user.id)
        db.session.add(user_profile)
        db.session.commit()
    
    return render_template('profile.html', user=user, profile=user_profile)

@app.route('/profile/edit', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    profile = UserProfile.query.filter_by(user_id=user.id).first()
    
    if request.method == 'POST':
        # Cập nhật thông tin profile
        profile.full_name = request.form.get('full_name')
        profile.phone = request.form.get('phone')
        profile.address = request.form.get('address')
        profile.bio = request.form.get('bio')
        
        db.session.commit()
        flash('Cập nhật thông tin thành công!')
        return redirect(url_for('profile'))
    
    return render_template('edit_profile.html', user=user, profile=profile)

@app.route('/settings')
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    return render_template('settings.html', user=user)

@app.route('/settings/password', methods=['POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not check_password_hash(user.password, current_password):
        flash('Mật khẩu hiện tại không đúng!')
        return redirect(url_for('settings'))
    
    if new_password != confirm_password:
        flash('Mật khẩu mới không khớp!')
        return redirect(url_for('settings'))
    
    user.password = generate_password_hash(new_password)
    db.session.commit()
    flash('Đổi mật khẩu thành công!')
    return redirect(url_for('settings'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Generate a unique token
            token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
            expires_at = datetime.utcnow() + timedelta(hours=1)  # Token expires in 1 hour
            
            # Create password reset token
            reset_token = PasswordResetToken(
                user_id=user.id,
                token=token,
                expires_at=expires_at
            )
            db.session.add(reset_token)
            db.session.commit()
            
            # Redirect directly to reset password page
            return redirect(url_for('reset_password', token=token))
        
        flash('Email không tồn tại trong hệ thống.', 'error')
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    reset_token = PasswordResetToken.query.filter_by(token=token, used=False).first()
    
    if not reset_token:
        flash('Link đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.', 'error')
        return redirect(url_for('forgot_password'))
    
    if datetime.utcnow() > reset_token.expires_at:
        flash('Link đặt lại mật khẩu đã hết hạn.', 'error')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Mật khẩu xác nhận không khớp.', 'error')
            return render_template('reset_password.html')
        
        # Update user's password
        reset_token.user.password = generate_password_hash(password)
        reset_token.used = True
        db.session.commit()
        
        flash('Mật khẩu đã được đặt lại thành công. Vui lòng đăng nhập.', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html')

@app.route('/quiz/<int:quiz_id>/toggle-visibility')
def toggle_quiz_visibility(quiz_id):
    if 'user_id' not in session or session['role'] != 'teacher':
        flash('Bạn không có quyền thực hiện hành động này!')
        return redirect(url_for('home'))
    
    quiz = Quiz.query.get_or_404(quiz_id)
    
    # Kiểm tra quyền truy cập
    if quiz.teacher_id != session['user_id']:
        flash('Bạn không có quyền thay đổi trạng thái bài kiểm tra này!')
        return redirect(url_for('manage_quizzes'))
    
    # Đảo ngược trạng thái công khai
    quiz.is_public = not quiz.is_public
    db.session.commit()
    
    status = "công khai" if quiz.is_public else "riêng tư"
    flash(f'Trạng thái bài kiểm tra đã được thay đổi thành {status}!')
    return redirect(url_for('manage_quizzes'))

@app.route('/login/google')
def login_google():
    return render_template('login_google.html')

@app.route('/login/google/callback', methods=['POST'])
def google_callback():
    try:
        # Lấy token ID từ request
        id_token = request.json.get('idToken')
        
        if not id_token:
            return jsonify({'success': False, 'error': 'Không tìm thấy token'}), 400
            
        # Xác thực token với Firebase
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        email = decoded_token['email']
        name = decoded_token.get('name', email.split('@')[0])
        
        # Kiểm tra xem người dùng đã tồn tại chưa
        user = User.query.filter_by(email=email).first()
        if not user:
            # Tạo người dùng mới
            user = User(
                email=email,
                username=name,
                password=generate_password_hash(str(random.getrandbits(128))),  # Tạo mật khẩu ngẫu nhiên
                role='student'  # Mặc định là student
            )
            db.session.add(user)
            db.session.commit()
            
            # Tạo profile cho người dùng mới
            profile = UserProfile(user_id=user.id)
            db.session.add(profile)
            db.session.commit()

        # Đăng nhập người dùng
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        return jsonify({'success': True, 'redirect': url_for('home')})
        
    except Exception as e:
        print(f"Error in google_callback: {str(e)}")  # Log lỗi
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/register/google/callback', methods=['POST'])
def register_google_callback():
    try:
        data = request.get_json()
        id_token = data.get('idToken')
        role = data.get('role')

        if not id_token or not role:
            return jsonify({'success': False, 'error': 'Thiếu thông tin cần thiết'}), 400

        # Xác thực token với Firebase
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        email = decoded_token['email']
        name = decoded_token.get('name', email.split('@')[0])

        # Kiểm tra xem email đã tồn tại chưa
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({'success': False, 'error': 'Email đã được sử dụng'}), 400

        # Tạo username từ email nếu không có name
        username = name
        # Nếu username đã tồn tại, thêm số ngẫu nhiên
        while User.query.filter_by(username=username).first():
            username = f"{name}{random.randint(1000, 9999)}"

        # Tạo mật khẩu ngẫu nhiên cho tài khoản
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))

        # Tạo user mới
        new_user = User(
            email=email,
            username=username,
            password=generate_password_hash(password),
            role=role
        )

        db.session.add(new_user)
        db.session.flush()  # Lấy ID của user mới

        # Tạo profile cho user
        profile = UserProfile(
            user_id=new_user.id,
            full_name=name
        )
        db.session.add(profile)
        db.session.commit()

        # Đăng nhập người dùng
        session['user_id'] = new_user.id
        session['username'] = new_user.username
        session['role'] = new_user.role

        # Chuyển hướng dựa trên role
        redirect_url = url_for('teacher_dashboard') if role == 'teacher' else url_for('home')

        return jsonify({
            'success': True,
            'redirect': redirect_url
        })

    except auth.InvalidIdTokenError:
        return jsonify({'success': False, 'error': 'Token không hợp lệ'}), 401
    except auth.ExpiredIdTokenError:
        return jsonify({'success': False, 'error': 'Token đã hết hạn'}), 401
    except auth.RevokedIdTokenError:
        return jsonify({'success': False, 'error': 'Token đã bị thu hồi'}), 401
    except Exception as e:
        print(f"Error in register_google_callback: {str(e)}")
        return jsonify({'success': False, 'error': 'Có lỗi xảy ra khi đăng ký'}), 500

def main():
    with app.app_context():
        # Chỉ tạo bảng nếu chưa tồn tại
        db.create_all()
    app.run(debug=True)


if __name__ == "__main__":
    main() 