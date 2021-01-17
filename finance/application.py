import os
import re

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
     # get user cash total
    result = db.execute("SELECT cash FROM users WHERE id= %s", session["user_id"])
    cash = result[0]['cash']

    # pull all transactions belonging to user
    portfolio = db.execute("SELECT stock, number_shares FROM shares WHERE user_id =%s ORDER BY stock ASC", session['user_id'])

    if not portfolio:
        return apology("sorry you have no holdings")

    grand_total = cash

    # determine current price, stock total value and grand total value
    for stock in portfolio:
        price = lookup(stock['stock'])['price']
        total = round(stock['number_shares'] * price, 2)
        stock.update({'price': price, 'total': total})
        grand_total = total + cash
    return render_template("index.html", stocks=portfolio, cash=usd(cash), total=usd(grand_total))


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """ Deposit money into account """

    if request.method == "POST":

        #get amount from form
        deposit = request.form.get("amount")

        if int(deposit) < 100:
            return apology("Minimum deposit is $100")


        #select users current cash
        cash = db.execute("SELECT cash from users WHERE id = :user", user = session['user_id'])
        curr_cash = cash[0]['cash']

        cash_balance = int(deposit) + curr_cash

        #update cash column in users table
        db.execute("UPDATE users SET cash = %s WHERE id = %s", cash_balance, session['user_id']);
        return redirect("/")

    else:
        #if route reached via GET
        return render_template("deposit.html")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        #stock and shares variable
        stock = request.form.get("stock")
        shares = request.form.get("shares")

        #Ensure stock symbol and share is submitted
        if not stock or not shares:
            return apology("must provide stock symbol and number of shares")

        if int(shares) <= 0:
            return apology("Enter positive integer")

        #check if stock symbol is valid
        if stock == None:
            return apology("stock name not found please try again")

        #look up stock price
        quote = lookup(stock)
        price = quote["price"]

        #calculate cost of stock
        cost = int(shares) * int(price)

        #select users cash from db
        cash = db.execute("SELECT cash FROM users WHERE id =%s", session['user_id']);

        #check if user has enough cash for purchase
        if int(shares) * price > cash[0]['cash']:
            return apology("Not enough cash to buy shares, Deposit into your account")

        #update users cash after purchase
        else:
            new_cash = cash[0]['cash'] - int(shares) * price

            #update cash column in users table
            db.execute("UPDATE users SET cash = %s WHERE id = %s", new_cash, session['user_id']);

            #insert transaction data into purchase table
            db.execute("INSERT INTO purchase(user_id, stock, price, shares, cost) VALUES(%s, %s, %s, %s, %s)", session['user_id'], stock, price, int(shares), cost);

            #INSERT transaction into history
            db.execute("INSERT INTO history (user_id, stock, price, shares) VALUES(%s, %s, %s, %s)", session['user_id'], stock, price, shares);

            # pull number of shares of symbol in shares table
            curr_portfolio = db.execute("SELECT number_shares FROM shares WHERE stock=:stock AND user_id=:user", stock = quote['symbol'], user=session['user_id'])

            # add to portfolio database
            # if symbol is new, add to portfolio
            if not curr_portfolio:
                db.execute("INSERT INTO shares (user_id, stock, number_shares) VALUES (:user, :stock, :number_shares)",
                    user = session['user_id'], stock = quote['symbol'], number_shares = shares)

            # if symbol is already in portfolio, update quantity of shares and total
            else:
                db.execute("UPDATE shares SET number_shares = number_shares + :number_shares WHERE stock=:stock",
                    number_shares = shares, stock=quote["symbol"]);
            #send them to portfolio
            return redirect("/")

    else:
        #user reached route via GET
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    history = db.execute("SELECT * FROM history WHERE user_id = %s ORDER BY date DESC", session['user_id'])

    return render_template("history.html", stocks = history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]


        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
    else:
        stock = request.form.get("symbol")

        quote = lookup(stock)

        symbol = quote['symbol']
        name = quote['name']
        price = quote['price']

        return render_template("quoted.html", symbol=symbol, name=name, price=usd(price))


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "GET":
        return render_template("register.html")

    # User reached route via POST (as by submitting a form via POST)
    else:
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        #Ensure username doesn't exist
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                            username=request.form.get("username"))
        if len(rows) == 1:
            return apology("Username already taken")


        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        #verify password strength
        elif(len(request.form.get('password'))>=8):
            if(bool(re.match('((?=.*\d)(?=.*[a-z])(?=.*[A-Z])(?=.*[!@#$%^&*]).{8,30})',request.form.get('password')))==True):

                #check if passwords match
                if request.form.get("confirmation") != request.form.get("password"):
                    return apology("passwords don't match")

                else:
                    #Insert user into database
                    username = request.form.get("username")
                    password = generate_password_hash(request.form.get("confirmation"))

                    db.execute("INSERT INTO users(username, hash) VALUES(%s, %s)",username, password);
                return redirect("/")

        else:
            return apology("Password doesn't satisfy site password policy")






@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
         #stock and shares variables
        stock = request.form.get("stock")
        shares = int(request.form.get("shares"))

        #Ensure stock symbol and share is submitted
        if not stock or not shares:
            return apology("must provide stock symbol and number of shares")

        #check if stock symbol is valid
        if stock == None:
            return apology("stock name not found please try again")

        #check if share is positive int
        if shares <= 0:
            return apology("Enter positive integer")

        #look up stock price
        quote = lookup(stock)
        price = quote["price"]

        #calculate cost of transaction
        cost = shares * price


        # pull number of shares of symbol in shares table
        curr_shares = db.execute("SELECT number_shares FROM shares WHERE stock=:stock AND user_id=:user", stock = quote['symbol'], user=session['user_id']);


        #check if user has enough shares to sell
        #select users cash from db
        cash = db.execute("SELECT cash FROM users WHERE id =%s", session['user_id']);

        if shares > curr_shares[0]['number_shares']:
            return apology("Not enough shares to sell")

        elif shares > 4:
            return apology("Too much shares to sell")

        else:
            #Approve users transaction
            #update users cash after purchase
            new_cash = round(cash[0]['cash'] + (shares * price), 4)

            # update portfolio database
            # subtract stock from portfolio
            new_shares = curr_shares[0]['number_shares'] - shares

            #update cash column in users table
            db.execute("UPDATE users SET cash = :new_cash WHERE id = :user_id", new_cash = new_cash, user_id = session['user_id']);

            #insert transaction data into sell table
            db.execute("INSERT INTO sell(user_id, stock, price, shares, sell_price) VALUES(%s, %s, %s, %s, %s)", session['user_id'], stock, price, shares, cost);

            # insert transaction into history
            db.execute("INSERT INTO history (user_id, stock, price, shares) VALUES(%s,%s,%s, %s)", session['user_id'], stock, price, -shares);

            if new_shares <= 0:
                db.execute("DELETE FROM shares WHERE user_id=:user AND stock = :symbol", user = session['user_id'], symbol = stock);
                return redirect("/")

            else:
                #update shares in database
                db.execute("UPDATE shares SET number_shares = :shares WHERE stock=:stock", shares = new_shares, stock = quote["symbol"]);
                return redirect("/")

    else:
        #pull up all transactions belonging to user if requesT method was GET
        portfolio = db.execute("SELECT stock FROM shares WhERE user_id=%s", session['user_id'])

        return render_template("sell.html", stocks = portfolio)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
