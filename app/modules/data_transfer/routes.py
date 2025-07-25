from flask import Blueprint, render_template, request, redirect, url_for, flash
from .tasks import sync_table_task
from ...modules.auth.decorators import basic_auth_required

transfer_bp = Blueprint('transfer', __name__, template_folder='../../templates/data_transfer')

@transfer_bp.route('/')
@basic_auth_required
def transfer_home():
    return render_template('data_transfer/index.html')

@transfer_bp.route('/start', methods=['POST'])
@basic_auth_required
def start_sync():
    tables = [t.strip() for t in request.form['tables'].split(',')]
    modified_col = request.form.get('modified_col', 'server_modified_date')
    for table in tables:
        sync_table_task.delay(table, modified_col)
    flash('Sync tasks queued')
    return redirect(url_for('transfer.transfer_home'))
