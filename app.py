from flask import Flask, render_template, request, redirect, url_for, make_response
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

    @login_manager.user_loader
    def load_user(user_id):
     return User.query.get(int(user_id))
    @app.route("/login", methods=["GET", "POST"])
    def login():

     if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(
            username=username
        ).first()

        if user and check_password_hash(user.password, password):
            login_user(user)

            return redirect(url_for("home"))

        return "Invalid username or password."

     return render_template("login.html")
    @app.route("/logout")
    @login_required
    def logout():
     logout_user()
     return redirect(url_for("login"))

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

    return render_template(
        "index.html",
        total_products=total_products,
        total_stock=total_stock,
        low_stock_products=low_stock_products,
        total_transactions=total_transactions,
        recent_transactions=recent_transactions
    )

# -----------------------------------
# 5. Products Page
# -----------------------------------

@app.route("/products")
@login_required
def products():

    search = request.args.get("search", "")

    if search:
        products = Product.query.filter(
            Product.name.ilike(f"%{search}%")
        ).all()
    else:
        products = Product.query.all()

    return render_template(
        "products.html",
        products=products,
        search=search
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
                return redirect(url_for("products"))

    return render_template(
        "edit_product.html",
        product=product,
        error=error
    )



# -----------------------------------
# 8. Delete Product
# -----------------------------------

@app.route("/delete-product/<int:id>")
@login_required
def delete_product(id):

    # Find product
    product = Product.query.get_or_404(id)

    # Delete product
    db.session.delete(product)

    # Save changes
    db.session.commit()

    return redirect(
        url_for("products")
    )


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

                return redirect(url_for("products"))

    return render_template(
        "stock_out.html",
        product=product,
        error=error
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

if __name__ == "__main__":

    app.run(debug=True)