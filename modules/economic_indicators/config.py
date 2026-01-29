"""
Economic Indicators Configuration

All FRED series IDs organized by report group.
"""

# Employment Situation - Establishment Survey
ESTABLISHMENT_SURVEY = {
    'PAYEMS': {'name': 'Total Nonfarm', 'units': 'thousands', 'frequency': 'monthly'},
    'USPRIV': {'name': 'Total Private', 'units': 'thousands', 'frequency': 'monthly'},
    'USGOOD': {'name': 'Goods-Producing', 'units': 'thousands', 'frequency': 'monthly'},
    'CES1021000001': {'name': 'Mining and Logging', 'units': 'thousands', 'frequency': 'monthly'},
    'USCONS': {'name': 'Construction', 'units': 'thousands', 'frequency': 'monthly'},
    'MANEMP': {'name': 'Manufacturing', 'units': 'thousands', 'frequency': 'monthly'},
    'DMANEMP': {'name': 'Durable Goods', 'units': 'thousands', 'frequency': 'monthly'},
    'CES3133600101': {'name': 'Motor Vehicles and Parts', 'units': 'thousands', 'frequency': 'monthly'},
    'NDMANEMP': {'name': 'Nondurable Goods', 'units': 'thousands', 'frequency': 'monthly'},
    'SRVPRD': {'name': 'Private Service-Providing', 'units': 'thousands', 'frequency': 'monthly'},
    'USWTRADE': {'name': 'Wholesale Trade', 'units': 'thousands', 'frequency': 'monthly'},
    'USTRADE': {'name': 'Retail Trade', 'units': 'thousands', 'frequency': 'monthly'},
    'CES4300000001': {'name': 'Transportation and Warehousing', 'units': 'thousands', 'frequency': 'monthly'},
    'CES4422000001': {'name': 'Utilities', 'units': 'thousands', 'frequency': 'monthly'},
    'USINFO': {'name': 'Information', 'units': 'thousands', 'frequency': 'monthly'},
    'USFIRE': {'name': 'Financial Activities', 'units': 'thousands', 'frequency': 'monthly'},
    'USPBS': {'name': 'Professional and Business Services', 'units': 'thousands', 'frequency': 'monthly'},
    'TEMPHELPS': {'name': 'Temporary Help Services', 'units': 'thousands', 'frequency': 'monthly'},
    'USEHS': {'name': 'Private Education and Health Services', 'units': 'thousands', 'frequency': 'monthly'},
    'CES6562000101': {'name': 'Health Care and Social Assistance', 'units': 'thousands', 'frequency': 'monthly'},
    'USLAH': {'name': 'Leisure and Hospitality', 'units': 'thousands', 'frequency': 'monthly'},
    'CES0500000003': {'name': 'Average Hourly Earnings (Private)', 'units': 'dollars', 'frequency': 'monthly'},
    'AWHAETP': {'name': 'Average Weekly Hours (Private)', 'units': 'hours', 'frequency': 'monthly'},
}

# Employment Situation - Household Survey
HOUSEHOLD_SURVEY = {
    'CNP16OV': {'name': 'Civilian Noninstitutional Population', 'units': 'thousands', 'frequency': 'monthly'},
    'CLF16OV': {'name': 'Civilian Labor Force', 'units': 'thousands', 'frequency': 'monthly'},
    'CIVPART': {'name': 'Labor Force Participation Rate', 'units': 'percent', 'frequency': 'monthly'},
    'CE16OV': {'name': 'Employed', 'units': 'thousands', 'frequency': 'monthly'},
    'EMRATIO': {'name': 'Employment-Population Ratio', 'units': 'percent', 'frequency': 'monthly'},
    'UNEMPLOY': {'name': 'Unemployed', 'units': 'thousands', 'frequency': 'monthly'},
    'UNRATE': {'name': 'Unemployment Rate', 'units': 'percent', 'frequency': 'monthly'},
}

# Unemployment Claims
UNEMPLOYMENT_CLAIMS = {
    'ICSA': {'name': 'Initial Jobless Claims', 'units': 'thousands', 'frequency': 'weekly'},
    'CCSA': {'name': 'Continuing Claims', 'units': 'thousands', 'frequency': 'weekly'},
}

# CPI Report
CPI_REPORT = {
    'CPIAUCSL': {'name': 'CPI All Items', 'units': 'index', 'frequency': 'monthly'},
    'CPILFESL': {'name': 'Core CPI (Less Food & Energy)', 'units': 'index', 'frequency': 'monthly'},
    'CUSR0000SAH1': {'name': 'CPI Shelter', 'units': 'index', 'frequency': 'monthly'},
    'CUSR0000SEHC': {'name': 'Owners Equivalent Rent', 'units': 'index', 'frequency': 'monthly'},
    'CUSR0000SEHA': {'name': 'Rent of Primary Residence', 'units': 'index', 'frequency': 'monthly'},
    'CUSR0000SAS4': {'name': 'Transportation Services', 'units': 'index', 'frequency': 'monthly'},
    'CUSR0000SETD': {'name': 'Motor Vehicle Maintenance & Repair', 'units': 'index', 'frequency': 'monthly'},
    'CUSR0000SETE': {'name': 'Motor Vehicle Insurance', 'units': 'index', 'frequency': 'monthly'},
    'CUSR0000SETA01': {'name': 'New Vehicles', 'units': 'index', 'frequency': 'monthly'},
    'CUSR0000SETA02': {'name': 'Used Cars and Trucks', 'units': 'index', 'frequency': 'monthly'},
    'CUSR0000SAH3': {'name': 'Household Furnishings & Supplies', 'units': 'index', 'frequency': 'monthly'},
    'CUSR0000SEHF': {'name': 'Major Appliances', 'units': 'index', 'frequency': 'monthly'},
    'CUSR0000SETB': {'name': 'Motor Vehicle Parts & Equipment', 'units': 'index', 'frequency': 'monthly'},
    'CPIENGSL': {'name': 'CPI Energy', 'units': 'index', 'frequency': 'monthly'},
    'CPIUFDSL': {'name': 'CPI Food', 'units': 'index', 'frequency': 'monthly'},
    'CUSR0000SASLE': {'name': 'Services Less Rent of Shelter', 'units': 'index', 'frequency': 'monthly'},
    'CUUR0000SAD': {'name': 'CPI Durables', 'units': 'index', 'frequency': 'monthly'},
    'CUUR0000SAN': {'name': 'CPI Nondurables', 'units': 'index', 'frequency': 'monthly'},
}

# PPI Report
PPI_REPORT = {
    'PPIACO': {'name': 'PPI All Commodities', 'units': 'index', 'frequency': 'monthly'},
    'PPIFES': {'name': 'PPI Final Demand', 'units': 'index', 'frequency': 'monthly'},
    'PPIFGS': {'name': 'PPI Final Demand Goods', 'units': 'index', 'frequency': 'monthly'},
    'PPIFDS': {'name': 'PPI Final Demand Services', 'units': 'index', 'frequency': 'monthly'},
    'WPSFD4111': {'name': 'PPI Core (Less Food & Energy)', 'units': 'index', 'frequency': 'monthly'},
    'PPITMS': {'name': 'PPI Trade Services (Final Demand)', 'units': 'index', 'frequency': 'monthly'},
    'PPIWTS': {'name': 'PPI Wholesale & Retail Margins', 'units': 'index', 'frequency': 'monthly'},
    'PCU423830423830': {'name': 'Machinery & Equipment Wholesaling Margins', 'units': 'index', 'frequency': 'monthly'},
    'PPITRS': {'name': 'PPI Transportation & Warehousing', 'units': 'index', 'frequency': 'monthly'},
    'PPIFFS': {'name': 'PPI Financial Services', 'units': 'index', 'frequency': 'monthly'},
    'PPIDCG': {'name': 'PPI Durable Consumer Goods', 'units': 'index', 'frequency': 'monthly'},
    'PPIITM': {'name': 'PPI Processed Inputs (Intermediate)', 'units': 'index', 'frequency': 'monthly'},
    'PPIIDC': {'name': 'PPI Intermediate Services', 'units': 'index', 'frequency': 'monthly'},
}

# PCE Report
PCE_REPORT = {
    'PCEPI': {'name': 'PCE Price Index', 'units': 'index', 'frequency': 'monthly'},
    'PCEPILFE': {'name': 'Core PCE (Less Food & Energy)', 'units': 'index', 'frequency': 'monthly'},
    'PCE': {'name': 'Personal Consumption Expenditures', 'units': 'billions', 'frequency': 'monthly'},
    'PI': {'name': 'Personal Income', 'units': 'billions', 'frequency': 'monthly'},
    'PSAVERT': {'name': 'Personal Savings Rate', 'units': 'percent', 'frequency': 'monthly'},
}

# GDP Report
GDP_REPORT = {
    'GDPC1': {'name': 'Real GDP', 'units': 'billions', 'frequency': 'quarterly'},
    'GDP': {'name': 'Nominal GDP', 'units': 'billions', 'frequency': 'quarterly'},
    'A191RL1Q225SBEA': {'name': 'Real GDP Growth (SAAR)', 'units': 'percent', 'frequency': 'quarterly'},
}

# Other Key Indicators
OTHER_INDICATORS = {
    'DGS10': {'name': '10-Year Treasury Yield', 'units': 'percent', 'frequency': 'daily'},
    'DGS2': {'name': '2-Year Treasury Yield', 'units': 'percent', 'frequency': 'daily'},
    'T10Y2Y': {'name': '10Y-2Y Treasury Spread', 'units': 'percent', 'frequency': 'daily'},
    'FEDFUNDS': {'name': 'Federal Funds Rate', 'units': 'percent', 'frequency': 'monthly'},
    'RSXFS': {'name': 'Retail Sales Ex Food Services', 'units': 'millions', 'frequency': 'monthly'},
    'UMCSENT': {'name': 'Consumer Sentiment (UMich)', 'units': 'index', 'frequency': 'monthly'},
    'HOUST': {'name': 'Housing Starts', 'units': 'thousands', 'frequency': 'monthly'},
    'INDPRO': {'name': 'Industrial Production', 'units': 'index', 'frequency': 'monthly'},
}

# Master mapping of report groups
REPORT_GROUPS = {
    'Employment Situation': {
        'Establishment Survey': ESTABLISHMENT_SURVEY,
        'Household Survey': HOUSEHOLD_SURVEY,
    },
    'Unemployment Claims': {
        'Weekly Claims': UNEMPLOYMENT_CLAIMS,
    },
    'CPI Report': {
        'Consumer Price Index': CPI_REPORT,
    },
    'PPI Report': {
        'Producer Price Index': PPI_REPORT,
    },
    'PCE Report': {
        'Personal Consumption': PCE_REPORT,
    },
    'GDP Report': {
        'Gross Domestic Product': GDP_REPORT,
    },
    'Other Indicators': {
        'Key Indicators': OTHER_INDICATORS,
    },
}

# Pre-configured dashboards
DASHBOARDS = {
    'inflation': {
        'name': 'Inflation Dashboard',
        'series': ['CPIAUCSL', 'CPILFESL', 'PCEPI', 'PCEPILFE', 'CUSR0000SASLE', 'CUSR0000SAH1'],
        'default_transform': 'yoy_percent'
    },
    'labor': {
        'name': 'Labor Market Dashboard',
        'series': ['PAYEMS', 'UNRATE', 'CIVPART', 'CES0500000003', 'AWHAETP', 'TEMPHELPS'],
        'default_transform': 'raw'
    },
    'claims': {
        'name': 'Jobless Claims Dashboard',
        'series': ['ICSA', 'CCSA'],
        'default_transform': 'raw',
        'default_ma': [4]  # 4-week moving average
    },
    'gdp': {
        'name': 'GDP Dashboard',
        'series': ['GDPC1', 'A191RL1Q225SBEA', 'PCE', 'PI'],
        'default_transform': 'raw'
    },
}


def get_all_indicators() -> dict:
    """Returns flat dict of all indicators with their metadata"""
    all_indicators = {}
    for report_name, categories in REPORT_GROUPS.items():
        for category_name, indicators in categories.items():
            for series_id, config in indicators.items():
                all_indicators[series_id] = {
                    **config,
                    'series_id': series_id,
                    'report_group': report_name,
                    'category': category_name,
                }
    return all_indicators


def get_indicator_count() -> int:
    """Returns total number of indicators configured"""
    return len(get_all_indicators())
