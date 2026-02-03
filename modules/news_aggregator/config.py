"""
News Aggregator Configuration

RSS feeds, leader database, keywords, and event categorization.
"""

# =============================================================================
# RSS FEED SOURCES
# =============================================================================

# Financial News (existing)
FINANCIAL_FEEDS = {
    'bloomberg': {
        'url': 'https://feeds.bloomberg.com/markets/news.rss',
        'name': 'Bloomberg Markets',
        'category': 'FINANCIAL'
    },
    'cnbc': {
        'url': 'https://www.cnbc.com/id/20910258/device/rss/rss.html',
        'name': 'CNBC Markets',
        'category': 'FINANCIAL'
    },
    'yahoo': {
        'url': 'https://finance.yahoo.com/news/rssindex',
        'name': 'Yahoo Finance',
        'category': 'FINANCIAL'
    }
}

# Geopolitical & Defense
GEOPOLITICAL_FEEDS = {
    'war_on_rocks': {
        'url': 'https://warontherocks.com/feed/',
        'name': 'War on the Rocks',
        'category': 'GEOPOLITICAL'
    },
    'foreign_policy': {
        'url': 'https://foreignpolicy.com/feed/',
        'name': 'Foreign Policy',
        'category': 'GEOPOLITICAL'
    },
    'foreign_affairs': {
        'url': 'https://www.foreignaffairs.com/rss.xml',
        'name': 'Foreign Affairs',
        'category': 'GEOPOLITICAL'
    },
    'defense_news': {
        'url': 'https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml',
        'name': 'Defense News',
        'category': 'GEOPOLITICAL'
    },
    'brookings': {
        'url': 'https://www.brookings.edu/feed/',
        'name': 'Brookings Institution',
        'category': 'GEOPOLITICAL'
    },
}

# Central Bank Official Feeds
CENTRAL_BANK_FEEDS = {
    'fed': {
        'url': 'https://www.federalreserve.gov/feeds/press_all.xml',
        'name': 'Federal Reserve',
        'category': 'CENTRAL_BANK'
    },
    'ecb': {
        'url': 'https://www.ecb.europa.eu/rss/press.xml',
        'name': 'ECB',
        'category': 'CENTRAL_BANK'
    },
    'boe': {
        'url': 'https://www.bankofengland.co.uk/rss/news',
        'name': 'Bank of England',
        'category': 'CENTRAL_BANK'
    },
    'boj': {
        'url': 'https://www.boj.or.jp/en/rss/whatsnew.xml',
        'name': 'Bank of Japan',
        'category': 'CENTRAL_BANK'
    },
    'boc': {
        'url': 'https://www.bankofcanada.ca/feed/',
        'name': 'Bank of Canada',
        'category': 'CENTRAL_BANK'
    },
    'rba': {
        'url': 'https://www.rba.gov.au/rss/rss-cb-media-releases.xml',
        'name': 'Reserve Bank of Australia',
        'category': 'CENTRAL_BANK'
    },
    'rbnz': {
        'url': 'https://www.rbnz.govt.nz/hub/-/media/project/sites/rbnz/files/rss/rbnz-news.xml',
        'name': 'Reserve Bank of New Zealand',
        'category': 'CENTRAL_BANK'
    },
}

# Political News
POLITICAL_FEEDS = {
    'ap_politics': {
        'url': 'https://feedx.net/rss/ap-politics.xml',
        'name': 'AP Politics',
        'category': 'POLITICAL'
    },
    'politico': {
        'url': 'https://rss.politico.com/economy.xml',
        'name': 'Politico Economy',
        'category': 'POLITICAL'
    },
    'the_hill': {
        'url': 'https://thehill.com/feed/',
        'name': 'The Hill',
        'category': 'POLITICAL'
    },
}

# Fixed Income / Rates / Bond Markets
FIXED_INCOME_FEEDS = {
    'ft_markets': {
        'url': 'https://www.ft.com/rss/home',
        'name': 'Financial Times',
        'category': 'FINANCIAL'
    },
    'marketwatch': {
        'url': 'https://feeds.content.dowjones.io/public/rss/mw_bulletins',
        'name': 'MarketWatch Bulletins',
        'category': 'FINANCIAL'
    },
    'treasury_gov': {
        'url': 'https://home.treasury.gov/system/files/136/treasury-rss.xml',
        'name': 'US Treasury',
        'category': 'ECON'
    },
}

# US Government / Trade
GOVERNMENT_FEEDS = {
    'white_house': {
        'url': 'https://www.whitehouse.gov/feed/',
        'name': 'White House',
        'category': 'POLITICAL'
    },
    'ustr': {
        'url': 'https://ustr.gov/about-us/policy-offices/press-office/press-releases/feed',
        'name': 'US Trade Representative',
        'category': 'POLITICAL'
    },
    'cbo': {
        'url': 'https://www.cbo.gov/publications/all/rss.xml',
        'name': 'Congressional Budget Office',
        'category': 'ECON'
    },
    'imf_news': {
        'url': 'https://www.imf.org/en/News/Rss?type=News',
        'name': 'IMF News',
        'category': 'ECON'
    },
}

# Combine all feeds
RSS_FEEDS = {
    **FINANCIAL_FEEDS,
    **GEOPOLITICAL_FEEDS,
    **CENTRAL_BANK_FEEDS,
    **POLITICAL_FEEDS,
    **FIXED_INCOME_FEEDS,
    **GOVERNMENT_FEEDS
}


# =============================================================================
# LEADER DATABASE
# =============================================================================

LEADERS = {
    # US Government & Federal Reserve
    'trump': {
        'names': ['Trump', 'Donald Trump', 'President Trump', 'POTUS'],
        'countries': ['US'],
        'role': 'POTUS',
        'institution': 'WHITE_HOUSE'
    },
    'biden': {
        'names': ['Biden', 'Joe Biden', 'President Biden'],
        'countries': ['US'],
        'role': 'FORMER_POTUS',
        'institution': 'WHITE_HOUSE'
    },
    'powell': {
        'names': ['Powell', 'Jay Powell', 'Jerome Powell', 'Fed Chair Powell', 'Chairman Powell'],
        'countries': ['US'],
        'role': 'FED_CHAIR',
        'institution': 'FED'
    },
    'yellen': {
        'names': ['Yellen', 'Janet Yellen', 'Secretary Yellen'],
        'countries': ['US'],
        'role': 'TREASURY_SEC',
        'institution': 'TREASURY'
    },
    'bessent': {
        'names': ['Bessent', 'Scott Bessent'],
        'countries': ['US'],
        'role': 'TREASURY_SEC',
        'institution': 'TREASURY'
    },
    'waller': {
        'names': ['Waller', 'Christopher Waller', 'Gov. Waller'],
        'countries': ['US'],
        'role': 'FED_GOVERNOR',
        'institution': 'FED'
    },
    'bowman': {
        'names': ['Bowman', 'Michelle Bowman', 'Gov. Bowman'],
        'countries': ['US'],
        'role': 'FED_GOVERNOR',
        'institution': 'FED'
    },
    'barr': {
        'names': ['Barr', 'Michael Barr', 'Vice Chair Barr'],
        'countries': ['US'],
        'role': 'FED_VICE_CHAIR',
        'institution': 'FED'
    },
    'gensler': {
        'names': ['Gensler', 'Gary Gensler'],
        'countries': ['US'],
        'role': 'SEC_CHAIR',
        'institution': 'SEC'
    },

    # Eurozone
    'lagarde': {
        'names': ['Lagarde', 'Christine Lagarde', 'ECB President Lagarde', 'President Lagarde'],
        'countries': ['EU'],
        'role': 'ECB_PRESIDENT',
        'institution': 'ECB'
    },
    'schnabel': {
        'names': ['Schnabel', 'Isabel Schnabel'],
        'countries': ['EU'],
        'role': 'ECB_BOARD',
        'institution': 'ECB'
    },
    'lane': {
        'names': ['Lane', 'Philip Lane'],
        'countries': ['EU'],
        'role': 'ECB_CHIEF_ECONOMIST',
        'institution': 'ECB'
    },
    'von_der_leyen': {
        'names': ['von der Leyen', 'Ursula von der Leyen', 'Commission President'],
        'countries': ['EU'],
        'role': 'EC_PRESIDENT',
        'institution': 'EU_COMMISSION'
    },
    'scholz': {
        'names': ['Scholz', 'Olaf Scholz', 'Chancellor Scholz'],
        'countries': ['DE', 'EU'],
        'role': 'CHANCELLOR',
        'institution': 'GERMANY'
    },
    'macron': {
        'names': ['Macron', 'Emmanuel Macron', 'President Macron'],
        'countries': ['FR', 'EU'],
        'role': 'PRESIDENT',
        'institution': 'FRANCE'
    },
    'meloni': {
        'names': ['Meloni', 'Giorgia Meloni', 'PM Meloni'],
        'countries': ['IT', 'EU'],
        'role': 'PM',
        'institution': 'ITALY'
    },

    # United Kingdom
    'bailey': {
        'names': ['Bailey', 'Andrew Bailey', 'BoE Governor Bailey', 'Governor Bailey'],
        'countries': ['GB'],
        'role': 'BOE_GOVERNOR',
        'institution': 'BOE'
    },
    'starmer': {
        'names': ['Starmer', 'Keir Starmer', 'PM Starmer'],
        'countries': ['GB'],
        'role': 'PM',
        'institution': 'UK_GOV'
    },
    'sunak': {
        'names': ['Sunak', 'Rishi Sunak'],
        'countries': ['GB'],
        'role': 'FORMER_PM',
        'institution': 'UK_GOV'
    },
    'reeves': {
        'names': ['Reeves', 'Rachel Reeves', 'Chancellor Reeves'],
        'countries': ['GB'],
        'role': 'CHANCELLOR',
        'institution': 'UK_TREASURY'
    },

    # Japan
    'ueda': {
        'names': ['Ueda', 'Kazuo Ueda', 'BoJ Governor Ueda', 'Governor Ueda'],
        'countries': ['JP'],
        'role': 'BOJ_GOVERNOR',
        'institution': 'BOJ'
    },
    'kishida': {
        'names': ['Kishida', 'Fumio Kishida', 'PM Kishida'],
        'countries': ['JP'],
        'role': 'FORMER_PM',
        'institution': 'JAPAN_GOV'
    },
    'ishiba': {
        'names': ['Ishiba', 'Shigeru Ishiba', 'PM Ishiba'],
        'countries': ['JP'],
        'role': 'PM',
        'institution': 'JAPAN_GOV'
    },
    'suzuki': {
        'names': ['Suzuki', 'Shunichi Suzuki'],
        'countries': ['JP'],
        'role': 'FINANCE_MIN',
        'institution': 'MOF'
    },
    'kanda': {
        'names': ['Kanda', 'Masato Kanda'],
        'countries': ['JP'],
        'role': 'FX_CHIEF',
        'institution': 'MOF'
    },

    # Canada
    'macklem': {
        'names': ['Macklem', 'Tiff Macklem', 'BoC Governor Macklem', 'Governor Macklem'],
        'countries': ['CA'],
        'role': 'BOC_GOVERNOR',
        'institution': 'BOC'
    },
    'trudeau': {
        'names': ['Trudeau', 'Justin Trudeau', 'PM Trudeau'],
        'countries': ['CA'],
        'role': 'PM',
        'institution': 'CANADA_GOV'
    },
    'poilievre': {
        'names': ['Poilievre', 'Pierre Poilievre'],
        'countries': ['CA'],
        'role': 'OPPOSITION',
        'institution': 'CANADA_GOV'
    },
    'carney': {
        'names': ['Carney', 'Mark Carney'],
        'countries': ['CA'],
        'role': 'PM_CANDIDATE',
        'institution': 'CANADA_GOV'
    },
    'freeland': {
        'names': ['Freeland', 'Chrystia Freeland'],
        'countries': ['CA'],
        'role': 'FORMER_FINANCE_MIN',
        'institution': 'CANADA_GOV'
    },

    # Mexico
    'sheinbaum': {
        'names': ['Sheinbaum', 'Claudia Sheinbaum', 'President Sheinbaum'],
        'countries': ['MX'],
        'role': 'PRESIDENT',
        'institution': 'MEXICO_GOV'
    },
    'rodriguez': {
        'names': ['Rodriguez', 'Victoria Rodriguez', 'Governor Rodriguez'],
        'countries': ['MX'],
        'role': 'BANXICO_GOVERNOR',
        'institution': 'BANXICO'
    },
    'ebrard': {
        'names': ['Ebrard', 'Marcelo Ebrard'],
        'countries': ['MX'],
        'role': 'ECONOMY_MIN',
        'institution': 'MEXICO_GOV'
    },
    'amlo': {
        'names': ['AMLO', 'Lopez Obrador', 'Andres Manuel Lopez Obrador'],
        'countries': ['MX'],
        'role': 'FORMER_PRESIDENT',
        'institution': 'MEXICO_GOV'
    },

    # Brazil
    'lula': {
        'names': ['Lula', 'Lula da Silva', 'President Lula'],
        'countries': ['BR'],
        'role': 'PRESIDENT',
        'institution': 'BRAZIL_GOV'
    },
    'campos_neto': {
        'names': ['Campos Neto', 'Roberto Campos Neto', 'Governor Campos Neto'],
        'countries': ['BR'],
        'role': 'BCB_GOVERNOR',
        'institution': 'BCB'
    },
    'haddad': {
        'names': ['Haddad', 'Fernando Haddad'],
        'countries': ['BR'],
        'role': 'FINANCE_MIN',
        'institution': 'BRAZIL_GOV'
    },

    # Argentina
    'milei': {
        'names': ['Milei', 'Javier Milei', 'President Milei'],
        'countries': ['AR'],
        'role': 'PRESIDENT',
        'institution': 'ARGENTINA_GOV'
    },
    'caputo': {
        'names': ['Caputo', 'Luis Caputo'],
        'countries': ['AR'],
        'role': 'ECONOMY_MIN',
        'institution': 'ARGENTINA_GOV'
    },
    'bausili': {
        'names': ['Bausili', 'Santiago Bausili'],
        'countries': ['AR'],
        'role': 'BCRA_GOVERNOR',
        'institution': 'BCRA'
    },

    # Australia
    'bullock': {
        'names': ['Bullock', 'Michele Bullock', 'RBA Governor Bullock', 'Governor Bullock'],
        'countries': ['AU'],
        'role': 'RBA_GOVERNOR',
        'institution': 'RBA'
    },
    'albanese': {
        'names': ['Albanese', 'Anthony Albanese', 'PM Albanese'],
        'countries': ['AU'],
        'role': 'PM',
        'institution': 'AUSTRALIA_GOV'
    },
    'chalmers': {
        'names': ['Chalmers', 'Jim Chalmers'],
        'countries': ['AU'],
        'role': 'TREASURER',
        'institution': 'AUSTRALIA_GOV'
    },

    # New Zealand
    'orr': {
        'names': ['Orr', 'Adrian Orr', 'RBNZ Governor Orr', 'Governor Orr'],
        'countries': ['NZ'],
        'role': 'RBNZ_GOVERNOR',
        'institution': 'RBNZ'
    },
    'luxon': {
        'names': ['Luxon', 'Christopher Luxon', 'PM Luxon'],
        'countries': ['NZ'],
        'role': 'PM',
        'institution': 'NZ_GOV'
    },

    # China
    'xi': {
        'names': ['Xi', 'Xi Jinping', 'President Xi'],
        'countries': ['CN'],
        'role': 'PRESIDENT',
        'institution': 'CCP'
    },
    'li_qiang': {
        'names': ['Li Qiang', 'Premier Li'],
        'countries': ['CN'],
        'role': 'PREMIER',
        'institution': 'CHINA_GOV'
    },
    'pan': {
        'names': ['Pan Gongsheng', 'Pan', 'PBOC Governor Pan'],
        'countries': ['CN'],
        'role': 'PBOC_GOVERNOR',
        'institution': 'PBOC'
    },
    'he_lifeng': {
        'names': ['He Lifeng', 'Vice Premier He'],
        'countries': ['CN'],
        'role': 'VICE_PREMIER',
        'institution': 'CHINA_GOV'
    },

    # Taiwan
    'lai': {
        'names': ['Lai', 'Lai Ching-te', 'William Lai', 'President Lai'],
        'countries': ['TW'],
        'role': 'PRESIDENT',
        'institution': 'TAIWAN_GOV'
    },
    'yang': {
        'names': ['Yang Chin-long', 'Governor Yang'],
        'countries': ['TW'],
        'role': 'CBC_GOVERNOR',
        'institution': 'CBC'
    },

    # Russia
    'putin': {
        'names': ['Putin', 'Vladimir Putin', 'President Putin'],
        'countries': ['RU'],
        'role': 'PRESIDENT',
        'institution': 'KREMLIN'
    },
    'lavrov': {
        'names': ['Lavrov', 'Sergei Lavrov'],
        'countries': ['RU'],
        'role': 'FOREIGN_MIN',
        'institution': 'KREMLIN'
    },
    'nabiullina': {
        'names': ['Nabiullina', 'Elvira Nabiullina', 'Governor Nabiullina'],
        'countries': ['RU'],
        'role': 'CBR_GOVERNOR',
        'institution': 'CBR'
    },

    # Ukraine
    'zelensky': {
        'names': ['Zelensky', 'Volodymyr Zelensky', 'President Zelensky'],
        'countries': ['UA'],
        'role': 'PRESIDENT',
        'institution': 'UKRAINE_GOV'
    },
    'shevchenko': {
        'names': ['Shevchenko', 'Andriy Shevchenko', 'Governor Shevchenko'],
        'countries': ['UA'],
        'role': 'NBU_GOVERNOR',
        'institution': 'NBU'
    },

    # Other Key Figures
    'mbs': {
        'names': ['MBS', 'Mohammed bin Salman', 'Crown Prince', 'Prince Mohammed'],
        'countries': ['SA'],
        'role': 'CROWN_PRINCE',
        'institution': 'SAUDI_GOV'
    },
    'erdogan': {
        'names': ['Erdogan', 'Recep Erdogan', 'President Erdogan'],
        'countries': ['TR'],
        'role': 'PRESIDENT',
        'institution': 'TURKEY_GOV'
    },
    'netanyahu': {
        'names': ['Netanyahu', 'Benjamin Netanyahu', 'Bibi', 'PM Netanyahu'],
        'countries': ['IL'],
        'role': 'PM',
        'institution': 'ISRAEL_GOV'
    },
    'modi': {
        'names': ['Modi', 'Narendra Modi', 'PM Modi'],
        'countries': ['IN'],
        'role': 'PM',
        'institution': 'INDIA_GOV'
    },
    'das': {
        'names': ['Das', 'Shaktikanta Das', 'Governor Das'],
        'countries': ['IN'],
        'role': 'RBI_GOVERNOR',
        'institution': 'RBI'
    },
}


# =============================================================================
# INSTITUTION KEYWORDS (detect institutions without requiring a leader mention)
# =============================================================================

INSTITUTION_KEYWORDS = {
    'FED': ['federal reserve', 'federal open market committee', 'the fed',
            'fed holds', 'fed cuts', 'fed raises', 'fed chief', 'fed governor',
            'fed chair', 'fomc', 'fed officials', 'fed meeting', 'fed policy',
            'fed signals', 'fed rate', 'fed pick', 'fed nominee', 'dovish fed',
            'hawkish fed', 'ahead of fed', 'fed minutes', 'fed statement'],
    'ECB': ['european central bank', 'ecb'],
    'BOE': ['bank of england', 'boe'],
    'BOJ': ['bank of japan', 'boj'],
    'BOC': ['bank of canada', 'boc'],
    'RBA': ['reserve bank of australia', 'rba'],
    'RBNZ': ['reserve bank of new zealand', 'rbnz'],
    'PBOC': ['people\'s bank of china', 'pboc'],
    'BANXICO': ['banxico', 'banco de mexico'],
    'BCB': ['banco central', 'bcb'],
    'WHITE_HOUSE': ['white house'],
    'TREASURY': ['u.s. treasury', 'treasury department', 'treasury secretary'],
    'IMF': ['international monetary fund', 'imf'],
}


# =============================================================================
# ACTION KEYWORDS
# =============================================================================

CRITICAL_ACTIONS = [
    'announces', 'announced', 'signs', 'signed', 'orders', 'ordered',
    'threatens', 'threatened', 'fires', 'fired', 'invades', 'invaded',
    'attacks', 'attacked', 'launches', 'launched', 'sanctions',
    'declares', 'declared', 'emergency', 'immediately', 'effective immediately',
    'executive order', 'martial law', 'deploys troops', 'closes border',
    'freezes assets', 'expels', 'expelled', 'withdraws from', 'breaking'
]

HIGH_ACTIONS = [
    'considers', 'considering', 'plans', 'planning', 'proposes', 'proposed',
    'warns', 'warning', 'signals', 'suggests', 'suggested', 'reviewing',
    'expected to', 'may', 'could', 'might', 'discussing', 'negotiating',
    'meeting with', 'preparing', 'drafting', 'will likely', 'sources say',
    'reportedly', 'according to sources'
]


# =============================================================================
# EVENT CATEGORIZATION
# =============================================================================

EVENT_TYPES = {
    'RATE_DECISION': [
        'rate decision', 'rate hike', 'rate cut', 'holds rates', 'keeps rates',
        'basis points', 'bps', 'interest rate decision', 'monetary policy decision',
        'policy rate', 'raises rates', 'lowers rates', 'rate unchanged',
        'fomc statement', 'fomc', 'rate steady', 'holds rate', 'kept rate',
        'rate announcement', 'cuts rate', 'raises rate', 'hiked rate',
    ],
    'TRADE_POLICY': [
        'tariff', 'tariffs', 'trade war', 'trade deal', 'trade agreement',
        'USMCA', 'import duty', 'export ban', 'trade restrictions',
        'trade negotiations', 'customs duty', 'customs duties', 'quotas'
    ],
    'SANCTIONS': [
        'sanctions', 'sanctioned', 'embargo', 'asset freeze', 'freezing assets',
        'blacklist', 'OFAC', 'economic sanctions', 'financial sanctions'
    ],
    'MILITARY': [
        'troops', 'military', 'invasion', 'invades', 'strike', 'strikes',
        'missile', 'missiles', 'NATO', 'defense', 'forces', 'army',
        'deployment', 'offensive', 'counteroffensive'
    ],
    'ELECTION': [
        'election', 'elections', 'vote', 'voting', 'poll', 'polls',
        'campaign', 'candidate', 'ballot', 'referendum'
    ],
    'ECONOMIC_DATA': [
        'GDP', 'gross domestic product', 'CPI', 'consumer price index',
        'inflation', 'jobs', 'employment', 'payroll', 'unemployment',
        'PMI', 'retail sales', 'consumer spending', 'PPI'
    ],
    'MARKET_MOVE': [
        'crash', 'crashes', 'surge', 'surges', 'plunge', 'plunges',
        'rally', 'rallies', 'selloff', 'sell-off', 'circuit breaker',
        'volatility', 'correction'
    ],
    'CURRENCY': [
        'intervention', 'currency intervention', 'devaluation', 'revaluation',
        'currency', 'FX', 'forex', 'exchange rate', 'peg'
    ],
    'DEBT_CREDIT': [
        'default', 'defaults', 'downgrade', 'downgrades', 'upgrade', 'upgrades',
        'rating', 'credit rating', 'bond', 'bonds', 'yield', 'yields',
        'spread', 'spreads', 'debt ceiling'
    ],
    'DISASTER': [
        'hurricane', 'earthquake', 'flood', 'flooding', 'wildfire',
        'tsunami', 'disaster', 'natural disaster', 'emergency'
    ],
}


# =============================================================================
# GEOPOLITICAL CRITICAL KEYWORDS
# =============================================================================

GEOPOLITICAL_CRITICAL = [
    'ISW', 'Institute for Study of War', 'invasion', 'invades',
    'offensive', 'counteroffensive', 'troops deployed', 'military buildup',
    'nuclear', 'nuclear weapons', 'ICBM', 'missile test', 'ballistic missile',
    'NATO Article 5', 'Taiwan Strait', 'South China Sea', 'coup',
    'regime change', 'martial law', 'state of emergency',
    'declaration of war', 'ceasefire', 'peace talks'
]


# =============================================================================
# COUNTRY KEYWORDS (for backward compatibility and tagging)
# =============================================================================

COUNTRY_KEYWORDS = {
    'US': [
        'united states', 'u.s.', 'usa', 'america', 'federal reserve',
        'fed', 'treasury', 'dollar', 'washington', 'white house'
    ],
    'JP': [
        'japan', 'japanese', 'tokyo', 'yen', 'boj', 'bank of japan', 'nikkei'
    ],
    'CA': [
        'canada', 'canadian', 'ottawa', 'cad', 'bank of canada'
    ],
    'MX': [
        'mexico', 'mexican', 'peso', 'banxico', 'mexico city'
    ],
    'EU': [
        'europe', 'european', 'euro', 'ecb', 'european central bank',
        'brussels', 'eurozone', 'european union'
    ],
    'GB': [
        'britain', 'british', 'uk', 'united kingdom', 'pound', 'sterling',
        'boe', 'bank of england', 'london'
    ],
    'CN': [
        'china', 'chinese', 'yuan', 'renminbi', 'pboc', 'beijing'
    ],
    'TW': [
        'taiwan', 'taiwanese', 'taipei'
    ],
    'RU': [
        'russia', 'russian', 'moscow', 'ruble', 'kremlin'
    ],
    'UA': [
        'ukraine', 'ukrainian', 'kyiv', 'kiev', 'hryvnia'
    ],
    'BR': [
        'brazil', 'brazilian', 'real', 'brasilia'
    ],
    'AR': [
        'argentina', 'argentinian', 'argentine', 'peso', 'buenos aires'
    ],
    'AU': [
        'australia', 'australian', 'sydney', 'aud', 'rba'
    ],
    'NZ': [
        'new zealand', 'nz', 'wellington', 'nzd', 'rbnz'
    ],
    'IN': [
        'india', 'indian', 'rupee', 'delhi', 'mumbai', 'rbi'
    ],
    'SA': [
        'saudi', 'saudi arabia', 'riyadh', 'riyal'
    ],
    'TR': [
        'turkey', 'turkish', 'ankara', 'lira'
    ],
    'IL': [
        'israel', 'israeli', 'tel aviv', 'jerusalem', 'shekel'
    ],
    'DE': [
        'germany', 'german', 'berlin', 'bundesbank'
    ],
    'FR': [
        'france', 'french', 'paris'
    ],
    'IT': [
        'italy', 'italian', 'rome'
    ],
    'GLOBAL': [
        'global', 'worldwide', 'international', 'world'
    ]
}


# =============================================================================
# SEVERITY KEYWORDS (for backward compatibility)
# =============================================================================

CRITICAL_KEYWORDS = [
    'crisis', 'crash', 'collapse', 'emergency', 'panic', 'default',
    'recession confirmed', 'war declared', 'invasion', 'nuclear',
    'catastrophe', 'catastrophic'
] + GEOPOLITICAL_CRITICAL

HIGH_KEYWORDS = [
    'tariff', 'trade war', 'rate cut', 'rate hike', 'recession',
    'inflation surge', 'employment crisis', 'debt ceiling', 'shutdown',
    'sanction', 'breaking', 'urgent', 'alert', 'warning'
] + HIGH_ACTIONS

MEDIUM_KEYWORDS = [
    'gdp', 'unemployment', 'inflation', 'interest rate', 'central bank',
    'policy', 'forecast', 'outlook', 'concern', 'risk'
]


# =============================================================================
# CATEGORY KEYWORDS (for backward compatibility)
# =============================================================================

CATEGORY_KEYWORDS = {
    'ECON': [
        'gdp', 'employment', 'jobs', 'unemployment', 'inflation',
        'cpi', 'ppi', 'retail sales', 'consumer spending'
    ],
    'FX': [
        'currency', 'dollar', 'euro', 'yen', 'pound', 'forex',
        'exchange rate', 'fx'
    ],
    'POLITICAL': [
        'election', 'congress', 'senate', 'president', 'government',
        'policy', 'tariff', 'trade', 'parliament'
    ],
    'CREDIT': [
        'bond', 'debt', 'credit', 'treasury', 'yield', 'spread', 'default'
    ],
    'CENTRAL_BANK': [
        'fed', 'federal reserve', 'ecb', 'boj', 'boe', 'central bank',
        'interest rate', 'monetary policy', 'rba', 'boc', 'rbnz'
    ],
    'GEOPOLITICAL': [
        'war', 'conflict', 'military', 'defense', 'sanctions', 'nato',
        'geopolitical', 'security'
    ]
}