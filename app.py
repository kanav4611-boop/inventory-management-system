import sqlite3
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

    recent_transactions = Transaction.query.order_by(
        Transaction.date.desc()
    ).limit(5).all()

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
        recent_transactions=recent_transactions,
        chart_labels=chart_labels,
        chart_values=chart_values
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
            error = "Please enter valid numbers for price and quantities."
        else:
            if not name:
                error = "Product name is required."
            elif not category:
                error = "Category is required."
            elif price < 0:
                error = "Price cannot be negative."
            elif quantity < 0:
                error = "Quantity cannot be negative."
            elif minimum_stock < 0:
                error = "Minimum stock cannot be negative."
            else:
                product = Product(
                    name=name,
                    category=category,
                    price=price,
                    quantity=quantity,
                    minimum_stock=minimum_stock
                )

                db.session.add(product)
                db.session.commit()
                flash("Product added successfully!", "success")
                return redirect(url_for("products"))

    return render_template("add_product.html", error=error)


    if request.method == "POST":

        name = request.form["name"]

        category = request.form["category"]

        price = float(
            request.form["price"]
        )

        quantity = int(
            request.form["quantity"]
        )

        minimum_stock = int(
            request.form["minimum_stock"]
        )

        # Create new product
        product = Product(
            name=name,
            category=category,
            price=price,
            quantity=quantity,
            minimum_stock=minimum_stock
        )

        # Save product to database
        db.session.add(product)

        db.session.commit()
    
        # Go back to products page
        return redirect(
            url_for("products")
        )

    return render_template(
        "add_product.html"
    )


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
            error = "Please enter valid numbers for price and quantities."
        else:
            if not name:
                error = "Product name is required."
            elif not category:
                error = "Category is required."
            elif price < 0:
                error = "Price cannot be negative."
            elif quantity < 0:
                error = "Quantity cannot be negative."
            elif minimum_stock < 0:
                error = "Minimum stock cannot be negative."
            else:
                product.name = name
                product.category = category
                product.price = price
                product.quantity = quantity
                product.minimum_stock = minimum_stock

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

    query = Transaction.query

    if search:
        query = query.filter(
            Transaction.product_name.ilike(f"%{search}%")
        )

    if transaction_type in ["Stock In", "Stock Out"]:
        query = query.filter(
            Transaction.transaction_type == transaction_type
        )

    transactions = query.order_by(
        Transaction.date.desc()
    ).all()

    return render_template(
        "transactions.html",
        transactions=transactions,
        search=search,
        transaction_type=transaction_type
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