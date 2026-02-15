"""
Economic Indicators Data Transformer

Calculates MoM, YoY, moving averages, and other transformations.
Uses date-based matching (not row offsets) for YoY/MoM to handle gaps correctly.
"""

import pandas as pd
import numpy as np
from typing import List, Optional
from dateutil.relativedelta import relativedelta


class DataTransformer:
    """
    Transforms economic indicator data with various calculations.
    """

    @staticmethod
    def calculate_change(df: pd.DataFrame, periods: int = 1, column: str = 'value') -> pd.Series:
        """Calculate absolute change over N periods"""
        return df[column].diff(periods)

    @staticmethod
    def calculate_percent_change(df: pd.DataFrame, periods: int = 1, column: str = 'value') -> pd.Series:
        """Calculate percent change over N periods"""
        return df[column].pct_change(periods) * 100

    @staticmethod
    def calculate_moving_average(df: pd.DataFrame, periods: int, column: str = 'value') -> pd.Series:
        """Calculate simple moving average"""
        return df[column].rolling(window=periods).mean()

    @staticmethod
    def _date_based_change(df: pd.DataFrame, months_back: int, column: str = 'value'):
        """
        Calculate change vs the value N months ago using actual date matching.
        Handles gaps in data correctly (unlike pct_change which counts rows).

        Returns (absolute_change, percent_change) Series tuple.
        """
        # Build a date->value lookup
        date_col = df['date']
        val_col = df[column]

        # Convert dates to comparable format
        dates = pd.to_datetime(date_col)
        lookup = dict(zip(dates, val_col))

        abs_changes = []
        pct_changes = []

        for d, v in zip(dates, val_col):
            target_date = d - relativedelta(months=months_back)
            prior = lookup.get(target_date)
            if prior is not None and pd.notna(prior) and prior != 0:
                abs_changes.append(v - prior)
                pct_changes.append(((v - prior) / prior) * 100)
            else:
                abs_changes.append(np.nan)
                pct_changes.append(np.nan)

        return (
            pd.Series(abs_changes, index=df.index),
            pd.Series(pct_changes, index=df.index),
        )

    @staticmethod
    def calculate_yoy_change(df: pd.DataFrame, frequency: str = 'monthly', column: str = 'value') -> pd.Series:
        """Calculate year-over-year absolute change using date-based matching."""
        months = {'quarterly': 12, 'monthly': 12, 'weekly': 12, 'daily': 12}
        abs_chg, _ = DataTransformer._date_based_change(df, months.get(frequency, 12), column)
        return abs_chg

    @staticmethod
    def calculate_yoy_percent(df: pd.DataFrame, frequency: str = 'monthly', column: str = 'value') -> pd.Series:
        """Calculate year-over-year percent change using date-based matching."""
        months = {'quarterly': 12, 'monthly': 12, 'weekly': 12, 'daily': 12}
        _, pct_chg = DataTransformer._date_based_change(df, months.get(frequency, 12), column)
        return pct_chg

    @staticmethod
    def calculate_mom_change(df: pd.DataFrame, column: str = 'value') -> pd.Series:
        """Calculate month-over-month change using date-based matching."""
        abs_chg, _ = DataTransformer._date_based_change(df, 1, column)
        return abs_chg

    @staticmethod
    def calculate_mom_percent(df: pd.DataFrame, column: str = 'value') -> pd.Series:
        """Calculate month-over-month percent change using date-based matching."""
        _, pct_chg = DataTransformer._date_based_change(df, 1, column)
        return pct_chg

    @staticmethod
    def calculate_annualized_rate(df: pd.DataFrame, periods: int = 1, column: str = 'value') -> pd.Series:
        """
        Calculate annualized rate of change (SAAR style).
        Formula: ((1 + pct_change) ^ (periods_per_year / periods) - 1) * 100
        """
        pct_change = df[column].pct_change(periods)
        # Assuming monthly data, annualize
        annualized = ((1 + pct_change) ** (12 / periods) - 1) * 100
        return annualized

    def transform(
        self,
        df: pd.DataFrame,
        transformations: List[str],
        frequency: str = 'monthly'
    ) -> pd.DataFrame:
        """
        Apply multiple transformations to a DataFrame.

        Args:
            df: DataFrame with 'date' and 'value' columns
            transformations: List of transformations to apply:
                - 'mom_change': Month-over-month change
                - 'mom_percent': Month-over-month percent
                - 'yoy_change': Year-over-year change
                - 'yoy_percent': Year-over-year percent
                - 'ma_3': 3-period moving average
                - 'ma_6': 6-period moving average
                - 'ma_12': 12-period moving average
                - 'ma_N': N-period moving average (any number)
                - 'annualized': Annualized rate
            frequency: Data frequency for YoY calculations

        Returns:
            DataFrame with additional columns for each transformation
        """
        result = df.copy()

        for transform in transformations:
            if transform == 'mom_change':
                result['mom_change'] = self.calculate_mom_change(result)

            elif transform == 'mom_percent':
                result['mom_percent'] = self.calculate_mom_percent(result)

            elif transform == 'yoy_change':
                result['yoy_change'] = self.calculate_yoy_change(result, frequency)

            elif transform == 'yoy_percent':
                result['yoy_percent'] = self.calculate_yoy_percent(result, frequency)

            elif transform.startswith('ma_'):
                periods = int(transform.split('_')[1])
                result[f'ma_{periods}'] = self.calculate_moving_average(result, periods)

            elif transform == 'annualized':
                result['annualized'] = self.calculate_annualized_rate(result)

        return result

    def get_latest_with_changes(
        self,
        df: pd.DataFrame,
        frequency: str = 'monthly'
    ) -> dict:
        """
        Get the latest value with all standard changes calculated.

        Returns:
            {
                'date': '2025-01-01',
                'value': 123.4,
                'mom_change': 0.5,
                'mom_percent': 0.41,
                'yoy_change': 3.2,
                'yoy_percent': 2.67
            }
        """
        if df is None or df.empty:
            return None

        transformed = self.transform(
            df,
            ['mom_change', 'mom_percent', 'yoy_change', 'yoy_percent'],
            frequency
        )

        latest = transformed.iloc[-1]

        return {
            'date': latest['date'].isoformat() if hasattr(latest['date'], 'isoformat') else str(latest['date']),
            'value': round(float(latest['value']), 4) if pd.notna(latest['value']) else None,
            'mom_change': round(float(latest['mom_change']), 4) if pd.notna(latest.get('mom_change')) else None,
            'mom_percent': round(float(latest['mom_percent']), 4) if pd.notna(latest.get('mom_percent')) else None,
            'yoy_change': round(float(latest['yoy_change']), 4) if pd.notna(latest.get('yoy_change')) else None,
            'yoy_percent': round(float(latest['yoy_percent']), 4) if pd.notna(latest.get('yoy_percent')) else None,
        }
