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
import plotly.graph_objs as go
import plotly.io as pio
import plotly.graph_objs as go
from plotly.subplots import make_subplots

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



# @app.route('/stock_analysis', methods=['GET', 'POST'])
# def stock_analysis():
#     if request.method == 'POST':
#         ticker = request.form['ticker']
#         try:
#             analysis = perform_stock_analysis(ticker)
#             return render_template('stock_analysis.html', analysis=analysis, ticker=ticker)
#         except Exception as e:
#             error_message = f"An error occurred: {str(e)}"
#             return render_template('stock_analysis.html', error=error_message)
#     return render_template('stock_analysis.html')
# def perform_stock_analysis(ticker):
#     fundamental = perform_fundamental_analysis(ticker)
#     technical = perform_technical_analysis(ticker)
    
#     analysis_summary = f"""
#     Fundamental Analysis:
#     P/E Ratio: {fundamental['pe_ratio']}
#     EPS: {fundamental['eps']}
#     Revenue Growth: {fundamental['revenue_growth']}
#     Debt to Equity: {fundamental['debt_to_equity']}
#     Profit Margin: {fundamental['profit_margin']}

#     Technical Analysis:
#     50-Day Moving Average: {technical['moving_average_50']}
#     200-Day Moving Average: {technical['moving_average_200']}
#     RSI: {technical['rsi']}
#     MACD: {technical['macd']}
#     Support Level: {technical['support_level']}
#     Resistance Level: {technical['resistance_level']}
#     """
    
#     prompt = f"Based on the following stock analysis for {ticker}, provide a brief summary and recommendation:\n\n{analysis_summary}"
    
#     ai_insight = model.generate_content(prompt).text
    
#     fundamental_chart = create_fundamental_chart(fundamental)
#     technical_chart = create_technical_chart(technical)
    
#     return {
#         'fundamental': fundamental,
#         'technical': technical,
#         'ai_insight': ai_insight,
#         'fundamental_chart': fundamental_chart,
#         'technical_chart': technical_chart
#     }

# def perform_fundamental_analysis(ticker):
#     stock = yf.Ticker(ticker)
#     info = stock.info
    
#     return {
#         'pe_ratio': info.get('trailingPE', 'N/A'),
#         'eps': info.get('trailingEps', 'N/A'),
#         'revenue_growth': info.get('revenueGrowth', 'N/A'),
#         'debt_to_equity': info.get('debtToEquity', 'N/A'),
#         'profit_margin': info.get('profitMargins', 'N/A')
#     }

# def perform_technical_analysis(ticker):
#     stock = yf.Ticker(ticker)
#     hist = stock.history(period="1y")
    
#     ma50 = hist['Close'].rolling(window=50).mean().iloc[-1]
#     ma200 = hist['Close'].rolling(window=200).mean().iloc[-1]
    
#     def calculate_rsi(data, window=14):
#         delta = data['Close'].diff()
#         gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
#         loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
#         rs = gain / loss
#         return 100 - (100 / (1 + rs))
    
#     rsi = calculate_rsi(hist).iloc[-1]
    
#     def calculate_macd(data, fast=12, slow=26, signal=9):
#         fast_ema = data['Close'].ewm(span=fast, adjust=False).mean()
#         slow_ema = data['Close'].ewm(span=slow, adjust=False).mean()
#         macd = fast_ema - slow_ema
#         signal_line = macd.ewm(span=signal, adjust=False).mean()
#         return macd.iloc[-1] - signal_line.iloc[-1]
    
#     macd = calculate_macd(hist)
    
#     support = hist['Low'].min()
#     resistance = hist['High'].max()
    
#     return {
#         'moving_average_50': ma50,
#         'moving_average_200': ma200,
#         'rsi': rsi,
#         'macd': macd,
#         'support_level': support,
#         'resistance_level': resistance
#     }

# def create_fundamental_chart(fundamental_data):
#     fig = go.Figure(data=[go.Bar(
#         x=['P/E Ratio', 'EPS', 'Revenue Growth', 'Debt to Equity', 'Profit Margin'],
#         y=[fundamental_data['pe_ratio'], fundamental_data['eps'], fundamental_data['revenue_growth'],
#            fundamental_data['debt_to_equity'], fundamental_data['profit_margin']]
#     )])
#     fig.update_layout(title='Fundamental Analysis Metrics', yaxis_title='Value')
#     return pio.to_html(fig, full_html=False)

# def create_technical_chart(technical_data):
#     fig = go.Figure(data=[go.Scatter(
#         x=['50-Day MA', '200-Day MA', 'RSI', 'MACD', 'Support', 'Resistance'],
#         y=[technical_data['moving_average_50'], technical_data['moving_average_200'],
#            technical_data['rsi'], technical_data['macd'],
#            technical_data['support_level'], technical_data['resistance_level']],
#         mode='lines+markers'
#     )])
#     fig.update_layout(title='Technical Analysis Metrics', yaxis_title='Value')
#     return pio.to_html(fig, full_html=False)
@app.route('/stock_analysis', methods=['GET', 'POST'])
def stock_analysis():
    if request.method == 'POST':
        ticker = request.form['ticker']
        try:
            analysis = perform_stock_analysis(ticker)
            return render_template('stock_analysis.html', analysis=analysis, ticker=ticker)
        except Exception as e:
            error_message = f"An error occurred: {str(e)}"
            return render_template('stock_analysis.html', error=error_message)
    return render_template('stock_analysis.html')
def perform_stock_analysis(ticker):
    try:
        # Fetch stock data
        stock = yf.Ticker(ticker)
        stock_data = stock.history(period="1y")
        info = stock.info

        # Perform fundamental analysis
        fundamental = {
            'pe_ratio': info.get('trailingPE', 0),
            'eps': info.get('trailingEps', 0),
            'revenue_growth': info.get('revenueGrowth', 0),
            'debt_to_equity': info.get('debtToEquity', 0),
            'profit_margin': info.get('profitMargins', 0)
        }

        # Perform technical analysis
        technical = perform_technical_analysis(stock_data)

        # Create charts
        fundamental_chart = create_fundamental_chart(fundamental)
        technical_chart = create_technical_chart(stock_data, technical)

        # Generate AI insight
        analysis_summary = f"""
        Fundamental Analysis:
        P/E Ratio: {fundamental['pe_ratio']}
        EPS: {fundamental['eps']}
        Revenue Growth: {fundamental['revenue_growth']}
        Debt to Equity: {fundamental['debt_to_equity']}
        Profit Margin: {fundamental['profit_margin']}

        Technical Analysis:
        50-Day Moving Average: {technical['moving_average_50']}
        200-Day Moving Average: {technical['moving_average_200']}
        RSI: {technical['rsi']}
        MACD: {technical['macd']}
        Support Level: {technical['support_level']}
        Resistance Level: {technical['resistance_level']}
        """

        prompt = f"Based on the following stock analysis for {ticker}, provide a brief summary and recommendation in simple terms for a beginner investor:\n\n{analysis_summary}"
        ai_insight = model.generate_content(prompt).text

        return {
            'fundamental': fundamental,
            'technical': technical,
            'ai_insight': ai_insight,
            'fundamental_chart': fundamental_chart.to_html(full_html=False),
            'technical_chart': technical_chart.to_html(full_html=False)
        }
    except Exception as e:
        return f"An error occurred while analyzing the stock: {str(e)}"

def perform_technical_analysis(data):
    ma50 = data['Close'].rolling(window=50).mean().iloc[-1]
    ma200 = data['Close'].rolling(window=200).mean().iloc[-1]
    
    def calculate_rsi(data, window=14):
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    rsi = calculate_rsi(data).iloc[-1]
    
    def calculate_macd(data, fast=12, slow=26, signal=9):
        fast_ema = data['Close'].ewm(span=fast, adjust=False).mean()
        slow_ema = data['Close'].ewm(span=slow, adjust=False).mean()
        macd = fast_ema - slow_ema
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        return macd.iloc[-1] - signal_line.iloc[-1]
    
    macd = calculate_macd(data)
    
    support = data['Low'].min()
    resistance = data['High'].max()
    
    return {
        'moving_average_50': ma50,
        'moving_average_200': ma200,
        'rsi': rsi,
        'macd': macd,
        'support_level': support,
        'resistance_level': resistance
    }

def create_fundamental_chart(fundamental):
    categories = ['P/E Ratio', 'EPS ($)', 'Revenue Growth (%)', 'Debt to Equity', 'Profit Margin (%)']
    values = [
        fundamental['pe_ratio'],
        fundamental['eps'],
        fundamental['revenue_growth'] * 100 if fundamental['revenue_growth'] != 'N/A' else 0,
        fundamental['debt_to_equity'],
        fundamental['profit_margin'] * 100 if fundamental['profit_margin'] != 'N/A' else 0
    ]

    fig = go.Figure(data=go.Bar(
        x=categories,
        y=values,
        text=[f"{v:.2f}" for v in values],
        textposition='auto',
    ))

    fig.update_layout(
        title='Fundamental Analysis Overview',
        xaxis_title='Metrics',
        yaxis_title='Values',
        height=500,
        annotations=[
            go.layout.Annotation(
                x=0.5,
                y=-0.15,
                showarrow=False,
                text="P/E Ratio: Price to Earnings ratio, lower is generally better<br>"
                     "EPS: Earnings Per Share, higher is better<br>"
                     "Revenue Growth: Year-over-year revenue increase, higher is better<br>"
                     "Debt to Equity: Company's financial leverage, lower is generally better<br>"
                     "Profit Margin: Percentage of revenue that's profit, higher is better",
                xref="paper",
                yref="paper",
                align="center",
            )
        ]
    )

    return fig

def create_technical_chart(stock_data, technical):
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.1,
                        row_heights=[0.5, 0.25, 0.25],
                        subplot_titles=("Price and Moving Averages", "Trading Volume", "Relative Strength Index (RSI)"))

    # Candlestick chart
    fig.add_trace(go.Candlestick(x=stock_data.index,
                                 open=stock_data['Open'],
                                 high=stock_data['High'],
                                 low=stock_data['Low'],
                                 close=stock_data['Close'],
                                 name='Price'), row=1, col=1)

    # Add moving averages
    fig.add_trace(go.Scatter(x=stock_data.index, y=stock_data['Close'].rolling(window=50).mean(),
                             name='50-day MA', line=dict(color='orange')), row=1, col=1)
    fig.add_trace(go.Scatter(x=stock_data.index, y=stock_data['Close'].rolling(window=200).mean(),
                             name='200-day MA', line=dict(color='red')), row=1, col=1)

    # Volume chart
    fig.add_trace(go.Bar(x=stock_data.index, y=stock_data['Volume'], name='Volume'), row=2, col=1)

    # RSI
    rsi = calculate_rsi(stock_data)
    fig.add_trace(go.Scatter(x=stock_data.index, y=rsi, name='RSI'), row=3, col=1)

    # Add RSI reference lines
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

    # Update layout
    fig.update_layout(
        title='Technical Analysis Dashboard',
        height=900,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        annotations=[
            go.layout.Annotation(
                x=0.5,
                y=-0.15,
                showarrow=False,
                text="Candlesticks show daily price movements<br>"
                     "Moving Averages indicate trend direction<br>"
                     "Volume bars show trading activity<br>"
                     "RSI above 70 suggests overbought, below 30 suggests oversold",
                xref="paper",
                yref="paper",
                align="center",
            )
        ]
    )

    # Update y-axes
    fig.update_yaxes(title_text="Price ($)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=3, col=1)

    return fig

def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))
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
    annual_interest_rate = float(request.form['interest_rate'])
    interest_rate = annual_interest_rate / 100 / 12  # Convert annual rate to monthly rate
    tenure_years = int(request.form['tenure'])
    tenure_months = tenure_years * 12  # Convert years to months
    
    emi = (principal * interest_rate * (1 + interest_rate)**tenure_months) / ((1 + interest_rate)**tenure_months - 1)
    
    total_payment = emi * tenure_months
    total_interest = total_payment - principal
    
    # Generate AI advice
    advice = generate_loan_advice(principal, interest_rate * 12 * 100, tenure_years/ 12, emi)
    
    return jsonify({
        'emi': emi,
        'total_payment': total_payment,
        'total_interest': total_interest,
        'ai_advice': advice
    })

def generate_loan_advice(principal, interest_rate, tenure, emi):
    prompt = f"""
    As a financial advisor, provide personalized advice for someone taking a loan with the following details:
    - Loan Amount: ₹{principal}
    - Annual Interest Rate: {interest_rate:.2f}%
    - Loan Tenure: {tenure} years
    - Monthly EMI: ₹{emi:.2f}

    Please provide advice on:
    1. The feasibility of this loan based on general financial principles.
    2. Suggestions for managing the loan effectively.
    3. Potential risks and how to mitigate them.
    4. Any alternative options they should consider.

    Keep the advice concise, practical, and tailored to the Indian context.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"An error occurred while generating advice: {e}"
if __name__ == '__main__':
    app.run(debug=True)