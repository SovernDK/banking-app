# Spending in other currencies is converted at the ECB rate of its booking day

Spending comes in several currencies (PLN, EUR, USD, sometimes JPY), and one chart needs one currency. Each payment is converted at the ECB euro reference rate of its own booking day, which is closer to what was really paid than today's rate. The rates come from the Frankfurter API: free, no key, history back to 1999. Requests carry only dates and currency codes. The rates are stored in the same SQLite file, so each day is fetched once. Other pairs are computed through the euro.

The ECB publishes nothing on weekends and holidays, so a payment uses the latest rate up to `YIJI_EXCHANGE_RATE_LOOKBACK_DAYS` before it. A payment with no such rate is left out of the converted view, and a warning counts how many. Guessing would chart a wrong amount without saying so. ECB mid-market rates differ slightly from what a bank charged; we accept that, because the bank's own conversion is not in the data Yiji keeps.
