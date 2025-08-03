# 文件: app.py (最终修复版 - 增加日期记忆开关)
import json
import uuid
import csv
import io
import os
import logging
import sys
import traceback
from datetime import datetime, date
from collections import defaultdict
from flask import Flask, render_template, request, redirect, url_for, flash, Response, send_from_directory, session
from markupsafe import escape

_env_initialized = False
IS_ANDROID = False
DATA_DIR = None
DATA_FILE = None
log_capture_string = io.StringIO()
 
def _initialize_app_env():
    global _env_initialized, IS_ANDROID, DATA_DIR, DATA_FILE
    if _env_initialized:
        return
 
    try:
        from com.chaquo.python import android
        context = android.get_application()
        if context is None:
            raise ValueError("Android context is null.")
        BASE_DIR = context.getFilesDir().toString()
        IS_ANDROID = True
    except Exception:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        IS_ANDROID = False
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
 
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    formatter = logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s')
 
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    string_io_handler = logging.StreamHandler(log_capture_string)
    string_io_handler.setFormatter(formatter)
    root_logger.addHandler(string_io_handler)

    OLD_DATA_DIR = os.path.join(BASE_DIR, 'data')
    NEW_DATA_DIR = os.path.join(BASE_DIR, 'user_data')

    if IS_ANDROID and os.path.isdir(OLD_DATA_DIR) and not os.path.isdir(NEW_DATA_DIR):
        try:
            logging.info(f"DIAGNOSTIC: Found old data at '{OLD_DATA_DIR}'. Migrating to '{NEW_DATA_DIR}'.")
            os.rename(OLD_DATA_DIR, NEW_DATA_DIR)
            logging.info("DIAGNOSTIC: Data migration successful.")
        except OSError as e:
            logging.critical(f"FATAL: Failed to migrate data from old directory: {e}", exc_info=True)

    DATA_DIR = NEW_DATA_DIR
    DATA_FILE = os.path.join(DATA_DIR, 'data.json')
    os.makedirs(DATA_DIR, exist_ok=True)

    _env_initialized = True

app = Flask(__name__)
app.secret_key = os.urandom(24)

def is_mobile():
    _initialize_app_env()
    user_agent = request.headers.get('User-Agent', '').lower()
    if IS_ANDROID:
        return True
    return any(k in user_agent for k in ['mobi', 'android', 'iphone', 'ipod', 'ipad', 'windows phone', 'blackberry'])

@app.context_processor
def inject_global_vars():
    """向所有模板注入全局变量"""
    _initialize_app_env()
    data = load_data()
    
    if data.get('settings', {}).get('keep_last_date', False) and 'last_used_date' in session:
        date_for_new_record = session['last_used_date']
    else:
        date_for_new_record = datetime.now().strftime('%Y-%m-%d')

    return {
        'current_year': datetime.now().year,
        'today_for_form': datetime.now().strftime('%Y-%m-%d'),
        'date_for_new_record': date_for_new_record, # 新增变量
        'default_expense_categories': data['categories']['expense'],
        'default_income_categories': data['categories']['income']
    }
 
def save_data(data):
    _initialize_app_env()
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_data():
    _initialize_app_env()
    
    initial_data = {
        "records": [],
        "categories": {
            "expense": ["交通"],
            "income": ["工资"]
        },
        "budgets": {},
        "settings": {
            "keep_last_date": False
        }
    }

    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            data.setdefault('records', [])
            data.setdefault('categories', {}).setdefault('expense', [])
            data.setdefault('categories', {}).setdefault('income', [])
            data.setdefault('budgets', {})
            data.setdefault('settings', {}).setdefault('keep_last_date', False)
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        save_data(initial_data)
        return initial_data

# --- 路由和视图函数 ---

@app.route('/')
def index():
    data = load_data()
    all_records = data['records']
    now = datetime.now()
 
    # 【核心修改 1/2】: 智能判断月份来源
    # 优先从移动端获取 'selected_month'
    # 如果没有，则尝试从桌面端获取 'selected_date' 并中提取月份
    # 如果都没有，则使用当前月份
    selected_month_from_mobile = request.args.get('selected_month')
    selected_date_from_desktop = request.args.get('selected_date')
 
    if selected_month_from_mobile:
        # 来源是移动端月份选择器
        target_month_str = selected_month_from_mobile
        # 为了兼容桌面版逻辑，我们从月份推算出一个日期字符串
        selected_date_str = f"{target_month_str}-01" 
    elif selected_date_from_desktop:
        # 来源是桌面端日期选择器
        selected_date_str = selected_date_from_desktop
        try:
            target_month_str = datetime.strptime(selected_date_str, '%Y-%m-%d').strftime('%Y-%m')
        except ValueError: # 如果日期格式错误，回退
            selected_date_str = now.strftime('%Y-%m-%d')
            target_month_str = now.strftime('%Y-%m')
    else:
        # 没有任何参数，使用今天和本月
        selected_date_str = now.strftime('%Y-%m-%d')
        target_month_str = now.strftime('%Y-%m')
    
    # 所有月度计算都基于最终确定的 target_month_str
    monthly_records = [r for r in all_records if r['date'].startswith(target_month_str)]
    monthly_income_total = sum(r['amount'] for r in monthly_records if r['type'] == 'income')
    monthly_expense_total = sum(r['amount'] for r in monthly_records if r['type'] == 'expense')
    monthly_savings = monthly_income_total - monthly_expense_total
    
    # 预算计算逻辑不变，它会自动使用正确的 monthly_records
    budgets = defaultdict(float, data.get('budgets', {}))
    monthly_expense_by_category = defaultdict(float)
    for record in monthly_records:
        if record['type'] == 'expense':
            monthly_expense_by_category[record['category']] += record['amount']
    
    total_budget = sum(budgets.values())
    budget_progress = {}
    for category, budget_amount in budgets.items():
        if budget_amount > 0:
            spent_amount = monthly_expense_by_category.get(category, 0)
            progress_percent = (spent_amount / budget_amount) * 100 if budget_amount > 0 else 0
            budget_progress[category] = { "spent": spent_amount, "budget": budget_amount, "progress": min(progress_percent, 100), "overspent": spent_amount > budget_amount }
    
    overall_budget_progress = (monthly_expense_total / total_budget) * 100 if total_budget > 0 else 0
 
    if is_mobile():
        # 【核心修改 2/2】: 将 target_month_str 传递给移动端模板
        return render_template('mobile/index.html',
                               monthly_savings=monthly_savings,
                               monthly_income_total=monthly_income_total,
                               monthly_expense_total=monthly_expense_total,
                               total_budget=total_budget,
                               overall_budget_progress=overall_budget_progress,
                               budget_progress=budget_progress,
                               selected_month=target_month_str) # <-- 新增变量
    else: 
        # 桌面端的日度计算（基于 selected_date_str）
        daily_income = sum(r['amount'] for r in all_records if r['date'] == selected_date_str and r['type'] == 'income')
        daily_expense = sum(r['amount'] for r in all_records if r['date'] == selected_date_str and r['type'] == 'expense')
        
        return render_template('index.html',
                               daily_income=daily_income, 
                               daily_expense=daily_expense,
                               monthly_income_total=monthly_income_total, 
                               monthly_expense_total=monthly_expense_total,
                               monthly_savings=monthly_savings,
                               total_budget=total_budget,
                               overall_budget_progress=overall_budget_progress,
                               budget_progress=budget_progress,
                               selected_date=selected_date_str) # 桌面版保持不变
 
@app.route('/add')
def add_form():
    """仅移动端使用的路由，用于显示添加记录的表单页。"""
    if is_mobile():
        return render_template('mobile/edit_record.html', record=None)
    else:
        return redirect(url_for('index'))
 
@app.route('/add_record', methods=['POST'])
def add_record():
    data = load_data()
    try:
        amount_float = float(request.form.get('amount'))
    except (ValueError, TypeError):
        flash('金额必须是有效的数字！', 'danger')
        return redirect(url_for('add_form') if is_mobile() else url_for('index'))
 
    category = ""
    if is_mobile():
        selected_category = request.form.get('category')
        if selected_category == '--custom--':
            category = request.form.get('custom_category_input', '').strip()
            if not category:
                flash('选择了自定义类别，但未填写名称！', 'danger')
                return redirect(url_for('add_form'))
        else:
            category = selected_category
    else:
        category = request.form.get('category', '').strip()
 
    new_record = {
        'id': str(uuid.uuid4()),
        'type': request.form.get('type'),
        'category': category,
        'amount': amount_float,
        'description': request.form.get('description', '').strip(),
        'date': request.form.get('date') or datetime.now().strftime('%Y-%m-%d')
    }
    
    if not all([new_record['type'], new_record['category'], new_record['amount'] > 0]):
        flash('类型、类别和金额都是必填项!', 'danger')
        return redirect(url_for('add_form') if is_mobile() else url_for('index'))
 
    data['records'].append(new_record)
    save_data(data)
 
    session['last_used_date'] = new_record['date']
    
    flash('记录添加成功！', 'success')
    
    if is_mobile():
        return redirect(url_for('records', selected_date=new_record['date']))
    else:
        # 【核心修改】: 重定向到 index 并附上日期参数
        return redirect(url_for('index', selected_date=new_record['date']))

@app.route('/edit_record/<record_id>', methods=['GET', 'POST'])
def edit_record(record_id):
    data = load_data()
    original_record = next((r for r in data['records'] if r['id'] == record_id), None)
    if not original_record:
        flash('未找到该记录！', 'danger')
        return redirect(url_for('records'))

    # ✅ 获取该日该类别所有记录
    same_category_records = [
        r for r in data['records']
        if r['date'] == original_record['date']
        and r['type'] == original_record['type']
        and r['category'] == original_record['category']
    ]

    # ✅ 计算合并后的金额和备注
    merged_amount = sum(r['amount'] for r in same_category_records)
    merged_description = ', '.join(
        r['description'].strip()
        for r in same_category_records
        if r['description'] and r['description'].strip()
    )

    if request.method == 'POST':
        try:
            amount = float(request.form.get('amount'))
        except:
            flash('金额无效', 'danger')
            return redirect(url_for('edit_record', record_id=record_id))

        category = request.form.get('category')
        new_type = request.form.get('type')
        new_date = request.form.get('date')
        description = request.form.get('description', '').strip()

        # ✅ 删除该日该类别所有记录
        data['records'] = [
            r for r in data['records'] if not (
                r['date'] == original_record['date'] and
                r['type'] == original_record['type'] and
                r['category'] == original_record['category']
            )
        ]

        # ✅ 新增一条合并后的记录
        new_record = {
            'id': str(uuid.uuid4()),
            'type': new_type,
            'category': category,
            'amount': amount,
            'description': description,
            'date': new_date
        }
        data['records'].append(new_record)
        save_data(data)

        flash('记录已更新（已合并）', 'success')
        return redirect(url_for('records', selected_date=new_date))

    # ✅ 传递给前端的记录是合并后的
    merged_record = {
        'id': record_id,  # 用第一条记录ID作为代表
        'type': original_record['type'],
        'category': original_record['category'],
        'amount': merged_amount,
        'description': merged_description,
        'date': original_record['date']
    }

    template_name = 'mobile/edit_record.html' if is_mobile() else 'edit_record.html'
    return render_template(template_name, record=merged_record)
    
@app.route('/delete_record/<record_id>', methods=['POST'])
def delete_record(record_id):
    data = load_data()
    record = next((r for r in data['records'] if r['id'] == record_id), None)
    if not record:
        flash('未找到该记录', 'danger')
        return redirect(url_for('records'))

    # ✅ 删除该日该类别所有记录
    data['records'] = [r for r in data['records'] if not (
        r['date'] == record['date'] and
        r['type'] == record['type'] and
        r['category'] == record['category']
    )]
    save_data(data)
    flash('已删除该类别所有记录', 'success')
    return redirect(url_for('records', selected_date=record['date']))

@app.route('/records')
def records():
    data = load_data()
    selected_date_str = request.args.get('selected_date', date.today().isoformat())
    records_for_day = [r for r in data['records'] if r['date'] == selected_date_str]

    # ✅ 合并逻辑：按 (type, category) 分组
    merged = defaultdict(lambda: {
        'id': None,  # 使用第一个记录的 ID 作为代表
        'type': '',
        'category': '',
        'amount': 0.0,
        'description': '',
        'date': selected_date_str,
        'count': 0  # 记录合并了几条
    })

    for r in records_for_day:
        key = (r['type'], r['category'])
        merged[key]['type'] = r['type']
        merged[key]['category'] = r['category']
        merged[key]['amount'] += r['amount']
        merged[key]['date'] = r['date']
        merged[key]['count'] += 1
        if merged[key]['id'] is None:
            merged[key]['id'] = r['id']  # 用第一条记录 ID 作为代表
        # 合并备注
        if r['description']:
            desc = r['description'].strip()
            if desc and desc not in merged[key]['description']:
                if merged[key]['description']:
                    merged[key]['description'] += f", {desc}"
                else:
                    merged[key]['description'] = desc

    merged_records = list(merged.values())

    income_records = [r for r in merged_records if r['type'] == 'income']
    expense_records = [r for r in merged_records if r['type'] == 'expense']
    daily_income_total = sum(r['amount'] for r in income_records)
    daily_expense_total = sum(r['amount'] for r in expense_records)

    template_name = 'mobile/records.html' if is_mobile() else 'records.html'
    return render_template(template_name,
                           all_day_records=merged_records,
                           income_records=income_records,
                           expense_records=expense_records,
                           selected_date=selected_date_str,
                           daily_income_total=daily_income_total,
                           daily_expense_total=daily_expense_total)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    data = load_data()
    if request.method == 'POST':
        updated_budgets = {}
        for key, value in request.form.items():
            if key.startswith('budget_'):
                category_name = key.replace('budget_', '', 1)
                try:
                    budget_amount = float(value) if value else 0.0
                    if budget_amount >= 0: updated_budgets[category_name] = budget_amount
                except (ValueError, TypeError): pass
        data['budgets'] = updated_budgets
        save_data(data)
        flash('预算已更新！', 'success')
        return redirect(url_for('settings'))
    
    budgets = defaultdict(float, data.get('budgets', {}))
    template_name = 'mobile/settings.html' if is_mobile() else 'settings.html'
    return render_template(template_name, 
                           categories=data['categories'], 
                           budgets=budgets,
                           settings=data.get('settings', {})) # 传递settings

@app.route('/toggle_keep_date', methods=['POST'])
def toggle_keep_date():
    """【新增】处理日期记忆开关的切换"""
    data = load_data()
    should_keep_date = 'keep_last_date' in request.form
    
    if 'settings' not in data:
        data['settings'] = {}
    data['settings']['keep_last_date'] = should_keep_date
    save_data(data)
    
    if should_keep_date:
        flash('已开启补录模式：日期将保持为您上次使用的日期。', 'success')
    else:
        flash('已关闭补录模式：日期将自动恢复到今天。', 'success')
        if 'last_used_date' in session:
            del session['last_used_date']
            
    return redirect(url_for('settings'))

@app.route('/add_category', methods=['POST'])
def add_category():
    data = load_data()
    category_type = request.form.get('type')
    new_category = request.form.get('new_category', '').strip()
    if not new_category or category_type not in ['expense', 'income']:
        flash('类别名称和类型不能为空！', 'danger')
        return redirect(url_for('settings'))
    if new_category in data['categories'][category_type]:
        flash(f"类别 '{new_category}' 已存在！", 'danger')
    else:
        data['categories'][category_type].append(new_category)
        save_data(data)
        flash(f"类别 '{new_category}' 添加成功！", 'success')
    return redirect(url_for('settings'))

@app.route('/delete_category', methods=['POST'])
def delete_category():
    data = load_data()
    category_type = request.form.get('type')
    category_to_delete = request.form.get('category')
    if category_to_delete in data['categories'][category_type]:
        data['categories'][category_type].remove(category_to_delete)
        if category_to_delete in data.get('budgets', {}): del data['budgets'][category_to_delete]
        save_data(data)
        flash(f"类别 '{category_to_delete}' 已删除。", 'success')
    else:
        flash('要删除的类别不存在！', 'danger')
    return redirect(url_for('settings'))

@app.route('/annual_report')
def annual_report():
    data = load_data()
    all_records = data['records']
    all_years = sorted(list(set(r['date'][:4] for r in all_records)), reverse=True)
    current_year_str = str(datetime.now().year)
    selected_year = request.args.get('year', all_years[0] if all_years else current_year_str)
    year_records = [r for r in all_records if r['date'].startswith(selected_year)]

    total_income = sum(r['amount'] for r in year_records if r['type'] == 'income')
    total_expense = sum(r['amount'] for r in year_records if r['type'] == 'expense')
    expense_by_category = defaultdict(float)
    monthly_trends = {f'{selected_year}-{m:02d}': {'income': 0, 'expense': 0} for m in range(1, 13)}

    for r in year_records:
        if r['date'][:7] in monthly_trends:
            if r['type'] == 'income': monthly_trends[r['date'][:7]]['income'] += r['amount']
            else:
                monthly_trends[r['date'][:7]]['expense'] += r['amount']
                expense_by_category[r['category']] += r['amount']
    top_expense_cat = sorted(expense_by_category.items(), key=lambda item: item[1], reverse=True)
    ai_summary = "该年度无足够数据生成摘要。"
    if total_expense > 0:
        top_cat_name = top_expense_cat[0][0] if top_expense_cat else "未知"
        ai_summary = f"根据您的数据，{selected_year}年度您的总收入为 ¥{total_income:,.2f}，总支出为 ¥{total_expense:,.2f}。主要支出集中在“{top_cat_name}”类别上。"
    
    render_params = {
        'all_years': all_years, 'selected_year': selected_year, 'total_income': total_income,
        'total_expense': total_expense, 'total_balance': total_income - total_expense,
        'top_expense_categories': top_expense_cat[:5], 'monthly_trends': monthly_trends, 'ai_summary': ai_summary
    }

    template_name = 'mobile/annual_report.html' if is_mobile() else 'annual_report.html'
    return render_template(template_name, **render_params)

@app.route('/export_csv')
def export_csv():
    data = load_data()
    records = data.get('records', [])
    output = io.StringIO()
    output.write('\ufeff') # BOM for Excel
    writer = csv.writer(output)
    writer.writerow(['ID', '类型', '类别', '金额', '备注', '日期'])
    for r in records:
        writer.writerow([r.get('id', ''), '收入' if r.get('type') == 'income' else '支出', r.get('category', ''), r.get('amount', 0), r.get('description', ''), r.get('date', '')])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment;filename=records_{datetime.now().strftime('%Y%m%d')}.csv"}
    )
@app.route('/export_json')
def export_json():
    if not os.path.exists(DATA_FILE):
        flash('数据文件不存在，无法导出。', 'danger')
        return redirect(url_for('settings'))
    return send_from_directory(
        directory=DATA_DIR, 
        path=os.path.basename(DATA_FILE), 
        as_attachment=True,
        download_name='sunshine_accounting_backup.json'
    )
@app.route('/import_json', methods=['POST'])
def import_json():
    if 'json_file' not in request.files:
        flash('没有文件被上传。', 'danger')
        return redirect(url_for('settings'))
    file = request.files['json_file']
    if file.filename == '':
        flash('未选择任何文件。', 'danger')
        return redirect(url_for('settings'))
    if file and file.filename.endswith('.json'):
        try:
            file_content = file.stream.read().decode('utf-8')
            new_data = json.loads(file_content)
            if 'records' in new_data and 'categories' in new_data and 'budgets' in new_data:
                save_data(new_data)
                flash('数据导入成功！您的所有数据已被更新。', 'success')
            else:
                flash('导入失败：JSON文件结构不正确，缺少必要的键 (records, categories, budgets)。', 'danger')
        except (json.JSONDecodeError, UnicodeDecodeError):
            flash('导入失败：文件不是有效的UTF-8编码JSON文件。', 'danger')
        except Exception as e:
            flash(f'发生未知错误: {e}', 'danger')
    else:
        flash('导入失败：请上传一个 .json 文件。', 'danger')
    return redirect(url_for('settings'))
@app.route('/debuglog')
def debug_log():
    _initialize_app_env()
    html_head = '''
    <head>
        <title>App Debug Log</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { background: #1a1a1a; color: #dcdcdc; font-family: Consolas, Monaco, monospace; line-height: 1.6; padding: 2em; margin: 0; }
            .controls { position: fixed; top: 10px; right: 15px; background: #333; padding: 10px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.5); z-index: 10; }
            .controls button { background: #555; color: white; border: none; padding: 8px 12px; margin-left: 10px; cursor: pointer; border-radius: 3px; }
            .controls button:hover { background: #666; }
            h1 { color: #87ceeb; margin-top: 50px; }
            pre { white-space: pre-wrap; word-wrap: break-word; }
            .INFO { color: #dcdcdc; }
            .WARNING { color: #f0e68c; }
            .ERROR { color: #ff6b6b; font-weight: bold; }
            .CRITICAL { color: #ff4757; font-weight: bold; background: #570000; display: block; padding: 2px 5px; }
            .DIAGNOSTIC { color: #87ceeb; }
        </style>
    </head>
    '''
    log_contents = log_capture_string.getvalue()
    colored = []
    for line in log_contents.splitlines():
        escaped = escape(line)
        if " | ERROR " in escaped:
            colored.append(f'<span class="ERROR">{escaped}</span>')
        elif " | WARNING " in escaped:
            colored.append(f'<span class="WARNING">{escaped}</span>')
        elif " | CRITICAL" in escaped:
            colored.append(f'<span class="CRITICAL">{escaped}</span>')
        elif "DIAGNOSTIC:" in escaped:
            colored.append(f'<span class="DIAGNOSTIC">{escaped}</span>')
        else:
            colored.append(f'<span class="INFO">{escaped}</span>')
    colored_logs = "<br>".join(colored)
    return f"""
    <html>{html_head}
    <body>
        <div class="controls">
            <form method="POST" action="/debuglog/clear" style="display:inline;">
                <button type="submit">清空日志</button>
            </form>
            <button onclick="location.reload()">刷新</button>
        </div>
        <h1>应用后端实时日志</h1>
        <pre>{colored_logs}</pre>
        <script>window.scrollTo(0, document.body.scrollHeight);</script>
    </body>
    </html>
    """
@app.route('/debuglog/clear', methods=['POST'])
def clear_debug_log():
    _initialize_app_env()
    log_capture_string.truncate(0)
    log_capture_string.seek(0)
    logging.info("DIAGNOSTIC: Log has been manually cleared by user.")
    return redirect(url_for('debug_log'))

def start_server():
    try:
        logging.info("=" * 20 + " Sunshine Accounting 服务器启动 (Android) " + "=" * 20)
        app.run(host='0.0.0.0', port=5001, debug=False)
    except Exception as e:
        logging.critical(f"FATAL: Flask server failed to start: {e}", exc_info=True)
 
if __name__ == '__main__':
    logging.info("=" * 20 + " Sunshine Accounting 应用启动 (Local/Docker) " + "=" * 20)
    app.run(host='0.0.0.0', port=5001, debug=True)

