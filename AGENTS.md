<!-- besser:begin -->
## Working on this project

Built with [BESSER](https://github.com/BESSER-PEARL/BESSER). BESSER rewrites this section on every push; anything outside it is yours and stays.

- The model is `buml/diagrams.json`. Open it in the [BESSER editor](https://editor.besser-pearl.org), and change data structures there, not only in the code.
- Files named `.besser_*` are BESSER's run records. Do not edit them by hand.

### Recent work

- 2026-11-26: `In the dashboard, : - update the emergency cover to account for fixed + variable expenses. - delete: EUR · next 6 months - Expenses so far vs planned should not be green if it is above 100%. - delete …`
- 2026-11-26: `I would like to update the dashboard withe the following: 1. Where am I now Current balance (net worth). Total balance today across accounts, with the change since last month and a small trend line. T…`
- 2026-11-26: `In the main menu, when we click on the Accounts or Entries the submenu appears, no problem. However, it should collapse when the user clicks elsewhere in the page.`
- 2026-11-26: `The income and expenses monthly table view, instead of a string, the user should be able to select a month based on a list. He should be able to choose the year from 2026 until 2036 and the month from…`
- 2026-11-26: `- Expense type should be entered before the amount. With that, if chosen variable, the amount should be named "This months amount" and should be optional. - The same as the expenses also counts for th…`

### Still open when the last run ended

- Left out: `Make the Category link optional for Entry/Income/Expense in backend/sql_alchemy.py, backend/pydantic_classes.py, and category-selection forms, as required by “Categories should not be mandatory.” (Pre…`
- Left out: `Separate category sets for Income and Expense and support creating a category directly from their category-selection pages, anchoring this to the request’s distinct income/expense categories and inlin…`
- Left out: `Extend Expense and Income persistence and forms with fixed, variable, extraordinary types plus expected/average amount, deviation, and optional current-month actual fields, preserving the exact reques…`
- Left out: `Implement monthly occurrence creation and carry-forward for fixed and variable income and expenses, including yellow highlighting when a carried-forward variable entry lacks an actual amount, in backe…`
- Left out: `Make “Repeat every x months” mandatory and reject 0 for fixed and variable expenses; add the matching recurrence validation for income where its fixed/variable monthly behavior requires it, in backend…`
- Left out: `Add selectable month and year (2026–2036) monthly views for income and expenses, with fixed/variable/extraordinary ordering for expenses, in frontend/src/pages/EntityList.jsx and monthly API handlers.…`
- Left out: `Record monthly occurrence actual amounts without range validation, and provide over-plan expense occurrences and below-minimum income occurrences for the overview, in backend/monthly.py and overview d…`
- Left out: `Implement currency selection limited to a list including EUR, BRL, and USD in Account creation/edit UI and backend validation, anchored to the currency-list request. (Existing currency selection; outs…`
- and 7 more
<!-- besser:end -->
