from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for, jsonify
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp
from passlib.hash import pbkdf2_sha256
from helpers import *

from flask.exthook import ExtDeprecationWarning
from warnings import simplefilter
simplefilter("ignore", ExtDeprecationWarning)
from flask_autoindex import AutoIndex
import csv
import os
import urllib.request


# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    table = db.execute("SELECT stockName, numBought, price FROM stocks WHERE id=:id", id=session['user_id'])
    row = db.execute("SELECT * FROM users WHERE id=:id", id=session['user_id'])
    cash = row[0]['cash']
    if table:
        shares = []
        stocks = []
        prices = []
        names = []
        totals = []
        final_t = 0
        for row in table:
           if row['stockName'] in stocks:
            index = stocks.index(row['stockName'])
            shares[index] = shares[index] + row['numBought']
           else:
               stocks.append(row['stockName'])
               shares.append(row['numBought'])
               quote = lookup(row['stockName'])
               price = quote['price']
               prices.append(price)
               name = quote['name']
               names.append(name)
        for i in range(len(stocks)):
            total = shares[i] * prices[i]
            totals.append(usd(total))
            final_t = final_t + total
        for i in range(len(stocks)-1):
            if(shares[i] == 0):
                del stocks[i]
                del shares[i]
                del prices[i]
                del names[i]
                del totals[i]
                
        
        final_t = final_t + cash
        
        return render_template("index.html", shares=shares, stocks=stocks, prices=prices, names=names, totals=totals, final_t = usd(final_t), cash=usd(cash), length=len(stocks))
    else:
        return render_template("index.html", shares=[], stocks=[], prices=[], names=[], totals=[], final_t = usd(cash), cash=usd(cash), length=0)
    #return apology("TODO")
@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    if request.method == "GET":
        rows = db.execute("SELECT * FROM users WHERE id = :id" , id = session["user_id"])
        return render_template("buy.html", cash=rows[0]["cash"])
    else: #method == post
        stock = request.form.get("stockName").upper()
        try:
            ex = int(request.form.get("numStocks"))
        except:
            return apology("Invalid Number of Stocks")
        if not request.form.get("numStocks") or int(request.form.get("numStocks")) <= 0:
            return apology("Invalid number of stocks")
        elif not stock or not lookup(stock):
            return apology("Invalid stock name")
        else:
            cost = float(request.form.get("numStocks")) * float(lookup(stock)["price"])
            cost = float(cost)
            rows = db.execute("SELECT * FROM users WHERE id = :id" , id = session["user_id"])
            cash=rows[0]["cash"]
            cash = float(cash)
            if(cash >= cost):
                cash -= cost
                db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash = cash, id = session["user_id"])
                db.execute("INSERT INTO stocks (id, stockName, price, numBought) VALUES(:id, :stockName, :price, :num)", id=session["user_id"], stockName=stock, price=cost, num = request.form.get("numStocks"))
            
            else:
                return apology("Insufficient funds")
            return redirect(url_for("index"))

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    table = db.execute("SELECT stockName, numBought, price, date FROM stocks WHERE id=:id", id=session['user_id'])
    row = db.execute("SELECT * FROM users WHERE id=:id", id=session['user_id'])
    cash = row[0]['cash']
    if table:
        shares = []
        stocks = []
        prices = []
        names = []
        for row in table:
           if row['stockName'] in stocks:
            index = stocks.index(row['stockName'])
            shares[index] = shares[index] + row['numBought']
            quote = lookup(row['stockName'])
            name = quote["name"]
            names.append(name)
           else:
               stocks.append(row['stockName'])
               shares.append(row['numBought'])
               quote = lookup(row['stockName'])
               price = quote['price']
               prices.append(price)
               name = quote["name"]
               names.append(name)
        
                
        return render_template("history.html", names = names, table = table, length = len(table))
    

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    
    return render_template("quote.html")
@app.route("/quoted", methods=["GET", "POST"])
@login_required
def quoted():
    url = "http://download.finance.yahoo.com/d/quotes.csv?f=snl1&s={}".format(request.args.get("symbol"))
    webpage = urllib.request.urlopen(url)
    datareader = csv.reader(webpage.read().decode("utf-8").splitlines())
    row = next(datareader)
    return jsonify({"name": row[1], "price": (row[2]), "symbol": row[0].upper()})

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    # ensure username was submitted
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")
        #ensure username is not taken
        elif request.form.get("username") == db.execute("SELECT * FROM users WHERE username = :jellyfish", jellyfish=request.form.get("username")):
            return apology("username is taken")
        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")
        elif not request.form.get("confirm password") == request.form.get("password"):
            return apology("passwords do not match")
        
        idnum = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", username = request.form.get("username"), hash = pwd_context.hash(request.form.get("password")))
        if(idnum == None):
            return apology("Registration not successful")
        #session["user_id"] = 
        return apology("Registration Successful")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    if request.method == "GET":
        rows = db.execute("SELECT * FROM users WHERE id = :id" , id = session["user_id"])
        return render_template("sell.html", cash=rows[0]["cash"])
    else: #method == post
        stock = request.form.get("stockName").upper()
        try:
            ex = int(request.form.get("numStocks"))
        except:
            return apology("Invalid Number of Stocks")
        if not request.form.get("numStocks") or int(request.form.get("numStocks")) <= 0:
            return apology("Invalid number of stocks")
        elif not stock or not lookup(stock):
            return apology("Invalid stock name")
        else:
            
            rows = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])
            stocksOwned = db.execute("SELECT * FROM stocks WHERE id = :id AND stockName = :stockName", id = session["user_id"], stockName = stock)
            index = 0
            pos = 0
            neg = 0
            while(index < len(stocksOwned)):
                if float(stocksOwned[index]["numBought"]) > 0:
                    pos += 1
                if float(stocksOwned[index]["numBought"]) < 0:
                    neg += 1
                index+=1
            total = pos - neg
            if(total <=0):
                return apology("Stock not owned")
            
            
            if(total - int(request.form.get("numStocks")) < 0):
                return apology("Not enough stocks owned")
            cost = float(request.form.get("numStocks")) * float(lookup(stock)["price"])
            cost = float(cost)
            cash=rows[0]["cash"]
            cash = float(cash)
            
            cash += cost
            cost = -1 * cost
            
            db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash = cash, id = session["user_id"])
            db.execute("INSERT INTO stocks (id, stockName, price, numBought) VALUES(:id, :stockName, :price, :num)", id=session["user_id"], stockName=stock, price=cost, num = (-1) * int(request.form.get("numStocks")))
            
            return redirect(url_for("index"))
    return apology("TODO")
