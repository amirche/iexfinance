import datetime
import pandas as pd

from iexfinance.base import _IEXBase
from iexfinance.stocks.base import Stock
from iexfinance.utils import _sanitize_dates
from iexfinance.utils.exceptions import IEXSymbolError


class HistoricalReader(Stock):
    """
    Base class to download historical data from the chart endpoint

    Reference: https://iextrading.com/developer/docs/#chart
    """

    def __init__(self, symbols, start, end=None, close_only=False, **kwargs):
        self.start, self.end = _sanitize_dates(start, end)
        self.single_day = True if self.end is None else False
        self.close_only = close_only
        super(HistoricalReader, self).__init__(symbols, **kwargs)

    @property
    def chart_range(self):
        """ Calculates the chart range from start and end
        """
        # TODO: rewrite to account for leap years

        delta_days = (datetime.datetime.now() - self.start).days
        if 0 <= delta_days < 6:
            return "5d"
        elif 6 <= delta_days < 28:
            return "1m"
        elif 28 <= delta_days < 84:
            return "3m"
        elif 84 <= delta_days < 168:
            return "6m"
        elif 168 <= delta_days < 365:
            return "1y"
        elif 365 <= delta_days < 730:
            return "2y"
        elif 730 <= delta_days < 1826:
            return "5y"
        elif 1826 <= delta_days < 5478:
            return "max"
        else:
            raise ValueError("Invalid date specified. " "Must be within past 15 years.")

    @property
    def params(self):
        syms = ",".join(self.symbols)
        params = {
            "symbols": syms,
            "types": "chart",
            "range": self.chart_range,
            "chartByDay": self.single_day,
            "chartCloseOnly": self.close_only,
        }
        if self.single_day:
            try:
                params["exactDate"] = self.start.strftime("%Y%m%d")
            except AttributeError:
                params["exactDate"] = self.start
        return params

    def _output_format(self, out, fmt_j=None, fmt_p=None):
        result = {}
        if len(self.symbols) == 1 and not out[self.symbols[0]]["chart"]:
            return pd.DataFrame(out)
        for symbol in self.symbols:
            if symbol not in out:
                raise IEXSymbolError(symbol)
            d = out.pop(symbol)["chart"]
            df = pd.DataFrame(d)
            if self.output_format == "pandas":
                df["date"] = pd.DatetimeIndex(df["date"])
            df = df.set_index(df["date"])
            values = ["close", "volume"]
            if self.close_only is False:
                values = ["open", "high", "low"] + values
            df = df[values]
            if self.single_day is False:
                sstart = self.start.strftime("%Y-%m-%d")
                send = self.end.strftime("%Y-%m-%d")
                df = df.loc[sstart:send]
            result.update({symbol: df})
        if self.output_format == "pandas":
            if len(result) > 1:
                result = pd.concat(result.values(), keys=result.keys(), axis=1)
        else:
            for sym in list(result):
                result[sym] = result[sym].to_dict("index")
        return result[self.symbols[0]] if len(self.symbols) == 1 else result


class IntradayReader(_IEXBase):
    """
    Base class for intraday historical data
    """

    def __init__(self, symbol, date=None, **kwargs):
        try:
            self.date = date.strftime("%Y%m%d")
        except AttributeError:
            self.date = date

        if not isinstance(symbol, str):
            raise ValueError("Please enter a valid single symbol.")

        self.symbol = symbol
        super(IntradayReader, self).__init__(**kwargs)

    @property
    def params(self):
        return {}

    @property
    def url(self):
        if self.date is None:
            return "stock/%s/chart/1d" % self.symbol
        else:
            return "stock/%s/chart/date/%s" % (self.symbol, self.date)

    def _convert_output(self, out):
        if out:
            df = pd.DataFrame(out).set_index("minute")
            df.index = df.date + " " + df.index
            df.index = pd.DatetimeIndex([pd.to_datetime(x) for x in df.index])
            return df
        else:
            return pd.DataFrame()
