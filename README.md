# flask-web-applications

This web applications via which users manage portfolios of stocks  i.e. buy and sell stocks (i.e., shares of a company)

It allows users to check real stocks’ actual prices and portfolios’ values, it will also let you buy (okay, “buy”) and sell (okay, “sell”) stocks by querying 
IEX for stocks’ prices.

Indeed, IEX lets you download stock quotes via their API (application programming interface) using URLs like https://cloud-sse.iexapis.com/stable/stock/nflx/quote?token=API_KEY. 
Notice how Netflix’s symbol (NFLX) is embedded in this URL; that’s how IEX knows whose data to return. 
