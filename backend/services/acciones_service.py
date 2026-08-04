import asyncio
import yfinance as yf

ACCIONES_CANDIDATAS = {
    # Tecnología
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corp.",
    "NVDA": "NVIDIA Corp.",
    "GOOGL": "Alphabet Inc.",
    "GOOG": "Alphabet Class C",
    "AMZN": "Amazon.com Inc.",
    "META": "Meta Platforms",
    "TSLA": "Tesla Inc.",
    "NFLX": "Netflix Inc.",
    "AMD": "Advanced Micro Devices",
    "INTC": "Intel Corp.",
    "CRM": "Salesforce Inc.",
    "ORCL": "Oracle Corp.",
    "ADBE": "Adobe Inc.",
    "AVGO": "Broadcom Inc.",
    "QCOM": "Qualcomm Inc.",
    "TXN": "Texas Instruments",
    "CSCO": "Cisco Systems",
    "IBM": "IBM Corp.",
    "HPQ": "HP Inc.",
    "DELL": "Dell Technologies",
    "MU": "Micron Technology",
    "INTU": "Intuit Inc.",
    "NOW": "ServiceNow Inc.",
    "SHOP": "Shopify Inc.",
    "PANW": "Palo Alto Networks",
    "SNOW": "Snowflake Inc.",
    "PLTR": "Palantir Technologies",
    "ARM": "Arm Holdings",
    "UBER": "Uber Technologies",
    "ABNB": "Airbnb Inc.",
    "DASH": "DoorDash Inc.",
    "XYZ": "Block Inc.",
    "HOOD": "Robinhood Markets",
    "COIN": "Coinbase Global",
    "SMCI": "Super Micro Computer",
    "AMAT": "Applied Materials",
    "LRCX": "Lam Research",
    "KLAC": "KLA Corp.",
    "MCHP": "Microchip Technology",
    "ADI": "Analog Devices",
    "CDNS": "Cadence Design Systems",
    "SNPS": "Synopsys Inc.",
    "ANET": "Arista Networks",
    "WDAY": "Workday Inc.",
    "CRWD": "CrowdStrike Holdings",
    "PYPL": "PayPal Holdings",
    "ASML": "ASML Holding (ADR)",
    "TSM": "TSMC (ADR)",
    "MELI": "MercadoLibre Inc.",
    "BABA": "Alibaba Group (ADR)",
    # Financieras
    "JPM": "JPMorgan Chase",
    "BAC": "Bank of America",
    "WFC": "Wells Fargo",
    "C": "Citigroup Inc.",
    "GS": "Goldman Sachs",
    "MS": "Morgan Stanley",
    "V": "Visa Inc.",
    "MA": "Mastercard Inc.",
    "AXP": "American Express",
    "COF": "Capital One",
    "SCHW": "Charles Schwab",
    "USB": "US Bancorp",
    "PNC": "PNC Financial",
    "TFC": "Truist Financial",
    "BLK": "BlackRock Inc.",
    "MET": "MetLife Inc.",
    "PRU": "Prudential Financial",
    "ALL": "Allstate Corp.",
    "AIG": "American Intl Group",
    "TRV": "Travelers Companies",
    "CB": "Chubb Ltd.",
    "SPGI": "S&P Global",
    "MCO": "Moody's Corp.",
    "ICE": "Intercontinental Exchange",
    "NDAQ": "Nasdaq Inc.",
    # Consumo
    "WMT": "Walmart Inc.",
    "COST": "Costco Wholesale",
    "TGT": "Target Corp.",
    "HD": "Home Depot",
    "LOW": "Lowe's Companies",
    "MCD": "McDonald's Corp.",
    "SBUX": "Starbucks Corp.",
    "NKE": "Nike Inc.",
    "DIS": "Walt Disney Co.",
    "KO": "Coca-Cola Co.",
    "PEP": "PepsiCo Inc.",
    "PG": "Procter & Gamble",
    "CL": "Colgate-Palmolive",
    "KMB": "Kimberly-Clark",
    "MO": "Altria Group",
    "PM": "Philip Morris Intl",
    "EL": "Estee Lauder",
    "LULU": "Lululemon Athletica",
    "CMG": "Chipotle Mexican Grill",
    "TJX": "TJX Companies",
    "ROST": "Ross Stores",
    "DLTR": "Dollar Tree",
    "GIS": "General Mills",
    "MDLZ": "Mondelez Intl",
    "HSY": "Hershey Co.",
    "KHC": "Kraft Heinz",
    "STZ": "Constellation Brands",
    "YUM": "Yum! Brands",
    "BBY": "Best Buy",
    "EBAY": "eBay Inc.",
    "ETSY": "Etsy Inc.",
    # Energía
    "XOM": "Exxon Mobil",
    "CVX": "Chevron Corp.",
    "COP": "ConocoPhillips",
    "SLB": "Schlumberger",
    "EOG": "EOG Resources",
    "PSX": "Phillips 66",
    "VLO": "Valero Energy",
    "MPC": "Marathon Petroleum",
    "OXY": "Occidental Petroleum",
    "KMI": "Kinder Morgan",
    "WMB": "Williams Companies",
    "OKE": "ONEOK Inc.",
    "BKR": "Baker Hughes",
    "HAL": "Halliburton Co.",
    "FANG": "Diamondback Energy",
    "DVN": "Devon Energy",
    # Industriales
    "BA": "Boeing Co.",
    "CAT": "Caterpillar Inc.",
    "DE": "Deere & Co.",
    "GE": "GE Aerospace",
    "HON": "Honeywell Intl",
    "UPS": "United Parcel Service",
    "FDX": "FedEx Corp.",
    "LMT": "Lockheed Martin",
    "RTX": "RTX Corp.",
    "GD": "General Dynamics",
    "NOC": "Northrop Grumman",
    "UNP": "Union Pacific",
    "ADP": "Automatic Data Proc.",
    "CTAS": "Cintas Corp.",
    "EMR": "Emerson Electric",
    "ETN": "Eaton Corp.",
    "CMI": "Cummins Inc.",
    "SWK": "Stanley Black & Decker",
    "PH": "Parker Hannifin",
    "ROP": "Roper Technologies",
    "ITW": "Illinois Tool Works",
    "ROK": "Rockwell Automation",
    "CSX": "CSX Corp.",
    "NSC": "Norfolk Southern",
    "LUV": "Southwest Airlines",
    "AAL": "American Airlines",
    "DAL": "Delta Air Lines",
    "UAL": "United Airlines",
    "MAR": "Marriott Intl",
    "RCL": "Royal Caribbean",
    "CCL": "Carnival Corp.",
    "NCLH": "Norwegian Cruise Line",
    # Salud
    "JNJ": "Johnson & Johnson",
    "PFE": "Pfizer Inc.",
    "MRK": "Merck & Co.",
    "ABBV": "AbbVie Inc.",
    "LLY": "Eli Lilly & Co.",
    "UNH": "UnitedHealth Group",
    "AMGN": "Amgen Inc.",
    "GILD": "Gilead Sciences",
    "BMY": "Bristol-Myers Squibb",
    "TMO": "Thermo Fisher",
    "DHR": "Danaher Corp.",
    "ABT": "Abbott Laboratories",
    "MDT": "Medtronic plc",
    "ISRG": "Intuitive Surgical",
    "VRTX": "Vertex Pharmaceuticals",
    "REGN": "Regeneron Pharma",
    "BIIB": "Biogen Inc.",
    "CVS": "CVS Health",
    "CI": "Cigna Group",
    "HUM": "Humana Inc.",
    "HCA": "HCA Healthcare",
    "ZTS": "Zoetis Inc.",
    "MRNA": "Moderna Inc.",
    "DXCM": "DexCom Inc.",
    "AZN": "AstraZeneca (ADR)",
    "NVS": "Novartis (ADR)",
    "SNY": "Sanofi (ADR)",
    # Comunicaciones
    "T": "AT&T Inc.",
    "VZ": "Verizon Communications",
    "TMUS": "T-Mobile US",
    "CMCSA": "Comcast Corp.",
    "CHTR": "Charter Communications",
    # Bienes raíces
    "AMT": "American Tower",
    "PLD": "Prologis Inc.",
    "SPG": "Simon Property Group",
    "O": "Realty Income",
    "WELL": "Welltower Inc.",
    "EQIX": "Equinix Inc.",
    # Materiales
    "LIN": "Linde plc",
    "APD": "Air Products",
    "SHW": "Sherwin-Williams",
    "DOW": "Dow Inc.",
    "FCX": "Freeport-McMoRan",
    "NEM": "Newmont Corp.",
    "NUE": "Nucor Corp.",
    "STLD": "Steel Dynamics",
    "VMC": "Vulcan Materials",
    "PPG": "PPG Industries",
    "ALB": "Albemarle Corp.",
    "CF": "CF Industries",
    # Autos
    "F": "Ford Motor Co.",
    "GM": "General Motors",
    "RIVN": "Rivian Automotive",
    "LCID": "Lucid Group",
    "LI": "Li Auto (ADR)",
    "NIO": "NIO Inc. (ADR)",
    "HMC": "Honda Motor (ADR)",
    "TM": "Toyota Motor (ADR)",
    # Latinoamérica
    "WALMEX.MX": "Walmart de Mexico",
    "AMX": "America Movil (ADR)",
    "FMX": "Femsa (ADR)",
    "CX": "Cemex (ADR)",
    "ITUB": "Itau Unibanco (ADR)",
    "BBD": "Banco Bradesco (ADR)",
    "PBR": "Petrobras (ADR)",
    "VALE": "Vale S.A. (ADR)",
}

DIAS_MOMENTUM = 60
DIAS_HISTORICO = 90


def _calcular_rsi(series, periodo=14):
    if len(series) < periodo + 1:
        return None
    ganancias = sum(max(series[i] - series[i-1], 0) for i in range(-periodo, 0))
    perdidas = sum(max(series[i-1] - series[i], 0) for i in range(-periodo, 0))
    if perdidas == 0:
        return 100.0
    rs = ganancias / perdidas
    return 100 - (100 / (1 + rs))


def _sincrono_obtener_acciones():
    tickers = list(ACCIONES_CANDIDATAS.keys())
    try:
        data = yf.download(tickers, period=f"{DIAS_HISTORICO}d", interval="1d", progress=False, group_by="ticker")
    except Exception:
        return None
    if data is None or data.empty:
        return None

    resultados = []
    for ticker, nombre in ACCIONES_CANDIDATAS.items():
        try:
            if data.columns.nlevels > 1:
                close = data[ticker]["Close"]
            else:
                close = data["Close"]
            close = close.dropna()
            if len(close) < 5:
                continue
            serie = [float(v) for v in close]
            ultimo = serie[-1]
            if ultimo <= 0:
                continue
            cambio_dia = ((ultimo - serie[-2]) / serie[-2] * 100) if len(serie) >= 2 else 0.0
            serie_momentum = serie[-DIAS_MOMENTUM:]
            momentum = ((ultimo - serie_momentum[0]) / serie_momentum[0] * 100) if len(serie_momentum) >= 2 else 0.0
            returns = [(serie[i] - serie[i-1]) / serie[i-1] for i in range(1, len(serie))]
            vol_diaria = (sum((r - sum(returns)/len(returns))**2 for r in returns) / len(returns)) ** 0.5
            vol_anual = vol_diaria * (252 ** 0.5) * 100
            rsi = _calcular_rsi(serie)
            # score: rendimiento por unidad de riesgo, penalizado si RSI sobrecompra
            score = (momentum / max(vol_anual, 1.0)) * 10
            if rsi is not None and rsi > 75:
                score *= 0.5
            resultados.append({
                "ticker": ticker,
                "empresa": nombre,
                "precio": round(ultimo, 2),
                "cambio_dia": round(cambio_dia, 2),
                "momentum_60d": round(momentum, 2),
                "volatilidad_anual": round(vol_anual, 1),
                "rsi": round(rsi, 1) if rsi is not None else None,
                "score": round(score, 2),
            })
        except (KeyError, IndexError, TypeError):
            continue

    if not resultados:
        return None
    resultados.sort(key=lambda r: r["score"], reverse=True)
    return resultados


async def obtener_acciones():
    return await asyncio.to_thread(_sincrono_obtener_acciones)
