# Zapier Setup Instructions - FitAnon Multi-Account

> Copy each section to Zapier Copilot to set up your tables and Zaps.
> Last Updated: January 10, 2026

---

## Square Connections Reference

| Connection Name | Email | Account |
|-----------------|-------|---------|
| THE FIT CLINIC LLC | mike@thefitclinicsj.com | Primary |
| FITCLINIC.IO | mike@fitclinic.io | Secondary |
| FITNESS WITH MIKE | shmockeyfit@gmail.com | Third |

---

## 1. CUSTOMER DATABASE TABLE

```
Add a new field called "Source" to the Customer Database table with these dropdown options:
- THE FIT CLINIC LLC
- FITCLINIC.IO
- FITNESS WITH MIKE

Then create 3 Zaps:

1. "Sync Customers - THE FIT CLINIC LLC"
   - Trigger: New Customer in Square (THE FIT CLINIC LLC connection)
   - Action: Create Record in Customer Database
   - Map fields: Customer Name, Email, Phone, Address, Customer ID
   - Set Source = "THE FIT CLINIC LLC"

2. "Sync Customers - FITCLINIC.IO"
   - Trigger: New Customer in Square (FITCLINIC.IO connection)
   - Action: Create Record in Customer Database
   - Map fields: Customer Name, Email, Phone, Address, Customer ID
   - Set Source = "FITCLINIC.IO"

3. "Sync Customers - FITNESS WITH MIKE"
   - Trigger: New Customer in Square (FITNESS WITH MIKE connection)
   - Action: Create Record in Customer Database
   - Map fields: Customer Name, Email, Phone, Address, Customer ID
   - Set Source = "FITNESS WITH MIKE"
```

---

## 2. TRANSACTIONS TABLE

```
Create a new table called "Transactions" with these fields:
- Transaction ID (Text)
- Source (Dropdown: THE FIT CLINIC LLC / FITCLINIC.IO / FITNESS WITH MIKE)
- Customer Name (Text)
- Customer Email (Email)
- Amount (Currency)
- Status (Dropdown: COMPLETED / PENDING / FAILED / REFUNDED)
- Payment Type (Text)
- Created At (DateTime)

Then create 3 Zaps:

1. "Sync Transactions - THE FIT CLINIC LLC"
   - Trigger: New Payment in Square (THE FIT CLINIC LLC connection)
   - Action: Create Record in Transactions table
   - Map all payment fields
   - Set Source = "THE FIT CLINIC LLC"

2. "Sync Transactions - FITCLINIC.IO"
   - Trigger: New Payment in Square (FITCLINIC.IO connection)
   - Action: Create Record in Transactions table
   - Map all payment fields
   - Set Source = "FITCLINIC.IO"

3. "Sync Transactions - FITNESS WITH MIKE"
   - Trigger: New Payment in Square (FITNESS WITH MIKE connection)
   - Action: Create Record in Transactions table
   - Map all payment fields
   - Set Source = "FITNESS WITH MIKE"
```

---

## 3. INVOICES TABLE

```
Create a new table called "Invoices" with these fields:
- Invoice ID (Text)
- Source (Dropdown: THE FIT CLINIC LLC / FITCLINIC.IO / FITNESS WITH MIKE)
- Invoice Number (Text)
- Customer Name (Text)
- Customer Email (Email)
- Amount (Currency)
- Status (Dropdown: DRAFT / SENT / PAID / CANCELED / OVERDUE)
- Due Date (Date)
- Created At (DateTime)
- Paid At (DateTime)

Then create 3 Zaps:

1. "Sync Invoices - THE FIT CLINIC LLC"
   - Trigger: New Invoice in Square (THE FIT CLINIC LLC connection)
   - Action: Create Record in Invoices table
   - Map all invoice fields
   - Set Source = "THE FIT CLINIC LLC"

2. "Sync Invoices - FITCLINIC.IO"
   - Trigger: New Invoice in Square (FITCLINIC.IO connection)
   - Action: Create Record in Invoices table
   - Map all invoice fields
   - Set Source = "FITCLINIC.IO"

3. "Sync Invoices - FITNESS WITH MIKE"
   - Trigger: New Invoice in Square (FITNESS WITH MIKE connection)
   - Action: Create Record in Invoices table
   - Map all invoice fields
   - Set Source = "FITNESS WITH MIKE"
```

---

## 4. SALES REPORTS TABLE

```
Create a new table called "Sales Reports" with these fields:
- Report Date (Date)
- Source (Dropdown: THE FIT CLINIC LLC / FITCLINIC.IO / FITNESS WITH MIKE)
- Gross Sales (Currency)
- Net Sales (Currency)
- Refunds (Currency)
- Discounts (Currency)
- Tax Collected (Currency)
- Transaction Count (Number)

Then create 3 scheduled Zaps (run daily at 11:59 PM):

1. "Daily Sales - THE FIT CLINIC LLC"
   - Trigger: Schedule (Every day at 11:59 PM)
   - Action 1: Find Orders in Square (THE FIT CLINIC LLC) for today
   - Action 2: Calculate totals using Formatter or Code step
   - Action 3: Create Record in Sales Reports table
   - Set Source = "THE FIT CLINIC LLC"

2. "Daily Sales - FITCLINIC.IO"
   - Trigger: Schedule (Every day at 11:59 PM)
   - Action 1: Find Orders in Square (FITCLINIC.IO) for today
   - Action 2: Calculate totals
   - Action 3: Create Record in Sales Reports table
   - Set Source = "FITCLINIC.IO"

3. "Daily Sales - FITNESS WITH MIKE"
   - Trigger: Schedule (Every day at 11:59 PM)
   - Action 1: Find Orders in Square (FITNESS WITH MIKE) for today
   - Action 2: Calculate totals
   - Action 3: Create Record in Sales Reports table
   - Set Source = "FITNESS WITH MIKE"
```

---

## 5. ITEM SALES TABLE

```
Create a new table called "Item Sales" with these fields:
- Item ID (Text)
- Source (Dropdown: THE FIT CLINIC LLC / FITCLINIC.IO / FITNESS WITH MIKE)
- Item Name (Text)
- Category (Text)
- Quantity Sold (Number)
- Gross Sales (Currency)
- Sale Date (Date)

Then create 3 Zaps:

1. "Sync Item Sales - THE FIT CLINIC LLC"
   - Trigger: New Order in Square (THE FIT CLINIC LLC connection)
   - Action: For each line item in the order, Create Record in Item Sales table
   - Map: Item ID, Item Name, Category, Quantity, Amount
   - Set Source = "THE FIT CLINIC LLC"

2. "Sync Item Sales - FITCLINIC.IO"
   - Trigger: New Order in Square (FITCLINIC.IO connection)
   - Action: For each line item, Create Record in Item Sales table
   - Map: Item ID, Item Name, Category, Quantity, Amount
   - Set Source = "FITCLINIC.IO"

3. "Sync Item Sales - FITNESS WITH MIKE"
   - Trigger: New Order in Square (FITNESS WITH MIKE connection)
   - Action: For each line item, Create Record in Item Sales table
   - Map: Item ID, Item Name, Category, Quantity, Amount
   - Set Source = "FITNESS WITH MIKE"
```

---

## Summary

| Table | Fields | Zaps Needed |
|-------|--------|-------------|
| Customer Database | Name, Email, Phone, Address, Customer ID, Source | 3 |
| Transactions | Transaction ID, Source, Customer, Amount, Status, Payment Type, Created At | 3 |
| Invoices | Invoice ID, Source, Number, Customer, Amount, Status, Due Date, Created/Paid At | 3 |
| Sales Reports | Date, Source, Gross/Net Sales, Refunds, Discounts, Tax, Transaction Count | 3 |
| Item Sales | Item ID, Source, Name, Category, Quantity, Sales, Date | 3 |

**Total: 5 Tables, 15 Zaps**

---

## Interface Setup

```
Create an Interface called "FitAnon Dashboard" with:

1. Header section with title "FitAnon Business Dashboard"

2. Filter controls:
   - Dropdown: Filter by Source (All / THE FIT CLINIC LLC / FITCLINIC.IO / FITNESS WITH MIKE)
   - Date range picker

3. Summary cards row:
   - Total Customers (count from Customer Database)
   - Total Revenue (sum from Transactions where Status = COMPLETED)
   - Total Transactions (count from Transactions)

4. Tab navigation:
   - Customers tab -> Table component showing Customer Database
   - Transactions tab -> Table component showing Transactions
   - Invoices tab -> Table component showing Invoices
   - Sales tab -> Table component showing Sales Reports
   - Items tab -> Table component showing Item Sales

5. All tables should be:
   - Read-only
   - Filterable by Source column
   - Sortable by date columns
   - Searchable
```

---

## MCP Server Mapping

Once Zaps are set up, verify which MCP server connects to which account:

| Zapier MCP Server | Square Connection |
|-------------------|-------------------|
| claude-mcp-1 | (check in Zapier) |
| claude-mcp-2 | (check in Zapier) |
| claude-mcp-3 | (check in Zapier) |

---

*Generated for Mike @ FitAnon - January 2026*
