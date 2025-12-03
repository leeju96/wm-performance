from flask import Flask, request, redirect, render_template, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import date, timedelta
from sqlalchemy import func

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///performance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# -------------------
# 로그인 필터
# -------------------
@app.before_request
def require_login():
    allowed = ['/login', '/static/', '/manifest.json', '/service-worker.js']

    if any(request.path.startswith(a) for a in allowed):
        return None

    if request.endpoint == "static":
        return None

    if not request.cookies.get("access"):
        return redirect("/login")


@app.route("/login")
def login_page():
    return render_template("login.html")

# -------------------
# DB 모델
# -------------------
class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(50))
    note = db.Column(db.String(200))


class PerformanceLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    log_date = db.Column(db.Date, nullable=False, default=date.today)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=False)
    sponsor_amount = db.Column(db.Integer, default=0)
    count = db.Column(db.Integer, default=0)
    member = db.relationship('Member', backref=db.backref('logs', lazy=True))


with app.app_context():
    db.create_all()


# -------------------
# 메인 대시보드
# -------------------
@app.route('/')
def dashboard():
    today = date.today()

    month_param = request.args.get('month')
    start_date_param = request.args.get('start_date')
    end_date_param = request.args.get('end_date')

    start_date_value = start_date_param or ""
    end_date_value = end_date_param or ""

    if month_param:
        try:
            year, month = map(int, month_param.split('-'))
        except:
            year = today.year
            month = today.month
    else:
        year = today.year
        month = today.month

    month_start = date(year, month, 1)
    month_end = date(year+1, 1, 1) if month == 12 else date(year, month+1, 1)

    if start_date_param or end_date_param:
        if start_date_param:
            y, m, d = map(int, start_date_param.split('-'))
            date_start = date(y, m, d)
        else:
            date_start = date(2000, 1, 1)

        if end_date_param:
            y, m, d = map(int, end_date_param.split('-'))
            date_end = date(y, m, d) + timedelta(days=1)
        else:
            date_end = date(2100, 1, 1)
    else:
        date_start = month_start
        date_end = month_end

    members = Member.query.order_by(Member.id.asc()).all()

    logs_query = PerformanceLog.query.filter(
        PerformanceLog.log_date >= date_start,
        PerformanceLog.log_date < date_end
    )

    logs = logs_query.order_by(PerformanceLog.log_date.desc()).all()

    my_member = Member.query.order_by(Member.id.asc()).first()
    if my_member:
        my_logs = logs_query.filter(
            PerformanceLog.member_id == my_member.id
        ).order_by(PerformanceLog.log_date.desc()).all()
    else:
        my_logs = []

    chart_labels = []
    chart_amounts = []
    chart_counts = []

    if members:
        rows = (
            db.session.query(
                Member.name,
                func.coalesce(func.sum(PerformanceLog.sponsor_amount), 0),
                func.coalesce(func.sum(PerformanceLog.count), 0)
            )
            .join(PerformanceLog, Member.id == PerformanceLog.member_id, isouter=True)
            .filter(
                PerformanceLog.log_date >= date_start,
                PerformanceLog.log_date < date_end
            )
            .group_by(Member.id)
            .order_by(Member.id.asc())
            .all()
        )

        for name, amount_sum, count_sum in rows:
            chart_labels.append(name)
            chart_amounts.append(int(amount_sum or 0))
            chart_counts.append(int(count_sum or 0))

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
        end_date_value=end_date_value
    )


# -------------------
# 팀원, 로그 CRUD
# -------------------
@app.route('/member/add', methods=['POST'])
def add_member():
    name = request.form.get('name')
    role = request.form.get('role')
    note = request.form.get('note')
    if name:
        db.session.add(Member(name=name, role=role, note=note))
        db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/log/add', methods=['POST'])
def add_log():
    member_id = request.form.get('member_id')
    log_date = request.form.get('log_date')
    sponsor_amount = int(request.form.get('sponsor_amount') or 0)
    count = int(request.form.get('count') or 0)

    if member_id:
        if log_date:
            y, m, d = map(int, log_date.split('-'))
            d_obj = date(y, m, d)
        else:
            d_obj = date.today()

        db.session.add(PerformanceLog(
            member_id=int(member_id),
            log_date=d_obj,
            sponsor_amount=sponsor_amount,
            count=count
        ))
        db.session.commit()

    return redirect(url_for('dashboard'))


@app.route('/log/delete/<int:log_id>', methods=['POST'])
def delete_log(log_id):
    log = PerformanceLog.query.get_or_404(log_id)
    db.session.delete(log)
    db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/member/<int:member_id>')
def member_detail(member_id):
    today = date.today()

    member = Member.query.get_or_404(member_id)

    start_date_param = request.args.get('start_date')
    end_date_param = request.args.get('end_date')

    start_date_value = start_date_param or ""
    end_date_value = end_date_param or ""

    if start_date_param or end_date_param:
        if start_date_param:
            y, m, d = map(int, start_date_param.split('-'))
            date_start = date(y, m, d)
        else:
            date_start = date(2000, 1, 1)

        if end_date_param:
            y, m, d = map(int, end_date_param.split('-'))
            date_end = date(y, m, d) + timedelta(days=1)
        else:
            date_end = date(2100, 1, 1)
    else:
        date_start = date(2000, 1, 1)
        date_end = date(2100, 1, 1)

    logs = (
        PerformanceLog.query
        .filter_by(member_id=member_id)
        .filter(PerformanceLog.log_date >= date_start)
        .filter(PerformanceLog.log_date < date_end)
        .order_by(PerformanceLog.log_date.desc())
        .all()
    )

    chart_labels = [l.log_date.strftime('%Y-%m-%d') for l in logs]
    chart_amounts = [l.sponsor_amount for l in logs]
    chart_counts = [l.count for l in logs]

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


@app.route('/member/<int:member_id>/update', methods=['POST'])
def update_member(member_id):
    member = Member.query.get_or_404(member_id)
    member.name = request.form.get('name')
    member.role = request.form.get('role')
    member.note = request.form.get('note')
    db.session.commit()
    return redirect(url_for('member_detail', member_id=member_id))


@app.route('/member/<int:member_id>/delete', methods=['POST'])
def delete_member(member_id):
    PerformanceLog.query.filter_by(member_id=member_id).delete()
    member = Member.query.get_or_404(member_id)
    db.session.delete(member)
    db.session.commit()
    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    app.run(debug=True)
# 공지사항
class Notice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.Date, default=date.today)

# Tip 게시판
class Tip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.Date, default=date.today)
@app.route("/notice")
def notice_list():
    notices = Notice.query.order_by(Notice.id.desc()).all()
    return render_template("notice_list.html", notices=notices)

@app.route("/notice/write", methods=["GET", "POST"])
def notice_write():
    if request.method == "POST":
        title = request.form["title"]
        content = request.form["content"]
        db.session.add(Notice(title=title, content=content))
        db.session.commit()
        return redirect("/notice")
    return render_template("notice_write.html")
@app.route("/tip")
def tip_list():
    tips = Tip.query.order_by(Tip.id.desc()).all()
    return render_template("tip_list.html", tips=tips)

@app.route("/tip/write", methods=["GET", "POST"])
def tip_write():
    if request.method == "POST":
        title = request.form["title"]
        content = request.form["content"]
        db.session.add(Tip(title=title, content=content))
        db.session.commit()
        return redirect("/tip")
    return render_template("tip_write.html")
