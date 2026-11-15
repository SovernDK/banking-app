# Yiji

A personal finance app that shows a person's bank transactions as spending charts.

## Spending

**Spending**:
Money leaving the account: booked or pending debits, excluding cancelled or rejected ones.
_Avoid_: Expenses, outgoings

**Main currency**:
The currency with the most spending; charts show only spending in it.

## Breakdowns

**Payment method**:
How money left the account: ATM withdrawal, Card payment, BLIK, Transfer, Direct debit, Fee or Other. Derived from the bank's data, never chosen by the person.
_Avoid_: Transaction type, channel

**Bank profile**:
The bank-specific knowledge of how one bank (identified by name and country) records payment methods. Banks without their own profile use the generic one.
_Avoid_: Scheme, bank mapping

**Category**:
What the money was spent on (Groceries, Rent, …), created and named by the person.
_Avoid_: Tag, label, type

**Counterparty name**:
Who the money went to: the creditor's name, or the first line of the payment description when the bank gives no creditor. Two names are the same when they differ only in letter case or spacing.
_Avoid_: Merchant, payee

**Category rule**:
A link from one counterparty name to one category; it applies to all past and future spending with that name.
_Avoid_: Assignment, mapping

**Uncategorised**:
Spending whose counterparty name has no category rule.
_Avoid_: Unknown, none

**Other**:
On a chart, the slices too small to show on their own, grouped into one.
