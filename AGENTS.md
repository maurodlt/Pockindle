<!-- besser:begin -->
## Working on this project

Built with [BESSER](https://github.com/BESSER-PEARL/BESSER). BESSER rewrites this section on every push; anything outside it is yours and stays.

- The model is `buml/diagrams.json`. Open it in the [BESSER editor](https://editor.besser-pearl.org), and change data structures there, not only in the code.
- Files named `.besser_*` are BESSER's run records. Do not edit them by hand.

### Recent work

- 2026-11-26: `In the dashboard - First low-balance warning should highlight any warnings in red. - Account balances today should highlight negative values in red as well.`
- 2026-11-26: `In the dashboard: - Left to spend this month should be yellow if below 10% of monthly income and red if below 0. - delete EUR overview section with current and average income, expenses and total. - Mi…`
- 2026-11-26: `In the dashboard, : - update the emergency cover to account for fixed + variable expenses. - delete: EUR · next 6 months - Expenses so far vs planned should not be green if it is above 100%. - delete …`
- 2026-11-26: `I would like to update the dashboard withe the following: 1. Where am I now Current balance (net worth). Total balance today across accounts, with the change since last month and a small trend line. T…`
- 2026-11-26: `In the main menu, when we click on the Accounts or Entries the submenu appears, no problem. However, it should collapse when the user clicks elsewhere in the page.`

### Still open when the last run ended

- Not in the code: `The dashboard shows each category's spending this month compared with its average over the previous 3–6 months, including the difference.`
- Not in the code: `The dashboard shows entries ending in the next few months and the monthly amount freed when they end.`
- Left out: `Implement the user-requested “Income and fixed, variable and extraordinary expenses” types, separating income and expense type vocabularies and supporting type-first variable amount/deviation fields i…`
- Left out: `Make Entry.category optional as required by “Categories should not be mandatory,” and support distinct income and expense category sets plus creating a category from the income/expense selection page.…`
- Left out: `Extend Entry/Income/Expense persistence and backend/monthly.py to support expected amount, deviation, per-month actual amount, and an optional monthly amount for variable income and expenses; retain u…`
- Left out: `Enforce “Repeat every x months” as mandatory and nonzero for fixed and variable expenses, and propagate fixed/variable expenses to each due month in the monthly view, ordered fixed, variable, extraord…`
- Left out: `Add repeating transfers between two accounts, including repeat interval handling in the transfer model, schemas, and existing transfer handlers/UI, as required by “Transfers should also have the optio…`
- Left out: `Implement monthly income and expense selectors with month names and years 2026–2036 in the monthly entry views, as required by the user’s monthly-view request. (Already generated; no month selector ch…`
- and 8 more
<!-- besser:end -->
