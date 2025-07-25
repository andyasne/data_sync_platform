from flask import Blueprint, render_template, request, redirect, url_for, session, current_app
from .decorators import basic_auth_required

auth_bp = Blueprint('auth', __name__, template_folder='../../templates/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if (request.form['username'] == current_app.config['ADMIN_USERNAME'] and
                request.form['password'] == current_app.config['ADMIN_PASSWORD']):
            session['logged_in'] = True
            return redirect(url_for('transfer.transfer_home'))
    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
