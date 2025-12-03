from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import date, timedelta
from sqlalchemy import func

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///performance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 팀원 테이블
class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(50))
    note = db.Column(db.String(200))

# 성과 로그 테이블
class PerformanceLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    log_date = db.Column(db.Date, nullable=False, default=date.today)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=False)
    sponsor_amount = db.Column(db.Integer, default=0)  # 후원금액
    count = db.Column(db.Integer, default=0)           # 건수
    member = db.relationship('Member', backref=db.backref('logs', lazy=True))

# DB 생성
with app.app_context():
    db.create_all()

@app.route('/')
def dashboard():
    today = date.today()

    # 쿼리스트링으로 들어오는 값들
    month_param = request.args.get('month')        # 예: 2025-12
    start_date_param = request.args.get('start_date')  # 예: 2025-12-01
    end_date_param = request.args.get('end_date')      # 예: 2025-12-31

    # input에 다시 채워줄 값 (없으면 빈 문자열)
    start_date_value = start_date_param or ""
    end_date_value = end_date_param or ""

    # 기본 월(오늘 기준)
    if month_param:
        try:
            year, month = map(int, month_param.split('-'))
        except ValueError:
            year = today.year
            month = today.month
    else:
        year = today.year
        month = today.month

    # 해당 월의 시작일, 다음 달 1일 (끝 경계)
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1)
    else:
        month_end = date(year, month + 1, 1)

    # 날짜 범위 계산
    if start_date_param or end_date_param:
        # 기간 검색 모드
        if start_date_param:
            y, m, d = map(int, start_date_param.split('-'))
            date_start = date(y, m, d)
        else:
            date_start = date(2000, 1, 1)  # 아주 예전 날짜

        if end_date_param:
            y, m, d = map(int, end_date_param.split('-'))
            end_inclusive = date(y, m, d)
            date_end = end_inclusive + timedelta(days=1)  # 사용자가 입력한 날짜까지 포함
        else:
            date_end = date(2100, 1, 1)  # 아주 먼 미래
    else:
        # 월별 보기 모드
        date_start = month_start
        date_end = month_end

    members = Member.query.order_by(Member.id.asc()).all()

    # 선택된 기간/월에 해당하는 로그만 조회
    logs_query = PerformanceLog.query.filter(
        PerformanceLog.log_date >= date_start,
        PerformanceLog.log_date < date_end,
    )

    logs = logs_query.order_by(PerformanceLog.log_date.desc()).all()

    # "나의 성과기록" 기준: 가장 먼저 등록한 팀원
    my_member = Member.query.order_by(Member.id.asc()).first()
    if my_member:
        my_logs = (
            logs_query
            .filter(PerformanceLog.member_id == my_member.id)
            .order_by(PerformanceLog.log_date.desc())
            .all()
        )
    else:
        my_logs = []

    # 성과표(그래프용 데이터) - 선택된 기간/월 기준 팀원별 금액/건수 합계
    chart_labels = []
    chart_amounts = []
    chart_counts = []

    if members:
        rows = (
            db.session.query(
                Member.name,
                func.coalesce(func.sum(PerformanceLog.sponsor_amount), 0),
                func.coalesce(func.sum(PerformanceLog.count), 0),
            )
            .join(PerformanceLog, Member.id == PerformanceLog.member_id, isouter=True)
            .filter(
                PerformanceLog.log_date >= date_start,
                PerformanceLog.log_date < date_end,
            )
            .group_by(Member.id)
            .order_by(Member.id.asc())
            .all()
        )

        for name, amount_sum, count_sum in rows:
            chart_labels.append(name)
            chart_amounts.append(int(amount_sum or 0))
            chart_counts.append(int(count_sum or 0))

    # input type="month"에 넣어줄 값 (예: 2025-12)
    current_month = f"{year:04d}-{month:02d}"

    return render_template(
        'dashboard.html',
        today=today,
        members=members,
        logs=logs,
        my_logs=my_logs,
        my_member=my_member,
        chart_labels=chart_labels,
        chart_amounts=chart_amounts,
        chart_counts=chart_counts,
        current_month=current_month,
        start_date_value=start_date_value,
        end_date_value=end_date_value,
    )


# 팀원 추가
@app.route('/member/add', methods=['POST'])
def add_member():
    name = request.form.get('name')
    role = request.form.get('role')
    note = request.form.get('note')
    if name:
        m = Member(name=name, role=role, note=note)
        db.session.add(m)
        db.session.commit()
    return redirect(url_for('dashboard'))

# 성과 로그 추가
@app.route('/log/add', methods=['POST'])
def add_log():
    member_id = request.form.get('member_id')
    log_date = request.form.get('log_date')
    sponsor_amount = request.form.get('sponsor_amount') or 0
    count = request.form.get('count') or 0

    if member_id:
        if log_date:
            y, m, d = map(int, log_date.split('-'))
            d_obj = date(y, m, d)
        else:
            d_obj = date.today()

        log = PerformanceLog(
            member_id=int(member_id),
            log_date=d_obj,
            sponsor_amount=int(sponsor_amount),
            count=int(count),
        )
        db.session.add(log)
        db.session.commit()

    return redirect(url_for('dashboard'))

# 성과 로그 삭제
@app.route('/log/delete/<int:log_id>', methods=['POST'])
def delete_log(log_id):
    log = PerformanceLog.query.get_or_404(log_id)
    db.session.delete(log)
    db.session.commit()
    return redirect(url_for('dashboard'))

# =========================
# 팀원 상세 페이지
# =========================

@app.route('/member/<int:member_id>')
def member_detail(member_id):
    today = date.today()

    member = Member.query.get_or_404(member_id)

    # 쿼리 파라미터 (기간 검색 재사용)
    start_date_param = request.args.get('start_date')
    end_date_param = request.args.get('end_date')

    start_date_value = start_date_param or ""
    end_date_value = end_date_param or ""

    # 기간 계산
    if start_date_param or end_date_param:
        # 특정 기간 검색
        if start_date_param:
            y, m, d = map(int, start_date_param.split('-'))
            date_start = date(y, m, d)
        else:
            date_start = date(2000, 1, 1)

        if end_date_param:
            y, m, d = map(int, end_date_param.split('-'))
            end_inclusive = date(y, m, d)
            date_end = end_inclusive + timedelta(days=1)
        else:
            date_end = date(2100, 1, 1)
    else:
        # 기본값: 그 팀원의 모든 기록
        date_start = date(2000, 1, 1)
        date_end = date(2100, 1, 1)

    # 해당 팀원 로그만 가져오기
    logs = (
        PerformanceLog.query
        .filter(PerformanceLog.member_id == member_id)
        .filter(PerformanceLog.log_date >= date_start)
        .filter(PerformanceLog.log_date < date_end)
        .order_by(PerformanceLog.log_date.desc())
        .all()
    )

    # 그래프용 데이터
    chart_labels = []
    chart_amounts = []
    chart_counts = []

    for log in logs:
        chart_labels.append(log.log_date.strftime('%Y-%m-%d'))
        chart_amounts.append(log.sponsor_amount)
        chart_counts.append(log.count)

    return render_template(
        'member_detail.html',
        member=member,
        logs=logs,
        today=today,
        start_date_value=start_date_value,
        end_date_value=end_date_value,
        chart_labels=chart_labels,
        chart_amounts=chart_amounts,
        chart_counts=chart_counts
    )

# 팀원 정보 수정
@app.route('/member/<int:member_id>/update', methods=['POST'])
def update_member(member_id):
    member = Member.query.get_or_404(member_id)

    name = request.form.get('name')
    role = request.form.get('role')
    note = request.form.get('note')

    if name:
        member.name = name
    member.role = role
    member.note = note

    db.session.commit()
    return redirect(url_for('member_detail', member_id=member.id))

# 팀원 삭제 (해당 팀원의 성과 기록도 함께 삭제)
@app.route('/member/<int:member_id>/delete', methods=['POST'])
def delete_member(member_id):
    member = Member.query.get_or_404(member_id)

    # 먼저 해당 팀원 로그 삭제
    PerformanceLog.query.filter_by(member_id=member.id).delete()

    # 팀원 삭제
    db.session.delete(member)
    db.session.commit()

    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    app.run(debug=True)
