"""
Recession Model Feature Engineering — single source of truth.

Houses the FRED series configuration and the feature-engineering pipeline
used by both training (`build_dataset`) and live prediction
(`build_current_features`). Kept as module-level functions so feature logic
lives in one place, not split across data-builder methods.
"""

from typing import List

import numpy as np
import pandas as pd


# ──────────────────────────────────────────────
# FRED Series Configuration
# ──────────────────────────────────────────────

# Tier 1: Available from 1960s — core macro indicators
TIER1_SERIES = {
    "UNRATE": "Unemployment Rate",
    "PAYEMS": "Total Nonfarm Payrolls",
    "INDPRO": "Industrial Production Index",
    "CPIAUCSL": "CPI All Items",
    "FEDFUNDS": "Federal Funds Rate",
    "HOUST": "Housing Starts",
    "PERMIT": "Building Permits",
    "M2SL": "M2 Money Supply",
    "USALOLITONOSTSAM": "OECD Composite Leading Indicator",
    "AWHMAN": "Avg Weekly Hours Manufacturing",
    "M1SL": "M1 Money Supply",
    "PPIACO": "PPI All Commodities",
    "WHLSLRIMSA": "Wholesale Inventories/Sales Ratio",
    "CIVPART": "Labor Force Participation Rate",
    "EMRATIO": "Employment-Population Ratio",
    "LNS12300060": "Prime-Age (25-54) Employment-Population Ratio",
}

# Tier 2: Available from late 1960s-1970s
TIER2_SERIES = {
    "UMCSENT": "U of Michigan Consumer Sentiment",
    "ICSA": "Initial Jobless Claims",
    "W875RX1": "Real Personal Income ex Transfers",
    "TOTALSL": "Total Consumer Credit Outstanding",
    "DGORDER": "Durable Goods New Orders",
    "NEWORDER": "Manufacturers New Orders",
    "CPILFESL": "Core CPI (Less Food & Energy)",
    "PCEPILFE": "Core PCE Price Index",
    "BOGZ1FL072052006Q": "Household Debt Service Ratio",
}

# Tier 3: Available from mid-1970s+
TIER3_SERIES = {
    "DGS10": "10-Year Treasury Yield",
    "DGS2": "2-Year Treasury Yield",
    "T10Y2Y": "10Y-2Y Treasury Spread",
    "DGS3MO": "3-Month Treasury Yield",
    "NFCI": "Chicago Fed National Financial Conditions",
    "ANFCI": "Adjusted NFCI",
    "TEDRATE": "TED Spread (3mo LIBOR - 3mo T-bill)",
    "VIXCLS": "VIX Volatility Index",
    "U6RATE": "U-6 Broad Unemployment Rate",
}

# Tier 4: Available from 1980s+
TIER4_SERIES = {
    "T10Y3M": "10Y-3M Treasury Spread",
    "BAA10Y": "BAA Corp Bond - 10Y Treasury Spread",
    "BAAFFM": "BAA Corp Bond - Fed Funds Spread",
    "DCOILWTICO": "WTI Crude Oil Price",
    "DTWEXBGS": "Trade Weighted US Dollar Index (Broad)",
    "STLFSI2": "St Louis Fed Financial Stress Index",
    "JTSJOL": "Job Openings (JOLTS)",
    "JTSQUR": "Quits Rate (JOLTS)",
}

# All series combined
FEATURE_SERIES = {**TIER1_SERIES, **TIER2_SERIES, **TIER3_SERIES, **TIER4_SERIES}

# NBER recession indicator
RECESSION_SERIES = "USREC"

# How far back to fetch
START_DATE = "1959-01-01"

# Forward-looking horizons (months)
HORIZONS = [3, 6, 12]

# Core features that must be non-null (Tier 1 only)
CORE_REQUIRED = {"UNRATE", "PAYEMS", "INDPRO", "CPIAUCSL", "FEDFUNDS"}


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create 80+ derived features from raw series."""

    # ════════════════════════════════════════════
    # YIELD CURVE & INTEREST RATES
    # ════════════════════════════════════════════

    for spread_col in ["T10Y2Y", "T10Y3M"]:
        if spread_col in df.columns:
            prefix = spread_col.lower()
            df[f"{prefix}_ma3"] = df[spread_col].rolling(3).mean()
            df[f"{prefix}_ma6"] = df[spread_col].rolling(6).mean()
            df[f"{prefix}_ma12"] = df[spread_col].rolling(12).mean()
            df[f"{prefix}_chg3"] = df[spread_col].diff(3)
            df[f"{prefix}_chg6"] = df[spread_col].diff(6)
            df[f"{prefix}_chg12"] = df[spread_col].diff(12)
            # Months inverted (below zero)
            df[f"{prefix}_inv_months"] = (
                (df[spread_col] < 0).rolling(12).sum()
            )
            # Spread acceleration
            chg3 = df[spread_col].diff(3)
            df[f"{prefix}_accel"] = chg3.diff(3)

    # Construct 10Y-3M from components if T10Y3M not available
    if "DGS10" in df.columns and "DGS3MO" in df.columns and "T10Y3M" not in df.columns:
        df["T10Y3M"] = df["DGS10"] - df["DGS3MO"]
        for suffix in ["_ma3", "_ma6", "_chg3", "_chg6"]:
            col = f"t10y3m{suffix}"
            if suffix.startswith("_ma"):
                w = int(suffix.replace("_ma", ""))
                df[col] = df["T10Y3M"].rolling(w).mean()
            else:
                w = int(suffix.replace("_chg", ""))
                df[col] = df["T10Y3M"].diff(w)

    # Real yield (10Y minus CPI YoY)
    if "DGS10" in df.columns and "CPIAUCSL" in df.columns:
        cpi_yoy = df["CPIAUCSL"].pct_change(12) * 100
        df["real_10y"] = df["DGS10"] - cpi_yoy

    # Term premium proxy (10Y - 2Y - historical avg)
    if "T10Y2Y" in df.columns:
        df["spread_10y2y_zscore"] = (
            (df["T10Y2Y"] - df["T10Y2Y"].rolling(60).mean())
            / df["T10Y2Y"].rolling(60).std().replace(0, 1)
        )

    # ════════════════════════════════════════════
    # CREDIT SPREADS & FINANCIAL CONDITIONS
    # ════════════════════════════════════════════

    for credit_col in ["BAA10Y", "BAAFFM"]:
        if credit_col in df.columns:
            prefix = credit_col.lower()
            df[f"{prefix}_ma3"] = df[credit_col].rolling(3).mean()
            df[f"{prefix}_ma6"] = df[credit_col].rolling(6).mean()
            df[f"{prefix}_chg3"] = df[credit_col].diff(3)
            df[f"{prefix}_chg6"] = df[credit_col].diff(6)
            df[f"{prefix}_chg12"] = df[credit_col].diff(12)
            # Z-score (how extreme vs 5-year history)
            df[f"{prefix}_zscore"] = (
                (df[credit_col] - df[credit_col].rolling(60).mean())
                / df[credit_col].rolling(60).std().replace(0, 1)
            )

    # TED spread
    if "TEDRATE" in df.columns:
        df["ted_ma3"] = df["TEDRATE"].rolling(3).mean()
        df["ted_chg3"] = df["TEDRATE"].diff(3)

    # Financial conditions
    for fci_col in ["NFCI", "ANFCI", "STLFSI2"]:
        if fci_col in df.columns:
            prefix = fci_col.lower()
            df[f"{prefix}_ma3"] = df[fci_col].rolling(3).mean()
            df[f"{prefix}_chg3"] = df[fci_col].diff(3)
            df[f"{prefix}_chg6"] = df[fci_col].diff(6)

    # VIX
    if "VIXCLS" in df.columns:
        df["vix_ma3"] = df["VIXCLS"].rolling(3).mean()
        df["vix_chg3"] = df["VIXCLS"].diff(3)
        df["vix_zscore"] = (
            (df["VIXCLS"] - df["VIXCLS"].rolling(60).mean())
            / df["VIXCLS"].rolling(60).std().replace(0, 1)
        )

    # ════════════════════════════════════════════
    # LABOR MARKET
    # ════════════════════════════════════════════

    if "UNRATE" in df.columns:
        df["unrate_chg1"] = df["UNRATE"].diff(1)
        df["unrate_chg3"] = df["UNRATE"].diff(3)
        df["unrate_chg6"] = df["UNRATE"].diff(6)
        df["unrate_chg12"] = df["UNRATE"].diff(12)
        df["unrate_ma3"] = df["UNRATE"].rolling(3).mean()
        df["unrate_ma6"] = df["UNRATE"].rolling(6).mean()
        df["unrate_min12"] = df["UNRATE"].rolling(12).min()
        # Sahm Rule proxy
        df["sahm_proxy"] = df["unrate_ma3"] - df["unrate_min12"]
        # Z-score
        df["unrate_zscore"] = (
            (df["UNRATE"] - df["UNRATE"].rolling(120).mean())
            / df["UNRATE"].rolling(120).std().replace(0, 1)
        )
        # Acceleration (second derivative)
        df["unrate_accel"] = df["unrate_chg3"].diff(3)

    if "ICSA" in df.columns:
        df["icsa_ma4"] = df["ICSA"].rolling(4).mean()
        df["icsa_ma13"] = df["ICSA"].rolling(13).mean()
        df["icsa_chg3"] = df["ICSA"].pct_change(3) * 100
        df["icsa_chg6"] = df["ICSA"].pct_change(6) * 100
        df["icsa_chg12"] = df["ICSA"].pct_change(12) * 100
        # Claims above/below trend
        df["icsa_vs_trend"] = df["ICSA"] / df["icsa_ma13"].replace(0, np.nan) - 1

    if "PAYEMS" in df.columns:
        df["payems_chg1"] = df["PAYEMS"].diff(1)
        df["payems_chg3"] = df["PAYEMS"].diff(3)
        df["payems_chg6"] = df["PAYEMS"].diff(6)
        df["payems_chg12"] = df["PAYEMS"].diff(12)
        df["payems_ma3"] = df["payems_chg1"].rolling(3).mean()
        df["payems_ma6"] = df["payems_chg1"].rolling(6).mean()
        df["payems_yoy_pct"] = df["PAYEMS"].pct_change(12) * 100
        # Payrolls deceleration
        df["payems_accel"] = df["payems_ma3"].diff(3)

    if "AWHMAN" in df.columns:
        df["awhman_chg3"] = df["AWHMAN"].diff(3)
        df["awhman_chg6"] = df["AWHMAN"].diff(6)
        df["awhman_ma6"] = df["AWHMAN"].rolling(6).mean()

    # ════════════════════════════════════════════
    # LABOR SUPPLY (participation, broad unemployment)
    # ════════════════════════════════════════════

    if "CIVPART" in df.columns:
        df["civpart_chg3"] = df["CIVPART"].diff(3)
        df["civpart_chg6"] = df["CIVPART"].diff(6)
        df["civpart_chg12"] = df["CIVPART"].diff(12)
        df["civpart_ma6"] = df["CIVPART"].rolling(6).mean()
        df["civpart_ma12"] = df["CIVPART"].rolling(12).mean()

    if "EMRATIO" in df.columns:
        df["emratio_chg3"] = df["EMRATIO"].diff(3)
        df["emratio_chg6"] = df["EMRATIO"].diff(6)
        df["emratio_chg12"] = df["EMRATIO"].diff(12)
        df["emratio_ma6"] = df["EMRATIO"].rolling(6).mean()

    if "LNS12300060" in df.columns:
        df["primeage_epop_chg3"] = df["LNS12300060"].diff(3)
        df["primeage_epop_chg6"] = df["LNS12300060"].diff(6)
        df["primeage_epop_chg12"] = df["LNS12300060"].diff(12)
        df["primeage_epop_ma6"] = df["LNS12300060"].rolling(6).mean()

    if "U6RATE" in df.columns:
        df["u6_chg3"] = df["U6RATE"].diff(3)
        df["u6_chg6"] = df["U6RATE"].diff(6)
        df["u6_chg12"] = df["U6RATE"].diff(12)
        # U6-U3 gap: rising gap = more hidden slack
        if "UNRATE" in df.columns:
            df["u6_u3_gap"] = df["U6RATE"] - df["UNRATE"]
            df["u6_u3_gap_chg6"] = df["u6_u3_gap"].diff(6)

    if "JTSJOL" in df.columns:
        df["jolts_openings_chg3"] = df["JTSJOL"].pct_change(3) * 100
        df["jolts_openings_chg6"] = df["JTSJOL"].pct_change(6) * 100
        df["jolts_openings_chg12"] = df["JTSJOL"].pct_change(12) * 100
        df["jolts_openings_ma6"] = df["JTSJOL"].rolling(6).mean()

    if "JTSQUR" in df.columns:
        df["quits_rate_chg3"] = df["JTSQUR"].diff(3)
        df["quits_rate_chg6"] = df["JTSQUR"].diff(6)
        df["quits_rate_chg12"] = df["JTSQUR"].diff(12)

    # ════════════════════════════════════════════
    # PRODUCTION & BUSINESS ACTIVITY
    # ════════════════════════════════════════════

    if "INDPRO" in df.columns:
        df["indpro_yoy"] = df["INDPRO"].pct_change(12) * 100
        df["indpro_mom"] = df["INDPRO"].pct_change(1) * 100
        df["indpro_chg3"] = df["INDPRO"].pct_change(3) * 100
        df["indpro_chg6"] = df["INDPRO"].pct_change(6) * 100
        df["indpro_ma6"] = df["indpro_mom"].rolling(6).mean()
        df["indpro_ma12"] = df["indpro_mom"].rolling(12).mean()
        # Negative growth streak
        df["indpro_neg_months"] = (df["indpro_mom"] < 0).rolling(6).sum()

    if "DGORDER" in df.columns:
        df["dgorder_yoy"] = df["DGORDER"].pct_change(12) * 100
        df["dgorder_chg3"] = df["DGORDER"].pct_change(3) * 100
        df["dgorder_chg6"] = df["DGORDER"].pct_change(6) * 100
        df["dgorder_ma3"] = df["dgorder_chg3"].rolling(3).mean()

    if "NEWORDER" in df.columns:
        df["neworder_yoy"] = df["NEWORDER"].pct_change(12) * 100
        df["neworder_chg3"] = df["NEWORDER"].pct_change(3) * 100

    # ════════════════════════════════════════════
    # HOUSING
    # ════════════════════════════════════════════

    if "HOUST" in df.columns:
        df["houst_yoy"] = df["HOUST"].pct_change(12) * 100
        df["houst_chg3"] = df["HOUST"].pct_change(3) * 100
        df["houst_chg6"] = df["HOUST"].pct_change(6) * 100
        df["houst_ma6"] = df["HOUST"].rolling(6).mean()
        df["houst_ma12"] = df["HOUST"].rolling(12).mean()
        # Housing collapse signal
        if "houst_ma6" in df.columns and "houst_ma12" in df.columns:
            df["houst_ma_cross"] = df["houst_ma6"] / df["houst_ma12"].replace(0, np.nan) - 1

    if "PERMIT" in df.columns:
        df["permit_yoy"] = df["PERMIT"].pct_change(12) * 100
        df["permit_chg3"] = df["PERMIT"].pct_change(3) * 100
        df["permit_chg6"] = df["PERMIT"].pct_change(6) * 100
        df["permit_ma6"] = df["PERMIT"].rolling(6).mean()

    # ════════════════════════════════════════════
    # INFLATION & MONETARY POLICY
    # ════════════════════════════════════════════

    if "CPIAUCSL" in df.columns:
        df["cpi_yoy"] = df["CPIAUCSL"].pct_change(12) * 100
        df["cpi_mom"] = df["CPIAUCSL"].pct_change(1) * 100
        df["cpi_3m_annualized"] = df["CPIAUCSL"].pct_change(3) * 400
        df["cpi_accel"] = df["cpi_yoy"].diff(6)  # inflation acceleration
        df["cpi_ma6"] = df["cpi_mom"].rolling(6).mean()

    if "CPILFESL" in df.columns:
        df["core_cpi_yoy"] = df["CPILFESL"].pct_change(12) * 100
        df["core_cpi_mom"] = df["CPILFESL"].pct_change(1) * 100

    if "PCEPILFE" in df.columns:
        df["core_pce_yoy"] = df["PCEPILFE"].pct_change(12) * 100

    if "PPIACO" in df.columns:
        df["ppi_yoy"] = df["PPIACO"].pct_change(12) * 100
        df["ppi_chg3"] = df["PPIACO"].pct_change(3) * 100

    # Fed funds
    if "FEDFUNDS" in df.columns:
        df["ff_chg3"] = df["FEDFUNDS"].diff(3)
        df["ff_chg6"] = df["FEDFUNDS"].diff(6)
        df["ff_chg12"] = df["FEDFUNDS"].diff(12)
        df["ff_ma6"] = df["FEDFUNDS"].rolling(6).mean()
        # Rate hike intensity (large moves)
        df["ff_hike_intensity"] = df["ff_chg12"].clip(lower=0)

        if "cpi_yoy" in df.columns:
            df["real_ff"] = df["FEDFUNDS"] - df["cpi_yoy"]
            df["real_ff_chg6"] = df["real_ff"].diff(6)
            df["real_ff_chg12"] = df["real_ff"].diff(12)
            df["real_ff_ma6"] = df["real_ff"].rolling(6).mean()

    # ════════════════════════════════════════════
    # MONEY SUPPLY & CREDIT
    # ════════════════════════════════════════════

    if "M2SL" in df.columns:
        df["m2_yoy"] = df["M2SL"].pct_change(12) * 100
        df["m2_chg6"] = df["M2SL"].pct_change(6) * 100
        df["m2_chg3"] = df["M2SL"].pct_change(3) * 100
        df["m2_accel"] = df["m2_yoy"].diff(6)

    if "M1SL" in df.columns:
        df["m1_yoy"] = df["M1SL"].pct_change(12) * 100

    if "TOTALSL" in df.columns:
        df["consumer_credit_yoy"] = df["TOTALSL"].pct_change(12) * 100
        df["consumer_credit_chg6"] = df["TOTALSL"].pct_change(6) * 100

    if "BOGZ1FL072052006Q" in df.columns:
        df["debt_service_chg3"] = df["BOGZ1FL072052006Q"].diff(3)
        df["debt_service_chg6"] = df["BOGZ1FL072052006Q"].diff(6)

    # ════════════════════════════════════════════
    # CONSUMER
    # ════════════════════════════════════════════

    if "UMCSENT" in df.columns:
        df["sentiment_chg3"] = df["UMCSENT"].diff(3)
        df["sentiment_chg6"] = df["UMCSENT"].diff(6)
        df["sentiment_chg12"] = df["UMCSENT"].diff(12)
        df["sentiment_ma3"] = df["UMCSENT"].rolling(3).mean()
        df["sentiment_ma6"] = df["UMCSENT"].rolling(6).mean()
        df["sentiment_zscore"] = (
            (df["UMCSENT"] - df["UMCSENT"].rolling(60).mean())
            / df["UMCSENT"].rolling(60).std().replace(0, 1)
        )
        # Sentiment collapse signal
        df["sentiment_crash"] = df["sentiment_chg6"].clip(upper=0)

    if "W875RX1" in df.columns:
        df["rpi_yoy"] = df["W875RX1"].pct_change(12) * 100
        df["rpi_mom"] = df["W875RX1"].pct_change(1) * 100
        df["rpi_chg3"] = df["W875RX1"].pct_change(3) * 100
        df["rpi_chg6"] = df["W875RX1"].pct_change(6) * 100

    # ════════════════════════════════════════════
    # ENERGY & COMMODITIES
    # ════════════════════════════════════════════

    if "DCOILWTICO" in df.columns:
        df["oil_yoy"] = df["DCOILWTICO"].pct_change(12) * 100
        df["oil_chg3"] = df["DCOILWTICO"].pct_change(3) * 100
        df["oil_chg6"] = df["DCOILWTICO"].pct_change(6) * 100
        df["oil_ma3"] = df["DCOILWTICO"].rolling(3).mean()
        df["oil_ma12"] = df["DCOILWTICO"].rolling(12).mean()
        # Oil shock signal (big positive moves)
        df["oil_shock"] = df["oil_chg3"].clip(lower=0)
        df["oil_zscore"] = (
            (df["DCOILWTICO"] - df["DCOILWTICO"].rolling(60).mean())
            / df["DCOILWTICO"].rolling(60).std().replace(0, 1)
        )

    # USD
    if "DTWEXBGS" in df.columns:
        df["usd_chg3"] = df["DTWEXBGS"].pct_change(3) * 100
        df["usd_chg6"] = df["DTWEXBGS"].pct_change(6) * 100
        df["usd_chg12"] = df["DTWEXBGS"].pct_change(12) * 100

    # ════════════════════════════════════════════
    # LEADING INDICATORS
    # ════════════════════════════════════════════

    if "USALOLITONOSTSAM" in df.columns:
        df["lei_chg3"] = df["USALOLITONOSTSAM"].diff(3)
        df["lei_chg6"] = df["USALOLITONOSTSAM"].diff(6)
        df["lei_chg12"] = df["USALOLITONOSTSAM"].diff(12)
        df["lei_ma3"] = df["USALOLITONOSTSAM"].rolling(3).mean()
        # Below 100 = contraction signal for OECD CLI
        df["lei_below_100"] = (df["USALOLITONOSTSAM"] < 100).astype(float)
        # Negative momentum streak
        chg1 = df["USALOLITONOSTSAM"].diff(1)
        df["lei_neg_months"] = (chg1 < 0).rolling(6).sum()

    if "WHLSLRIMSA" in df.columns:
        df["inv_sales_chg3"] = df["WHLSLRIMSA"].diff(3)
        df["inv_sales_chg6"] = df["WHLSLRIMSA"].diff(6)

    # ════════════════════════════════════════════
    # CROSS-FEATURE INTERACTIONS
    # ════════════════════════════════════════════

    # Yield curve + unemployment (classic recession combo)
    if "T10Y2Y" in df.columns and "UNRATE" in df.columns:
        df["curve_x_unemployment"] = df["T10Y2Y"] * df["unrate_chg3"]

    # Credit spread + financial conditions
    if "BAA10Y" in df.columns and "NFCI" in df.columns:
        df["credit_x_fci"] = df["BAA10Y"] * df["NFCI"]

    # Real rate + housing (rate hikes crushing housing)
    if "real_ff" in df.columns and "HOUST" in df.columns:
        houst_yoy = df["HOUST"].pct_change(12)
        df["rate_x_housing"] = df["real_ff"] * houst_yoy

    # Sentiment + claims (consumer stress)
    if "UMCSENT" in df.columns and "ICSA" in df.columns:
        df["sentiment_x_claims"] = df["sentiment_chg6"] * df["icsa_chg6"]

    # Oil shock + inflation (stagflation signal)
    if "oil_chg3" in df.columns and "cpi_yoy" in df.columns:
        df["oil_x_inflation"] = df["oil_chg3"] * df["cpi_yoy"]

    # Participation drop + unemployment (hidden labor market deterioration)
    if "civpart_chg6" in df.columns and "unrate_chg6" in df.columns:
        df["participation_x_unemployment"] = df["civpart_chg6"] * df["unrate_chg6"]

    # Quits rate + openings (labor market confidence)
    if "quits_rate_chg6" in df.columns and "jolts_openings_chg6" in df.columns:
        df["quits_x_openings"] = df["quits_rate_chg6"] * df["jolts_openings_chg6"]

    # Defragment the DataFrame after all column additions
    return df.copy()


def get_feature_columns(df: pd.DataFrame) -> List[str]:
    """Return the list of feature column names."""
    exclude = set(FEATURE_SERIES.keys()) | {"USREC"} | {
        f"recession_{h}m" for h in HORIZONS
    }
    # Raw series that are also used as direct features
    direct_features = {
        "T10Y2Y", "T10Y3M", "UNRATE", "FEDFUNDS", "NFCI", "ANFCI",
        "BAA10Y", "BAAFFM", "UMCSENT", "USALOLITONOSTSAM", "VIXCLS",
        "TEDRATE", "STLFSI2", "AWHMAN", "CIVPART", "EMRATIO",
        "LNS12300060", "U6RATE", "JTSJOL", "JTSQUR",
    }
    cols = []
    for c in df.columns:
        if c in exclude and c not in direct_features:
            continue
        if c.startswith("recession_"):
            continue
        cols.append(c)
    return cols
