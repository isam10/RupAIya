import os
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import re
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for
import pandas as pd
import numpy as np

# Set up API keys and credentials
os.environ["GOOGLE_API_KEY"] = "AIzaSyChGObvSKtfT7C0FakHeaggVC4EAffU2P8"

# Configure the Gemini model
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
model = genai.GenerativeModel('gemini-pro')

# Cache dictionaries
stock_data_cache = {}
news_cache = {}
cache_duration = timedelta(minutes=5)  # Cache data for 5 minutes

def fetch_stock_data(tickers):
    now = datetime.now()
    data = {}
    for ticker in tickers:
        if ticker in stock_data_cache and now - stock_data_cache[ticker]['timestamp'] < cache_duration:
            data[ticker] = stock_data_cache[ticker]['data']
        else:
            stock = yf.Ticker(ticker)
            stock_history = stock.history(period="1d")
            try:
                price = stock_history['Close'].iloc[-1]
                change = ((stock_history['Close'].iloc[-1] - stock_history['Open'].iloc[-1]) / stock_history['Open'].iloc[-1]) * 100
                stock_data = {'price': price, 'change': change}
                stock_data_cache[ticker] = {'data': stock_data, 'timestamp': now}
                data[ticker] = stock_data
            except IndexError as e:
                print(f"Error fetching data for {ticker}: {e}")
                data[ticker] = {'price': "N/A", 'change': "N/A"}
    return data

def fetch_low_priced_stocks(max_price=100):
    now = datetime.now()
    cache_key = f"low_priced_stocks_{max_price}"
    if cache_key in stock_data_cache and now - stock_data_cache[cache_key]['timestamp'] < cache_duration:
        return stock_data_cache[cache_key]['data']
    
    url = "https://www.moneycontrol.com/stocks/marketstats/nse-mostactive-stocks/nse-priceband-upto-100.html"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    stocks = []
    table = soup.find('table', {'class': 'tbldata14 bdrtpg'})
    if table:
        rows = table.find_all('tr')[1:]  # Skip the header row
        for row in rows:
            cols = row.find_all('td')
            if len(cols) > 1:
                ticker = cols[0].get_text().strip()
                price = float(cols[1].get_text().replace(',', '').strip())
                if price <= max_price:
                    stocks.append(ticker)
    
    stock_data_cache[cache_key] = {'data': stocks, 'timestamp': now}
    return stocks

def fetch_financial_news():
    now = datetime.now()
    cache_key = "financial_news"
    if cache_key in news_cache and now - news_cache[cache_key]['timestamp'] < cache_duration:
        return news_cache[cache_key]['data']
    
    url = "https://www.moneycontrol.com/news/"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    headlines = [headline.get_text() for headline in soup.find_all('h2', class_='news_headline')]
    news_cache[cache_key] = {'data': headlines[:10], 'timestamp': now}  # Cache top 10 news headlines
    return headlines[:10]

def format_market_info(market_data, news_headlines):
    info = "Stock Prices:\n"
    for ticker, details in market_data.items():
        info += f"{ticker}: {details['price']} (Change: {details['change']:.2f}%)\n"
    info += "\nRecent News Headlines:\n"
    for headline in news_headlines:
        info += f"- {headline}\n"
    return info

def get_user_preferences():
    # Placeholder for getting user preferences
    return {
        "investment_goals": "long-term growth",
        "risk_tolerance": "medium",
        "preferred_sectors": ["technology", "healthcare"]
    }

def extract_price_constraint(query):
    match = re.search(r'under\s*(\d+)\s*rupees', query.lower())
    if match:
        return int(match.group(1))
    return None

def generate_response(query, market_info, user_preferences):
    prompt = f"""You are an AI assistant specializing in the stock market. Here is the current market information:

{market_info}

User preferences:
- Investment goals: {user_preferences['investment_goals']}
- Risk tolerance: {user_preferences['risk_tolerance']}
- Preferred sectors: {', '.join(user_preferences['preferred_sectors'])}

Based on this market data, news sentiment, and user preferences, please provide a specific and detailed answer to the following question:

{query}

Use only the provided current market data and user preferences. Do not use any pre-existing general knowledge.

In your response:
1. Use the provided current market data to inform your answer.
2. If the query is about future stock prices, use historical data trends, current market conditions, and available financial predictions to make an educated forecast.
3. Consider potential small-cap and penny stocks that show signs of future growth if relevant.
4. Provide reasoning for your recommendations or analysis, citing relevant data where possible.
5. Be specific, concise, and informative, always framing your response in the context of the current market conditions.
6. If asked about specific stocks, provide insights based on the overall market trend and your knowledge of companies.
7. Give detailed answer and give great justification for suggesting what you suggest.
8. Use only the provided current market data and user preferences. Do not use any pre-existing general knowledge."""

    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"An error occurred while generating the response: {e}"

# Nifty 50 stocks
nifty_50_stocks = {
    "RELIANCE.NS": "Reliance Industries",
    "INFY.NS": "Infosys",
    "ICICIBANK.NS": "ICICI Bank",
    "TCS.NS": "Tata Consultancy Services",
    "KOTAKBANK.NS": "Kotak Mahindra Bank",
    "HINDUNILVR.NS": "Hindustan Unilever",
    "BHARTIARTL.NS": "Bharti Airtel",
    "ITC.NS": "ITC Limited",
    "LT.NS": "Larsen & Toubro",
    "SBIN.NS": "State Bank of India",
    "BAJFINANCE.NS": "Bajaj Finance",
    "AXISBANK.NS": "Axis Bank",
    "ASIANPAINT.NS": "Asian Paints",
    "DMART.NS": "Avenue Supermarts",
    "MARUTI.NS": "Maruti Suzuki India",
    "SUNPHARMA.NS": "Sun Pharmaceutical Industries",
    "NESTLEIND.NS": "Nestlé India",
    "ULTRACEMCO.NS": "UltraTech Cement",
    "HCLTECH.NS": "HCL Technologies",
    "TITAN.NS": "Titan Company"
}

def fetch_stock_data_for_highlights(stock_symbol):
    try:
        stock = yf.Ticker(stock_symbol)
        data = stock.history(period="5d")
        if len(data) >= 2:
            return data.iloc[-2:]  # Return only the last two days
        else:
            print(f"Not enough data for {stock_symbol}")
            return None
    except Exception as e:
        print(f"Error fetching data for {stock_symbol}: {e}")
        return None

def fetch_news_for_highlights(company_name):
    news_params = {
        "apiKey": "9756635ba92f4fca9d07a7c18de7c58c",
        "q": company_name,
        "from": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
        "sortBy": "relevancy",
        "language": "en"
    }
    try:
        response = requests.get(url="https://newsapi.org/v2/everything", params=news_params)
        response.raise_for_status()
        articles = response.json().get("articles", [])
        return articles[:3]
    except requests.RequestException as e:
        print(f"Error fetching news for {company_name}: {e}")
        return []

def get_market_highlights():
    buy_candidates = []
    for stock_symbol, company_name in nifty_50_stocks.items():
        data = fetch_stock_data_for_highlights(stock_symbol)
        
        if data is None or len(data) < 2:
            continue
        
        yesterday_closing_price = data['Close'].iloc[-1]
        day_before_yesterday_closing_price = data['Close'].iloc[-2]
        
        difference = yesterday_closing_price - day_before_yesterday_closing_price
        diff_percent = (difference / yesterday_closing_price) * 100
        
        up_down = "🔺" if difference > 0 else "🔻"
        
        buy_candidates.append((stock_symbol, company_name, up_down, diff_percent, []))

    # Sort candidates by absolute percentage change and take top 10
    buy_candidates.sort(key=lambda x: abs(x[3]), reverse=True)
    top_candidates = buy_candidates[:10]

    # Fetch news for top candidates
    for candidate in top_candidates:
        news_articles = fetch_news_for_highlights(candidate[1])
        formatted_articles = [f"Headline: {article['title']}. Brief: {article['description']}" for article in news_articles[:3]]
        candidate[4].extend(formatted_articles)
    
    return top_candidates

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    query = request.form['query']
    max_price = extract_price_constraint(query)
    tickers = fetch_low_priced_stocks(max_price) if max_price else []
    
    if not tickers:
        words = query.split()
        tickers = [word.upper() for word in words if '.' in word and len(word) <= 10]

    stock_data = fetch_stock_data(tickers if tickers else ['^NSEI', '^BSESN', 'TATAMOTORS.NS', 'RELIANCE.NS', 'INFY.NS', 'ITC.NS', 'HINDUNILVR.NS'])
    news_headlines = fetch_financial_news()
    market_info = format_market_info(stock_data, news_headlines)
    user_preferences = get_user_preferences()
    
    response = generate_response(query, market_info, user_preferences)
    return jsonify({'response': response})

@app.route('/market_highlights')
def market_highlights():
    highlights = get_market_highlights()
    return render_template('market_highlights.html', highlights=highlights)

# @app.route('/tax_planner')
# def tax_planner():
#     return render_template('tax_planner.html')

# @app.route('/calculate_tax', methods=['POST'])
# def calculate_tax():
#     income = float(request.form['income'])
#     deductions = float(request.form['deductions'])
    
#     taxable_income = max(income - deductions, 0)
    
#     # Simple tax calculation (you may want to update this based on current tax laws)
#     if taxable_income <= 250000:
#         tax = 0
#     elif taxable_income <= 500000:
#         tax = (taxable_income - 250000) * 0.05
#     elif taxable_income <= 1000000:
#         tax = 12500 + (taxable_income - 500000) * 0.20
#     else:
#         tax = 112500 + (taxable_income - 1000000) * 0.30
    
#     return jsonify({
#         'taxable_income': taxable_income,
#         'tax': tax
#     })

# @app.route('/budget_designer')
# def budget_designer():
#     return render_template('budget_designer.html')

# @app.route('/calculate_budget', methods=['POST'])
# def calculate_budget():
#     income = float(request.form['income'])
#     expenses = {
#         'housing': float(request.form['housing']),
#         'transportation': float(request.form['transportation']),
#         'food': float(request.form['food']),
#         'utilities': float(request.form['utilities']),
#         'insurance': float(request.form['insurance']),
#         'healthcare': float(request.form['healthcare']),
#         'savings': float(request.form['savings']),
#         'personal': float(request.form['personal']),
#         'entertainment': float(request.form['entertainment'])
#     }
    
#     total_expenses = sum(expenses.values())
#     remaining = income - total_expenses
    
#     return jsonify({
#         'total_expenses': total_expenses,
#         'remaining': remaining,
#         'budget_breakdown': expenses
#     })
@app.route('/tax_planner')
def tax_planner():
    return render_template('tax_planner.html')

@app.route('/calculate_tax', methods=['POST'])
def calculate_tax():
    income = float(request.form['income'])
    
    # Calculate tax based on income slabs (for example purposes, using simplified Indian tax slabs)
    if income <= 250000:
        tax = 0
    elif income <= 500000:
        tax = (income - 250000) * 0.05
    elif income <= 750000:
        tax = 12500 + (income - 500000) * 0.10
    elif income <= 1000000:
        tax = 37500 + (income - 750000) * 0.15
    elif income <= 1250000:
        tax = 75000 + (income - 1000000) * 0.20
    elif income <= 1500000:
        tax = 125000 + (income - 1250000) * 0.25
    else:
        tax = 187500 + (income - 1500000) * 0.30
    
    # Tax saving suggestions
    prompt = f"""
    As a financial advisor, provide personalized tax planning advice for someone with an annual income of ₹{income}. 
    Include specific tax-saving strategies, investment options, and relevant deductions they could claim. 
    Keep the advice concise yet informative, focusing on the most impactful strategies for their income level.
    """
    
    try:
        response = model.generate_content(prompt)
        ai_advice = response.text.strip()
    except Exception as e:
        ai_advice = f"An error occurred while generating advice: {e}"

    return jsonify({
        'income': income,
        'tax': tax,
        'effective_tax_rate': (tax / income) * 100 if income > 0 else 0,
        'ai_advice': ai_advice
    })

@app.route('/budget_designer')
def budget_designer():
    return render_template('budget_designer.html')

@app.route('/calculate_budget', methods=['POST'])
def calculate_budget():
    income = float(request.form['income'])
    
    # Calculate budget allocation based on the 50/30/20 rule
    needs = income * 0.5
    wants = income * 0.3
    savings = income * 0.2
    
    budget_breakdown = {
        'Housing': needs * 0.35,
        'Transportation': needs * 0.15,
        'Food': needs * 0.25,
        'Utilities': needs * 0.10,
        'Insurance': needs * 0.15,
        'Personal Spending': wants * 0.4,
        'Entertainment': wants * 0.3,
        'Miscellaneous': wants * 0.3,
        'Emergency Fund': savings * 0.5,
        'Retirement Savings': savings * 0.3,
        'Other Savings Goals': savings * 0.2
    }
    prompt = f"""
    As a financial advisor, provide personalized budgeting advice for someone with a monthly income of ₹{income}. 
    Suggest a detailed budget breakdown, including recommended spending for various categories and savings goals. 
    Also, provide tips for sticking to the budget and potential areas for cost-cutting. 
    Keep the advice practical and tailored to the Indian context.
    """
    
    try:
        response = model.generate_content(prompt)
        ai_advice = response.text.strip()
    except Exception as e:
        ai_advice = f"An error occurred while generating advice: {e}"

    return jsonify({
        'income': income,
        'needs': needs,
        'wants': wants,
        'savings': savings,
        'budget_breakdown': budget_breakdown,
        'ai_advice': ai_advice
    })
@app.route('/real_estate_advisor')
def real_estate_advisor():
    return render_template('real_estate_advisor.html')

@app.route('/get_real_estate_advice', methods=['POST'])
def get_real_estate_advice():
    budget = float(request.form['budget'])
    location = request.form['location']
    purpose = request.form['purpose']  # 'investment' or 'living'

    prompt = f"""
    As a real estate expert, provide advice for someone looking to {purpose} in {location} with a budget of ₹{budget}. 
    Include insights on:
    1. Current market trends in {location}
    2. Types of properties available within the budget
    3. Potential areas for good returns (if for investment)
    4. Factors to consider (location-specific pros and cons)
    5. Tips for negotiation and due diligence
    Keep the advice practical, concise, and tailored to the Indian real estate market.
    """

    try:
        response = model.generate_content(prompt)
        advice = response.text.strip()
    except Exception as e:
        advice = f"An error occurred while generating advice: {e}"

    return jsonify({'advice': advice})
@app.route('/loan_calculator')
def loan_calculator():
    return render_template('loan_calculator.html')

@app.route('/calculate_loan', methods=['POST'])
def calculate_loan():
    principal = float(request.form['principal'])
    interest_rate = float(request.form['interest_rate']) / 100 / 12  # Monthly interest rate
    tenure = int(request.form['tenure']) * 12  # Convert years to months
    
    emi = (principal * interest_rate * (1 + interest_rate)**tenure) / ((1 + interest_rate)**tenure - 1)
    
    total_payment = emi * tenure
    total_interest = total_payment - principal
    
    return jsonify({
        'emi': emi,
        'total_payment': total_payment,
        'total_interest': total_interest
    })

if __name__ == '__main__':
    app.run(debug=True)