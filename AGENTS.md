<!-- besser:begin -->
## Working on this project

Built with [BESSER](https://github.com/BESSER-PEARL/BESSER). BESSER rewrites this section on every push; anything outside it is yours and stays.

- The model is `buml/diagrams.json`. Open it in the [BESSER editor](https://editor.besser-pearl.org), and change data structures there, not only in the code.
- Files named `.besser_*` are BESSER's run records. Do not edit them by hand.

### Recent work

- 2026-11-26: `The income and expenses monthly table view, instead of a string, the user should be able to select a month based on a list. He should be able to choose the year from 2026 until 2036 and the month from…`
- 2026-11-26: `- Expense type should be entered before the amount. With that, if chosen variable, the amount should be named "This months amount" and should be optional. - The same as the expenses also counts for th…`
- 2026-11-26: `Please update: - "Repeat every x months" should be mandatory for fixed and variable expenses. 0 should not be accepted. - For variable expenses, one should enter the expected value for that expense an…`
- 2026-11-26: `Refactor the app to replace "Revenue" by "Income".`
- 2026-11-26: `A few more updates: - Transfers should also have the options to be repeated. - When choosing the category for expenses/revenue, the user should be able to include new categories from that page directl…`

### Still open when the last run ended

- Not in the code: `Variable expenses may have an optional current-month amount; its label is “This months amount”.`
- Not checked: `The app is visually pleasant and easy to use.`
- Left out: `Add a distinct ExpenseCategory/IncomeCategory discriminator to Category and filter category listings/creation so revenue categories and expense categories remain separate, while preserving optional En…`
- Left out: `Extend Income in backend/sql_alchemy.py and backend/pydantic_classes.py with fixed, variable, and extraordinary type, expected/average and deviation values, optional monthly amount, and repeat interva…`
- Left out: `Make variable income and expense monthly amounts optional and label them “This months amount”; preserve expected/average plus deviation and do not reject monthly edits outside that range in backend/mo…`
- Left out: `Require recurrenceIntervalMonths greater than zero for fixed and variable expenses in backend/pydantic_classes.py and expense handlers, and bring eligible fixed/variable entries forward into each due …`
- Left out: `Order monthly expense rows by FIX, VARIABLE, EXTRAORDINARY and highlight variable rows yellow in frontend/src/pages/EntityList.jsx. (Monthly expense ordering and highlighting are outside this request.…`
- Left out: `Track and expose each monthly expense occurrence above expected value plus deviation, and show the complete above-stipulated expense occurrence list on Overview in backend/monthly.py and frontend/src/…`
- and 6 more
<!-- besser:end -->
