from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user


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

        if user and user.password == password:
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

    # Find product by ID
    product = Product.query.get_or_404(id)

    if request.method == "POST":

        product.name = request.form["name"]

        product.category = request.form["category"]

        product.price = float(
            request.form["price"]
        )

        product.quantity = int(
            request.form["quantity"]
        )

        product.minimum_stock = int(
            request.form["minimum_stock"]
        )

        # Save changes
        db.session.commit()

        return redirect(
            url_for("products")
        )

    return render_template(
        "edit_product.html",
        product=product
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

    if request.method == "POST":
        quantity = int(request.form["quantity"])

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

    return render_template("stock_in.html", product=product)
@app.route("/stock-out/<int:id>", methods=["GET", "POST"])
@login_required
def stock_out(id):
    product = Product.query.get_or_404(id)

    if request.method == "POST":
        quantity = int(request.form["quantity"])

        if quantity > product.quantity:
            return "Not enough stock available."

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

    return render_template("stock_out.html", product=product)
@app.route("/transactions")
@login_required
def transactions():
    transactions = Transaction.query.order_by(
        Transaction.date.desc()
    ).all()

    return render_template(
        "transactions.html",
        transactions=transactions
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


# -----------------------------------
# 10. Run Application
# -----------------------------------

if __name__ == "__main__":

    app.run(debug=True)