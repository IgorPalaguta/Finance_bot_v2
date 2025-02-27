from flask import Flask, request, jsonify, render_template

app = Flask(__name__)


# Функція підключення до БД
def get_db_connection():
    import sqlite3
    conn = sqlite3.connect('expenses.db')
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/')
def index():
    user_id = request.args.get('user_id')
    
    if not user_id:
        return "❌ User ID не отримано!", 400
    
    return f"✅ Ваш Telegram ID: {user_id}"



# 📌 Сторінка додавання категорії (отримує user_id)
@app.route('/add_category')
def add_category_page():
    user_id = request.args.get('user_id', '')
    return render_template('add_category.html', user_id=user_id)


@app.route('/add_category', methods=['POST'])
def add_category():
    data = request.json
    user_id = data.get('user_id')
    category_name = data.get('category')

    if not user_id or not category_name:
        return jsonify({"message": "❌ Введіть user_id і назву категорії!"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM categories WHERE user_id = ? AND name = ?", (user_id, category_name))

    if cursor.fetchone():
        conn.close()
        return jsonify({"message": "⚠️ Категорія вже існує!"}), 400

    cursor.execute("INSERT INTO categories (user_id, name) VALUES (?, ?)", (user_id, category_name))
    conn.commit()
    conn.close()

    return jsonify({"message": "✅ Категорія додана успішно!"})


if __name__ == '__main__':
    app.run(debug=True)
