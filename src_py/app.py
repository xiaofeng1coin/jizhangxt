# 文件: app.py (最终定稿修复版)

# 文件: src_py/app.py (最终修复版)
 
import json
import uuid
import csv
import io
import os
import logging  # <--- 关键修复：添加缺失的 import
from datetime import datetime, date
from collections import defaultdict
from flask import Flask, render_template, request, redirect, url_for, flash, Response, send_from_directory
from markupsafe import escape # <-- 关键修复：添加缺失的 import
 
# --- 日志系统设置 ---
log_capture_string = io.StringIO()
root_logger = logging.getLogger()
if root_logger.hasHandlers():
    root_logger.handlers.clear()
root_logger.setLevel(logging.INFO)
stream_handler = logging.StreamHandler(log_capture_string)
formatter = logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s')
stream_handler.setFormatter(formatter)
root_logger.addHandler(stream_handler)
# --- 日志设置结束 ---

# --- 初始化 Flask 应用 ---
app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- 常量定义 ---
DATA_DIR = 'data'
DATA_FILE = os.path.join(DATA_DIR, 'data.json')

# --- 核心辅助函数 ---
def is_mobile():
    """检测请求是否来自移动设备。"""
    user_agent = request.headers.get('User-Agent', '').lower()
    mobile_keywords = ['mobi', 'android', 'iphone', 'ipod', 'ipad', 'windows phone', 'blackberry']
    return any(keyword in user_agent for keyword in mobile_keywords)

@app.context_processor
def inject_global_vars():
    """为所有模板注入全局变量，减少重复代码。"""
    data = load_data()
    return {
        'current_year': datetime.now().year,
        'today_for_form': datetime.now().strftime('%Y-%m-%d'),
        'default_expense_categories': data['categories']['expense'],
        'default_income_categories': data['categories']['income']
    }

# --- 数据处理辅助函数 ---
def save_data(data):
    """将数据结构以美化的JSON格式保存到文件。"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_data():
    """加载数据文件。如果不存在或损坏，则创建并返回一个纯净的初始结构。"""
    initial_data = {
        "records": [],
        "categories": {"expense": [], "income": []},
        "budgets": {}
    }
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            data.setdefault('records', [])
            data.setdefault('categories', {}).setdefault('expense', [])
            data.setdefault('categories', {}).setdefault('income', [])
            data.setdefault('budgets', {})
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
    current_month_str = now.strftime('%Y-%m')
    
    monthly_records = [r for r in all_records if r['date'].startswith(current_month_str)]
    monthly_income_total = sum(r['amount'] for r in monthly_records if r['type'] == 'income')
    monthly_expense_total = sum(r['amount'] for r in monthly_records if r['type'] == 'expense')
    monthly_savings = monthly_income_total - monthly_expense_total
    
    # 【最终修复】将预算相关的计算逻辑移到 if/else 分支之前，作为通用逻辑
    # 这样可以确保无论桌面端还是移动端，都能获取到所有需要的预算变量。
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
        # 移动端视图只需要这些变量
        return render_template('mobile/index.html',
                               monthly_savings=monthly_savings,
                               monthly_income_total=monthly_income_total,
                               monthly_expense_total=monthly_expense_total,
                               total_budget=total_budget,
                               overall_budget_progress=overall_budget_progress,
                               budget_progress=budget_progress)
    else: 
        # 桌面端视图需要每日数据 和 所有预算变量
        today_str = now.strftime('%Y-%m-%d')
        daily_income = sum(r['amount'] for r in all_records if r['date'] == today_str and r['type'] == 'income')
        daily_expense = sum(r['amount'] for r in all_records if r['date'] == today_str and r['type'] == 'expense')
        
        return render_template('index.html',
                               daily_income=daily_income, 
                               daily_expense=daily_expense,
                               monthly_income_total=monthly_income_total, 
                               monthly_expense_total=monthly_expense_total,
                               monthly_savings=monthly_savings,
                               total_budget=total_budget,
                               overall_budget_progress=overall_budget_progress,
                               budget_progress=budget_progress)

# --- 其他路由保持不变，为了完整性全部列出 ---

@app.route('/add')
def add_form():
    """仅移动端使用的路由，用于显示添加记录的表单页。"""
    if is_mobile():
        return render_template('mobile/edit_record.html', record=None)
    else:
        return redirect(url_for('index'))

@app.route('/add_record', methods=['POST'])
def add_record():
    """处理添加新记录的请求，已分离移动端和桌面端逻辑。"""
    data = load_data()
    try:
        amount_float = float(request.form.get('amount'))
    except (ValueError, TypeError):
        flash('金额必须是有效的数字！', 'danger')
        return redirect(url_for('add_form') if is_mobile() else url_for('index'))

    category = ""
    if is_mobile(): # 移动端：处理“自定义类别”逻辑
        selected_category = request.form.get('category')
        if selected_category == '--custom--':
            category = request.form.get('custom_category_input', '').strip()
            if not category:
                flash('选择了自定义类别，但未填写名称！', 'danger')
                return redirect(url_for('add_form'))
        else:
            category = selected_category
    else: # 桌面端：直接获取类别，保持简单逻辑
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
    flash('记录添加成功！', 'success')
    
    if is_mobile():
        return redirect(url_for('records', selected_date=new_record['date']))
    else:
        return redirect(url_for('index'))

@app.route('/edit_record/<record_id>', methods=['GET', 'POST'])
def edit_record(record_id):
    """显示和处理编辑记录的请求，已分离移动端和桌面端逻辑。"""
    data = load_data()
    record_to_edit = next((r for r in data['records'] if r['id'] == record_id), None)
    if not record_to_edit:
        flash('未找到该记录！', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            amount_float = float(request.form.get('amount'))
        except (ValueError, TypeError):
            flash('金额必须是有效的数字！', 'danger')
            return redirect(url_for('edit_record', record_id=record_id))

        category = ""
        if is_mobile(): # 移动端逻辑
            selected_category = request.form.get('category')
            if selected_category == '--custom--':
                category = request.form.get('custom_category_input', '').strip()
                if not category:
                    flash('选择了自定义类别，但未填写名称！', 'danger')
                    return redirect(url_for('edit_record', record_id=record_id))
            else:
                category = selected_category
        else: # 桌面端逻辑
            category = request.form.get('category').strip()

        record_to_edit['type'] = request.form.get('type')
        record_to_edit['category'] = category
        record_to_edit['amount'] = amount_float
        record_to_edit['description'] = request.form.get('description').strip()
        record_to_edit['date'] = request.form.get('date')
        
        save_data(data)
        flash('记录更新成功！', 'success')
        return redirect(url_for('records', selected_date=record_to_edit['date']))
    
    template_name = 'mobile/edit_record.html' if is_mobile() else 'edit_record.html'
    return render_template(template_name, record=record_to_edit)
    
@app.route('/delete_record/<record_id>', methods=['POST'])
def delete_record(record_id):
    data = load_data()
    record_date = next((r['date'] for r in data['records'] if r['id'] == record_id), date.today().isoformat())
    data['records'] = [r for r in data['records'] if r['id'] != record_id]
    save_data(data)
    flash('记录已删除。', 'success')
    return redirect(url_for('records', selected_date=record_date))

@app.route('/records')
def records():
    data = load_data()
    selected_date_str = request.args.get('selected_date', date.today().isoformat())
    records_for_day = [r for r in data['records'] if r['date'] == selected_date_str]
    income_records = [r for r in records_for_day if r['type'] == 'income']
    expense_records = [r for r in records_for_day if r['type'] == 'expense']
    daily_income_total = sum(r['amount'] for r in income_records)
    daily_expense_total = sum(r['amount'] for r in expense_records)
    
    template_name = 'mobile/records.html' if is_mobile() else 'records.html'
    return render_template(template_name,
                           all_day_records=sorted(records_for_day, key=lambda x: x.get('id', ''), reverse=True),
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
    return render_template(template_name, categories=data['categories'], budgets=budgets)

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

# ---【新增】数据导入与导出路由 ---
@app.route('/export_json')
def export_json():
    """提供 data.json 文件下载"""
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
    """处理上传的 JSON 文件并替换现有数据"""
    if 'json_file' not in request.files:
        flash('没有文件被上传。', 'danger')
        return redirect(url_for('settings'))
    
    file = request.files['json_file']
 
    if file.filename == '':
        flash('未选择任何文件。', 'danger')
        return redirect(url_for('settings'))
    
    if file and file.filename.endswith('.json'):
        try:
            # 读取文件内容并解码为字符串
            file_content = file.stream.read().decode('utf-8')
            new_data = json.loads(file_content)
 
            # 验证JSON文件的基本结构
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

# --- [新增开始] 日志查看路由 ---
@app.route('/debuglog')
def debug_log():
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
    
    colored_log_lines = []
    for line in log_contents.splitlines():
        escaped_line = escape(line)
        if " | ERROR " in escaped_line:
            colored_log_lines.append(f'<span class="ERROR">{escaped_line}</span>')
        elif " | WARNING " in escaped_line:
            colored_log_lines.append(f'<span class="WARNING">{escaped_line}</span>')
        elif " | CRITICAL" in escaped_line:
            colored_log_lines.append(f'<span class="CRITICAL">{escaped_line}</span>')
        elif "DIAGNOSTIC:" in escaped_line:
            colored_log_lines.append(f'<span class="DIAGNOSTIC">{escaped_line}</span>')
        else:
            colored_log_lines.append(f'<span class="INFO">{escaped_line}</span>')
    
    colored_logs = "<br>".join(colored_log_lines)
    
    return f"""
    <html>
        {html_head}
        <body>
            <div class="controls">
                <form method="POST" action="/debuglog/clear" style="display:inline;">
                    <button type="submit">清空日志</button>
                </form>
                <button onclick="location.reload()">刷新</button>
            </div>
            <h1>应用后端实时日志</h1>
            <pre>{colored_logs}</pre>
            <script>
                // 自动滚动到底部
                window.scrollTo(0, document.body.scrollHeight);
            </script>
        </body>
    </html>
    """
 
@app.route('/debuglog/clear', methods=['POST'])
def clear_debug_log():
    log_capture_string.truncate(0)
    log_capture_string.seek(0)
    logging.info("DIAGNOSTIC: Log has been manually cleared by user.")
    return redirect(url_for('debug_log'))
# --- [新增结束] ---
 
 
# --- 启动逻辑 ---
def start_server():
    """此函数由安卓的 Chaquopy 调用，用于在后台线程中启动服务器。"""
    try:
        logging.info("=" * 20 + " Sunshine Accounting 服务器启动 " + "=" * 20)
        app.run(host='0.0.0.0', port=5001, debug=False)
    except Exception as e:
        logging.critical(f"FATAL: Flask server failed to start: {e}", exc_info=True)
 
 
if __name__ == '__main__':
    logging.info("=" * 20 + " Sunshine Accounting 应用启动 (Local Test) " + "=" * 20)
    app.run(host='0.0.0.0', port=5001, debug=True)
