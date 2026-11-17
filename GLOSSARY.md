# Yiji

A personal finance app that shows a person's bank transactions as spending charts.

## Spending

**Spending**:
Money leaving the account: booked debits only. Pending payments count once the bank books them; cancelled and rejected ones never do. Money moved between two accounts in the same bank connection is not spending.
_Avoid_: Expenses, outgoings

**Payment**:
One booked debit as Yiji keeps it: name (first payment description line), payee (creditor), amount, currency, booking date and payment method. Nothing else from the bank is stored.
_Avoid_: Transaction (that is the bank's full record)

**Spending history**:
Every payment ever fetched, kept after the bank stops serving it (banks give only 3–13 months). Each fetch replaces the account's payments from the first day it covered.

**Main currency**:
The currency with the most spending; the default display currency.

**Display currency**:
The currency every chart shows; chosen by the person, payments in other currencies are converted into it.

**Exchange rate**:
The ECB reference rate published on a payment's booking date, or the latest one up to a week before it (weekends, holidays). A payment with no such rate is left out of a converted view.

**Comparison**:
The same number of days as the selected period, ending one month (M2M) or one year (Y2Y) before today; always shown, hatched beside the current bars. Days the bank gave no history for count as no spending.
_Avoid_: Previous period, baseline

## Bank

**Bank connection**:
The person's consent, given at their bank, for Yiji to read that bank's accounts for a limited number of days. Yiji can fetch nothing before it exists and nothing after it expires; renewing it is reconnecting.
_Avoid_: Link, login, session

**First fill**:
The fetch right after the first bank connection, which stores as much past spending as the bank serves (90 days at Pekao). Later fetches only add what was booked since the last one.
_Avoid_: Prefill, initial import

## Breakdowns

**Payment method**:
How money left the account: ATM withdrawal, Card payment, BLIK, Transfer, Direct debit, Fee or Other. Derived from the bank's data, never chosen by the person.
_Avoid_: Transaction type, channel

**Bank profile**:
The bank-specific knowledge of how one bank (identified by name and country) records its transactions: which fields become a payment's name, payee, amount, date and payment method, and which transactions are kept at all. Banks without their own profile use the generic one.
_Avoid_: Scheme, bank mapping

**Category**:
What the money was spent on (Groceries, Rent, …), created and named by the person.
_Avoid_: Tag, label, type

**Counterparty name**:
Who the money went to: the payment's payee, or its name when there is no payee. Two names are the same when they differ only in letter case or spacing.
_Avoid_: Merchant, payee

Spending with no counterparty name (a cash withdrawal, say) goes by its payment method in the Counterparties donut.

**Category rule**:
A link from one counterparty name to one category; it applies to all past and future spending with that name.
_Avoid_: Assignment, mapping

**Uncategorised**:
Spending whose counterparty name has no category rule.
_Avoid_: Unknown, none

**Other**:
On a chart, the slices too small to show on their own, grouped into one.
