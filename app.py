import sqlite3
import math
from datetime import datetime, timedelta
from io import BytesIO
from flask import send_file
from flask import Flask, render_template, request, redirect, url_for, make_response, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user
)

from werkzeug.security import generate_password_hash, check_password_hash


# -----------------------------------
# 1. Create Flask application
# -----------------------------------

app = Flask(__name__)
app.config["SECRET_KEY"] = "inventory-management-secret-key"


# -----------------------------------
# 2. Database configuration
# -----------------------------------

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///inventory.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


# Create database object
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


# -----------------------------------
# 3. Product Database Model
# -----------------------------------
class User(UserMixin, db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(100),
        nullable=False
    )
class Product(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    category = db.Column(
        db.String(100)
    )

    price = db.Column(
        db.Float,
        nullable=False
    )

    quantity = db.Column(
        db.Integer,
        nullable=False
    )

    minimum_stock = db.Column(
        db.Integer,
        default=5
    )


class Transaction(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    product_id = db.Column(
        db.Integer,
        nullable=False
    )

    product_name = db.Column(
        db.String(100),
        nullable=False
    )

    transaction_type = db.Column(
        db.String(20),
        nullable=False
    )

    quantity = db.Column(
        db.Integer,
        nullable=False
    )

    date = db.Column(
        db.DateTime,
        default=db.func.now()
    )

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)
    username = db.Column(db.String(100), nullable=False)
    action = db.Column(db.String(80), nullable=False)
    details = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.now())


def log_activity(action, details):
    if current_user.is_authenticated:
        db.session.add(ActivityLog(
            user_id=current_user.id,
            username=current_user.username,
            action=action,
            details=details
        ))


# -----------------------------------
# 3A. Authentication
# -----------------------------------

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("home"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    error = None

    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not check_password_hash(current_user.password, current_password):
            error = "Current password is incorrect."
        elif len(new_password) < 8:
            error = "New password must contain at least 8 characters."
        elif new_password != confirm_password:
            error = "New passwords do not match."
        elif new_password == current_password:
            error = "Choose a new password different from your current password."
        else:
            current_user.password = generate_password_hash(new_password)
            log_activity("Password Changed", "Admin password was updated")
            db.session.commit()
            logout_user()
            flash("Password changed successfully. Please log in again.", "success")
            return redirect(url_for("login"))

    return render_template("change_password.html", error=error)

# -----------------------------------
# 4. Home Page
# -----------------------------------

@app.route("/")
@login_required
def home():
    total_products = Product.query.count()

    total_stock = db.session.query(
        db.func.sum(Product.quantity)
    ).scalar() or 0

    low_stock_products = Product.query.filter(
        Product.quantity <= Product.minimum_stock
    ).count()

    total_transactions = Transaction.query.count()

    total_inventory_value = db.session.query(
        db.func.sum(Product.price * Product.quantity)
    ).scalar() or 0

    out_of_stock_products = Product.query.filter(
        Product.quantity == 0
    ).count()

    recent_transactions = Transaction.query.order_by(
        Transaction.date.desc()
    ).limit(5).all()

    # Monthly stock movement chart data
    movement_rows = db.session.query(
        db.func.strftime("%Y-%m", Transaction.date).label("month"),
        Transaction.transaction_type,
        db.func.sum(Transaction.quantity)
    ).group_by(
        db.func.strftime("%Y-%m", Transaction.date),
        Transaction.transaction_type
    ).order_by("month").all()

    monthly_totals = {}
    for month, movement_type, total in movement_rows:
        monthly_totals.setdefault(month, {"Stock In": 0, "Stock Out": 0})
        monthly_totals[month][movement_type] = total

    movement_months = list(monthly_totals.keys())
    monthly_stock_in = [monthly_totals[m]["Stock In"] for m in movement_months]
    monthly_stock_out = [monthly_totals[m]["Stock Out"] for m in movement_months]

    # Dashboard chart data
    category_data = db.session.query(
        Product.category,
        db.func.sum(Product.quantity)
    ).group_by(Product.category).all()

    chart_labels = [item[0] for item in category_data]
    chart_values = [item[1] for item in category_data]

    return render_template(
        "index.html",
        total_products=total_products,
        total_stock=total_stock,
        low_stock_products=low_stock_products,
        total_transactions=total_transactions,
        total_inventory_value=total_inventory_value,
        out_of_stock_products=out_of_stock_products,
        recent_transactions=recent_transactions,
        chart_labels=chart_labels,
        chart_values=chart_values,
        movement_months=movement_months,
        monthly_stock_in=monthly_stock_in,
        monthly_stock_out=monthly_stock_out
    )


# -----------------------------------
# 5. Products Page
# -----------------------------------


@app.route("/products")
@login_required
def products():
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    sort = request.args.get("sort", "").strip()

    query = Product.query

    # Search by product name
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))

    # Filter by category
    if category:
        query = query.filter(Product.category == category)

    # Sort products
    if sort == "price_low":
        query = query.order_by(Product.price.asc())
    elif sort == "price_high":
        query = query.order_by(Product.price.desc())
    elif sort == "quantity":
        query = query.order_by(Product.quantity.asc())
    elif sort == "name":
        query = query.order_by(Product.name.asc())

    # Pagination
    page = request.args.get("page", 1, type=int)
    pagination = query.paginate(page=page, per_page=5, error_out=False)
    products = pagination.items

    categories = db.session.query(Product.category).distinct().all()
    categories = [item[0] for item in categories if item[0]]

    return render_template(
        "products.html",
        products=products,
        search=search,
        category=category,
        categories=categories,
        sort=sort,
        pagination=pagination
    )


# -----------------------------------
# 6. Add Product
# -----------------------------------


@app.route("/add-product", methods=["GET", "POST"])
@login_required
def add_product():
    error = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()

        try:
            price = float(request.form.get("price", ""))
            quantity = int(request.form.get("quantity", ""))
            minimum_stock = int(request.form.get("minimum_stock", ""))
        except (ValueError, TypeError):
            error = "Enter a valid price and whole-number quantities."
        else:
            if not name or not category:
                error = "Product name and category are required."
            elif len(name) > 100 or len(category) > 100:
                error = "Product name and category must be 100 characters or fewer."
            elif not math.isfinite(price) or price < 0:
                error = "Enter a valid, non-negative price."
            elif quantity < 0 or minimum_stock < 0:
                error = "Quantity and minimum stock cannot be negative."
            else:
                product = Product(
                    name=name,
                    category=category,
                    price=price,
                    quantity=quantity,
                    minimum_stock=minimum_stock
                )
                db.session.add(product)
                log_activity("Product Added", f"Added product: {product.name}")
                db.session.commit()
                flash("Product added successfully!", "success")
                return redirect(url_for("products"))

    return render_template("add_product.html", error=error)


# -----------------------------------
# 7. Edit Product
# -----------------------------------


@app.route("/edit-product/<int:id>", methods=["GET", "POST"])
@login_required
def edit_product(id):
    product = Product.query.get_or_404(id)
    error = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()

        try:
            price = float(request.form.get("price", ""))
            quantity = int(request.form.get("quantity", ""))
            minimum_stock = int(request.form.get("minimum_stock", ""))
        except (ValueError, TypeError):
            error = "Enter a valid price and whole-number quantities."
        else:
            if not name or not category:
                error = "Product name and category are required."
            elif len(name) > 100 or len(category) > 100:
                error = "Product name and category must be 100 characters or fewer."
            elif not math.isfinite(price) or price < 0:
                error = "Enter a valid, non-negative price."
            elif quantity < 0 or minimum_stock < 0:
                error = "Quantity and minimum stock cannot be negative."
            else:
                product.name = name
                product.category = category
                product.price = price
                product.quantity = quantity
                product.minimum_stock = minimum_stock
                log_activity("Product Updated", f"Updated product: {product.name}")
                db.session.commit()
                flash("Product updated successfully!", "success")
                return redirect(url_for("products"))

    return render_template(
        "edit_product.html",
        product=product,
        error=error
    )


# -----------------------------------
# 8. Delete Product
# -----------------------------------

@app.route("/delete-product/<int:id>", methods=["POST"])
@login_required
def delete_product(id):
    product = Product.query.get_or_404(id)

    log_activity("Product Deleted", f"Deleted product: {product.name}")
    db.session.delete(product)
    db.session.commit()

    flash("Product deleted successfully!", "success")

    return redirect(url_for("products"))


@app.route("/stock-in/<int:id>", methods=["GET", "POST"])
@login_required
def stock_in(id):
    product = Product.query.get_or_404(id)
    error = None

    if request.method == "POST":
        try:
            quantity = int(request.form.get("quantity", ""))
        except (ValueError, TypeError):
            error = "Please enter a valid whole number."
        else:
            if quantity <= 0:
                error = "Quantity must be greater than zero."
            else:
                product.quantity += quantity
                transaction = Transaction(
                    product_id=product.id,
                    product_name=product.name,
                    transaction_type="Stock In",
                    quantity=quantity
                )
                db.session.add(transaction)
                log_activity("Stock In", f"Added {quantity} units of {product.name}")
                db.session.commit()
                flash("Stock added successfully!", "success")
                return redirect(url_for("products"))

    return render_template(
        "stock_in.html",
        product=product,
        error=error
    )


@app.route("/stock-out/<int:id>", methods=["GET", "POST"])
@login_required
def stock_out(id):
    product = Product.query.get_or_404(id)
    error = None

    if request.method == "POST":
        try:
            quantity = int(request.form.get("quantity", ""))
        except (ValueError, TypeError):
            error = "Please enter a valid whole number."
        else:
            if quantity <= 0:
                error = "Quantity must be greater than zero."
            elif quantity > product.quantity:
                error = "Not enough stock available."
            else:
                product.quantity -= quantity

                transaction = Transaction(
                    product_id=product.id,
                    product_name=product.name,
                    transaction_type="Stock Out",
                    quantity=quantity
                )

                db.session.add(transaction)
                log_activity("Stock Out", f"Removed {quantity} units of {product.name}")
                db.session.commit()
                flash("Stock removed successfully!", "success")

                return redirect(url_for("products"))

    return render_template(
        "stock_out.html",
        product=product,
        error=error
    )


@app.route("/product/<int:id>")
@login_required
def product_details(id):
    product = Product.query.get_or_404(id)
    recent_transactions = Transaction.query.filter_by(
        product_id=product.id
    ).order_by(Transaction.date.desc()).limit(10).all()

    return render_template(
        "product_details.html",
        product=product,
        recent_transactions=recent_transactions
    )


@app.route("/transactions")
@login_required
def transactions():
    search = request.args.get("search", "").strip()
    transaction_type = request.args.get("type", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    error = None

    query = Transaction.query

    if search:
        query = query.filter(
            Transaction.product_name.ilike(f"%{search}%")
        )

    if transaction_type in ["Stock In", "Stock Out"]:
        query = query.filter(
            Transaction.transaction_type == transaction_type
        )

    start_date = None
    end_date = None
    try:
        if date_from:
            start_date = datetime.strptime(date_from, "%Y-%m-%d")
        if date_to:
            end_date = datetime.strptime(date_to, "%Y-%m-%d")
        if start_date and end_date and start_date > end_date:
            error = "The start date cannot be later than the end date."
        else:
            if start_date:
                query = query.filter(Transaction.date >= start_date)
            if end_date:
                query = query.filter(
                    Transaction.date < end_date + timedelta(days=1)
                )
    except ValueError:
        error = "Please enter valid dates in the date fields."

    page = request.args.get("page", 1, type=int)
    if error:
        pagination = None
        transactions = []
    else:
        pagination = query.order_by(
            Transaction.date.desc()
        ).paginate(page=page, per_page=10, error_out=False)
        transactions = pagination.items

    return render_template(
        "transactions.html",
        transactions=transactions,
        pagination=pagination,
        search=search,
        transaction_type=transaction_type,
        date_from=date_from,
        date_to=date_to,
        error=error
    )

@app.route("/stock-summary")
@login_required
def stock_summary():
    total_stock_in = db.session.query(
        db.func.sum(Transaction.quantity)
    ).filter(Transaction.transaction_type == "Stock In").scalar() or 0

    total_stock_out = db.session.query(
        db.func.sum(Transaction.quantity)
    ).filter(Transaction.transaction_type == "Stock Out").scalar() or 0

    stock_in_by_product = db.session.query(
        Transaction.product_name,
        db.func.sum(Transaction.quantity).label("total")
    ).filter(
        Transaction.transaction_type == "Stock In"
    ).group_by(Transaction.product_id, Transaction.product_name).order_by(
        db.func.sum(Transaction.quantity).desc()
    ).all()

    stock_out_by_product = db.session.query(
        Transaction.product_name,
        db.func.sum(Transaction.quantity).label("total")
    ).filter(
        Transaction.transaction_type == "Stock Out"
    ).group_by(Transaction.product_id, Transaction.product_name).order_by(
        db.func.sum(Transaction.quantity).desc()
    ).all()

    return render_template(
        "stock_summary.html",
        total_stock_in=total_stock_in,
        total_stock_out=total_stock_out,
        net_movement=total_stock_in - total_stock_out,
        stock_in_by_product=stock_in_by_product,
        stock_out_by_product=stock_out_by_product
    )


@app.route("/activity-log")
@login_required
def activity_log():
    activities = ActivityLog.query.order_by(
        ActivityLog.timestamp.desc()
    ).limit(200).all()

    return render_template(
        "activity_log.html",
        activities=activities
    )


@app.route("/low-stock")
@login_required
def low_stock():
    products = Product.query.filter(
        Product.quantity <= Product.minimum_stock
    ).all()

    return render_template(
        "low_stock.html",
        products=products
    )



# -----------------------------------
# 9. Create Database
# -----------------------------------

with app.app_context():

    db.create_all()


@app.route("/export-low-stock")
@login_required
def export_low_stock():
    import csv
    from io import StringIO

    products = Product.query.filter(
        Product.quantity <= Product.minimum_stock
    ).order_by(Product.name.asc()).all()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Product ID",
        "Product Name",
        "Category",
        "Price",
        "Available Quantity",
        "Minimum Stock"
    ])

    for product in products:
        writer.writerow([
            product.id,
            product.name,
            product.category,
            product.price,
            product.quantity,
            product.minimum_stock
        ])

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = (
        "attachment; filename=low_stock_report.csv"
    )
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    return response


@app.route("/export-products")
@login_required
def export_products():
    import csv
    from io import StringIO

    products = Product.query.order_by(Product.id).all()

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "ID",
        "Product Name",
        "Category",
        "Price",
        "Quantity",
        "Minimum Stock"
    ])

    for product in products:
        writer.writerow([
            product.id,
            product.name,
            product.category,
            product.price,
            product.quantity,
            product.minimum_stock
        ])

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = (
        "attachment; filename=inventory_products.csv"
    )
    response.headers["Content-Type"] = "text/csv; charset=utf-8"

    return response


# -----------------------------------
# 10. Run Application
# -----------------------------------

@app.route("/export-transactions")
@login_required
def export_transactions():
    import csv
    from io import StringIO

    transactions = Transaction.query.order_by(
        Transaction.date.desc()
    ).all()

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "ID",
        "Product",
        "Transaction Type",
        "Quantity",
        "Date"
    ])

    for transaction in transactions:
        writer.writerow([
            transaction.id,
            transaction.product_name,
            transaction.transaction_type,
            transaction.quantity,
            transaction.date
        ])

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = (
        "attachment; filename=transaction_history.csv"
    )
    response.headers["Content-Type"] = "text/csv; charset=utf-8"

    return response
@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_server_error(error):
    return render_template("500.html"), 500

@app.route("/backup-database")
@login_required
def backup_database():
    source = db.engine.raw_connection()
    backup_db = sqlite3.connect(":memory:")

    try:
        source.backup(backup_db)
        backup_data = backup_db.serialize()
    finally:
        backup_db.close()
        source.close()

    return send_file(
        BytesIO(backup_data),
        mimetype="application/x-sqlite3",
        as_attachment=True,
        download_name="inventory_backup.db"
    )

if __name__ == "__main__":

    app.run(debug=True)