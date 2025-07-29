import json
import uuid
import csv
import io
import os
from datetime import datetime, date
from collections import defaultdict
from flask import Flask, render_template, request, redirect, url_for, flash, Response

# --- 初始化 Flask 应用 ---
app = Flask(__name__)
# 强烈建议使用一个更长、更随机的密钥
app.secret_key = os.urandom(24)


@app.context_processor
def inject_current_year():
    return {'current_year': datetime.now().year}


# --- 常量定义 ---
DATA_DIR = 'data'
DATA_FILE = os.path.join(DATA_DIR, 'data.json')


# --- 数据处理辅助函数 ---

def load_data():
    """从单一的data.json加载所有数据，并确保所有关键键都存在"""
    # 设定一个健壮的默认数据结构
    default_data = {
        "records": [],
        "categories": {
            "expense": ['餐饮', '交通', '购物', '娱乐', '住房', '通讯', '医疗', '教育', '人情', '其他'],
            "income": ['工资', '兼职', '理财', '红包', '奖金', '其他']
        },
        "budgets": {}  # 预算现在是按类别存储的字典
    }

    # 确保 data 目录存在
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
            # 递归地更新默认数据，这样即使JSON文件不完整也不会出错
            # 注意：此方法不适用于深度嵌套的合并，但对当前结构足够
            default_data.update(loaded_data)
            # 再次确保核心键存在，防止文件被错误修改
            if 'records' not in default_data: default_data['records'] = []
            if 'categories' not in default_data: default_data['categories'] = {"expense": [], "income": []}
            if 'budgets' not in default_data: default_data['budgets'] = {}
            return default_data
    except (FileNotFoundError, json.JSONDecodeError):
        # 如果文件不存在或格式错误，保存并返回一个全新的默认文件
        save_data(default_data)
        return default_data


def save_data(data):
    """将包含所有数据的字典保存到data.json"""
    # 按日期对记录进行降序排序
    if 'records' in data:
        data['records'].sort(key=lambda x: x.get('date', ''), reverse=True)

    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# --- 路由和视图函数 ---

@app.route('/')
def index():
    """主页 - 仪表盘"""
    data = load_data()
    all_records = data['records']
    categories = data['categories']
    # 使用 defaultdict，这样模板中引用不存在的预算时不会出错
    budgets = defaultdict(float, data.get('budgets', {}))
    now = datetime.now()
    today_for_form = now.strftime('%Y-%m-%d')
    current_month_str = now.strftime('%Y-%m')

    daily_income = sum(r['amount'] for r in all_records if r['date'] == today_for_form and r['type'] == 'income')
    daily_expense = sum(r['amount'] for r in all_records if r['date'] == today_for_form and r['type'] == 'expense')

    monthly_records = [r for r in all_records if r['date'].startswith(current_month_str)]
    monthly_income_total = sum(r['amount'] for r in monthly_records if r['type'] == 'income')
    monthly_expense_total = sum(r['amount'] for r in monthly_records if r['type'] == 'expense')

    monthly_expense_by_category = defaultdict(float)
    for record in monthly_records:
        if record['type'] == 'expense':
            monthly_expense_by_category[record['category']] += record['amount']

    total_budget = sum(budgets.values())

    budget_progress = {}
    for category, budget_amount in budgets.items():
        if budget_amount > 0:  # 只显示有预算的类别
            spent_amount = monthly_expense_by_category.get(category, 0)
            progress_percent = (spent_amount / budget_amount) * 100
            budget_progress[category] = {
                "spent": spent_amount,
                "budget": budget_amount,
                "progress": min(progress_percent, 100),
                "overspent": spent_amount > budget_amount
            }

    overall_budget_progress = (monthly_expense_total / total_budget) * 100 if total_budget > 0 else 0

    return render_template(
        'index.html',
        daily_income=daily_income, daily_expense=daily_expense,
        monthly_income_total=monthly_income_total, monthly_expense_total=monthly_expense_total,
        monthly_savings=monthly_income_total - monthly_expense_total,
        default_expense_categories=categories['expense'],
        default_income_categories=categories['income'],
        budget_progress=dict(sorted(budget_progress.items())),
        overall_budget_progress=min(overall_budget_progress, 100),
        total_budget=total_budget,
        today_for_form=today_for_form
    )


@app.route('/add_record', methods=['POST'])
def add_record():
    data = load_data()
    try:
        amount_float = float(request.form.get('amount'))
    except (ValueError, TypeError):
        flash('金额必须是有效的数字！', 'danger')
        return redirect(url_for('index'))

    new_record = {
        'id': str(uuid.uuid4()),
        'type': request.form.get('type'),
        'category': request.form.get('category', '').strip(),
        'amount': amount_float,
        'description': request.form.get('description', '').strip(),
        'date': request.form.get('date') or datetime.now().strftime('%Y-%m-%d')
    }

    if not all([new_record['type'], new_record['category'], new_record['amount'] > 0]):
        flash('类型、类别和金额都是必填项，且金额必须大于0！', 'danger')
        return redirect(url_for('index'))

    data['records'].append(new_record)
    save_data(data)
    flash('记录添加成功！', 'success')
    return redirect(url_for('index'))


@app.route('/edit_record/<record_id>', methods=['GET', 'POST'])
def edit_record(record_id):
    data = load_data()
    record_to_edit = next((r for r in data['records'] if r['id'] == record_id), None)

    if not record_to_edit:
        flash('未找到该记录！', 'danger')
        return redirect(url_for('records'))

    if request.method == 'POST':
        try:
            amount_float = float(request.form.get('amount'))
            if amount_float <= 0:
                flash('金额必须是大于0的数字！', 'danger')
                return redirect(url_for('edit_record', record_id=record_id))
        except (ValueError, TypeError):
            flash('金额必须是有效的数字！', 'danger')
            return redirect(url_for('edit_record', record_id=record_id))

        record_to_edit['type'] = request.form.get('type')
        record_to_edit['category'] = request.form.get('category').strip()
        record_to_edit['amount'] = amount_float
        record_to_edit['description'] = request.form.get('description').strip()
        record_to_edit['date'] = request.form.get('date')
        save_data(data)
        flash('记录更新成功！', 'success')
        return redirect(url_for('records', selected_date=record_to_edit['date']))

    return render_template(
        'edit_record.html',
        record=record_to_edit,
        expense_categories=data['categories']['expense'],
        income_categories=data['categories']['income']
    )


@app.route('/delete_record/<record_id>', methods=['POST'])
def delete_record(record_id):
    data = load_data()
    original_length = len(data['records'])
    data['records'] = [r for r in data['records'] if r['id'] != record_id]

    if len(data['records']) < original_length:
        save_data(data)
        flash('记录已删除。', 'success')
    else:
        flash('删除失败，未找到该记录！', 'danger')

    return redirect(request.referrer or url_for('records'))


@app.route('/records')
def records():
    data = load_data()
    all_records = data['records']
    selected_date_str = request.args.get('selected_date', date.today().isoformat())
    records_for_day = [r for r in all_records if r['date'] == selected_date_str]

    income_records = [r for r in records_for_day if r['type'] == 'income']
    expense_records = [r for r in records_for_day if r['type'] == 'expense']

    daily_income_total = sum(r['amount'] for r in income_records)
    daily_expense_total = sum(r['amount'] for r in expense_records)

    return render_template(
        'records.html',
        income_records=income_records,
        expense_records=expense_records,
        selected_date=selected_date_str,
        daily_income_total=daily_income_total,
        daily_expense_total=daily_expense_total
    )


# 【核心修改】 settings 路由现在与新的HTML完美匹配
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    data = load_data()
    if request.method == 'POST':
        # 处理按类别预算的更新
        updated_budgets = {}
        for key, value in request.form.items():
            if key.startswith('budget_'):
                category_name = key.replace('budget_', '', 1)
                try:
                    # 如果值为空字符串，则视为0
                    budget_amount = float(value) if value else 0.0
                    if budget_amount >= 0:
                        # 只有大于0的预算才会被保存，简化数据
                        if budget_amount > 0:
                            updated_budgets[category_name] = budget_amount
                    else:
                        flash(f"类别'{category_name}'的预算金额不能为负数", "danger")
                except ValueError:
                    flash(f"为类别'{category_name}'输入的'{value}'不是有效的预算金额", "danger")

        data['budgets'] = updated_budgets
        save_data(data)
        flash('预算已更新！', 'success')
        return redirect(url_for('settings'))

    # 对于GET请求，渲染页面
    # 使用 defaultdict 以防止模板中出现键错误
    return render_template('settings.html',
                           categories=data['categories'],
                           budgets=defaultdict(float, data.get('budgets', {})))


# 【核心修改】 add_category 路由现在更健壮
@app.route('/add_category', methods=['POST'])
def add_category():
    data = load_data()
    category_type = request.form.get('type')
    new_category = request.form.get('new_category', '').strip()

    if not new_category or category_type not in ['expense', 'income']:
        flash('类别名称和类型不能为空！', 'danger')
        return redirect(url_for('settings'))

    if new_category in data['categories'][category_type]:
        flash(f"“{category_type}”类别下的 '{new_category}' 已存在！", 'danger')
    else:
        data['categories'][category_type].append(new_category)
        save_data(data)
        flash(f"类别 '{new_category}' 添加成功！", 'success')
    return redirect(url_for('settings'))


# 【核心修改】 delete_category 路由现在更健壮
@app.route('/delete_category', methods=['POST'])
def delete_category():
    data = load_data()
    category_type = request.form.get('type')
    category_to_delete = request.form.get('category')

    if category_type not in ['expense', 'income'] or not category_to_delete:
        flash('删除操作无效！', 'danger')
        return redirect(url_for('settings'))

    if category_to_delete in data['categories'][category_type]:
        data['categories'][category_type].remove(category_to_delete)
        # 如果删除的类别有预算，也一并删除预算
        if category_to_delete in data.get('budgets', {}):
            del data['budgets'][category_to_delete]
        save_data(data)
        flash(f"类别 '{category_to_delete}' 已删除。", 'success')
    else:
        flash('要删除的类别不存在！', 'danger')
    return redirect(url_for('settings'))


@app.route('/export_csv')
def export_csv():
    data = load_data()
    records = data.get('records', [])

    output = io.StringIO()
    # 写入BOM头，确保Excel正确识别UTF-8
    output.write('\ufeff')

    writer = csv.writer(output)
    writer.writerow(['ID', '类型', '类别', '金额', '备注', '日期'])

    for r in records:
        writer.writerow([
            r.get('id', ''),
            '收入' if r.get('type') == 'income' else '支出',
            r.get('category', ''),
            r.get('amount', 0),
            r.get('description', ''),
            r.get('date', '')
        ])

    # 确保指针在开始位置
    output.seek(0)

    return Response(
        output.getvalue(),  # .getvalue()已经是字符串了，不需要再编码
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment;filename=records_{datetime.now().strftime('%Y%m%d')}.csv"}
    )


@app.route('/report/annual')
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
    monthly_trends = {f'{selected_year}-{str(m).zfill(2)}': {'income': 0, 'expense': 0} for m in range(1, 13)}

    for r in year_records:
        if r['date'][:7] in monthly_trends:
            if r['type'] == 'income':
                monthly_trends[r['date'][:7]]['income'] += r['amount']
            else:
                monthly_trends[r['date'][:7]]['expense'] += r['amount']
                expense_by_category[r['category']] += r['amount']

    top_expense_cat = sorted(expense_by_category.items(), key=lambda item: item[1], reverse=True)

    ai_summary = "无足够数据生成摘要。"
    if total_expense > 0:
        top_cat_name = top_expense_cat[0][0] if top_expense_cat else "未知"
        ai_summary = f"根据您的数据，{selected_year}年度您的总收入为 ¥{total_income:,.2f}，总支出为 ¥{total_expense:,.2f}。主要支出集中在“{top_cat_name}”类别上。建议您继续保持良好的记账习惯，并关注支出较高的领域。"

    return render_template(
        'annual_report.html',
        all_years=all_years, selected_year=selected_year,
        total_income=total_income, total_expense=total_expense, total_balance=total_income - total_expense,
        top_expense_categories=top_expense_cat[:5],
        monthly_trends=monthly_trends,
        ai_summary=ai_summary
    )


# --- 主程序入口 ---
if __name__ == '__main__':
    # load_data() 函数内部已包含目录检查，这里不再需要
    app.run(host='0.0.0.0', port=5000, debug=True)
