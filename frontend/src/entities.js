const entryFields = [
  { name: 'description', label: 'Description', type: 'text', required: true },
  { name: 'amount', label: 'Amount', type: 'number', required: true },
  { name: 'startDate', label: 'Start date', type: 'date', required: true },
  { name: 'endDate', label: 'End date', type: 'date' },
  { name: 'recurrenceIntervalMonths', label: 'Repeat every (months)', type: 'number', step: '1', min: '1' },
  { name: 'account', label: 'Account', type: 'reference', source: 'account', required: true },
  { name: 'category', label: 'Category', type: 'reference', source: 'category' }
]
export const entities = {
  account: { label: 'Accounts', singular: 'Account', fields: [
    { name: 'name', label: 'Name', type: 'text', required: true },
    { name: 'currency', label: 'Currency code', type: 'enum', options: ['EUR', 'BRL', 'USD'], required: true },
    { name: 'openingBalance', label: 'Opening balance', type: 'number', required: true },
    { name: 'openingBalanceDate', label: 'Balance as of', type: 'date', required: true },
    { name: 'groups', label: 'Groups', type: 'multi', source: 'accountgroup' }
  ] },
  accountgroup: { label: 'Groups', singular: 'Group', fields: [
    { name: 'name', label: 'Name', type: 'text', required: true },
    { name: 'accounts', label: 'Accounts to consolidate', type: 'multi', source: 'account', required: true }
  ] },
  category: { label: 'Categories', singular: 'Category', fields: [
    { name: 'name', label: 'Name', type: 'text', required: true },
    { name: 'kind', label: 'For entries', type: 'enum', options: ['income', 'expense'], required: true }
  ] },
  entry: { label: 'All entries', singular: 'Entry', fields: entryFields, readOnlyCreate: true },
  expense: { label: 'Expenses', singular: 'Expense', fields: [
    { name: 'description', label: 'Description', type: 'text', required: true },
    { name: 'expenseType', label: 'Expense type', type: 'enum', options: ['FIX', 'VARIABLE', 'EXTRAORDINARY'], required: true },
    { name: 'expectedValue', label: 'Average amount', type: 'number', min: '0.01', conditional: 'VARIABLE', required: true },
    { name: 'allowedDeviation', label: 'Acceptable deviation (±)', type: 'number', min: '0', conditional: 'VARIABLE', required: true },
    { name: 'amount', label: 'Amount', type: 'number', min: '0.01' },
    ...entryFields.filter(field => !['description', 'amount'].includes(field.name))] },
  income: { label: 'Income', singular: 'Income', fields: [
    { name: 'description', label: 'Description', type: 'text', required: true },
    { name: 'incomeType', label: 'Income type', type: 'enum', options: ['FIXED', 'VARIABLE', 'EXTRAORDINARY'], required: true },
    { name: 'expectedValue', label: 'Average amount', type: 'number', min: '0.01', incomeRecurring: true, required: true },
    { name: 'allowedDeviation', label: 'Deviation (±)', type: 'number', min: '0', incomeRecurring: true, required: true },
    { name: 'amount', label: 'Amount', type: 'number', min: '0.01' },
    ...entryFields.filter(field => !['description', 'amount'].includes(field.name))] }
}
export const today = () => new Date().toLocaleDateString('en-CA')
export function initialValues(entity) {
  return Object.fromEntries(entities[entity].fields.map(field => [field.name,
    field.type === 'multi' ? [] : field.name === 'startDate' || field.name === 'openingBalanceDate' ? today() :
    field.type === 'enum' && !['expenseType', 'incomeType'].includes(field.name) ? field.options[0] : '']))
}
export function payload(entity, values) {
  return Object.fromEntries(entities[entity].fields.filter(field => (!field.conditional || values.expenseType === field.conditional) && (!field.incomeRecurring || ['FIXED', 'VARIABLE'].includes(values.incomeType))).map(field => {
    let value = values[field.name]
    if (field.type === 'number') value = value === '' || value == null ? null : Number(value)
    if (field.type === 'reference') value = value === '' || value == null ? null : Number(value)
    if (field.type === 'multi') value = (value || []).map(Number)
    if (!field.required && value === '') value = null
    return [field.name, value]
  }))
}
