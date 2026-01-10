# Zapier Dashboard Structure - FitAnon Multi-Account

## Data Sources (3 Square Accounts)

| Source Label | Email | Location ID |
|--------------|-------|-------------|
| THE FIT CLINIC LLC | mike@thefitclinicsj.com | (from Square) |
| THE FIT CLINIC | mike@fitclinic.io | (from Square) |
| FITNESS WITH MIKE | shmockeyfit@gmail.com | (from Square) |

---

## Zapier Tables Structure

### 1. CUSTOMERS Table
| Field | Type | Notes |
|-------|------|-------|
| customer_id | Text | Square Customer ID |
| source | Select | THE FIT CLINIC LLC / THE FIT CLINIC / FITNESS WITH MIKE |
| location_id | Text | Square Location ID |
| given_name | Text | First name |
| family_name | Text | Last name |
| email | Email | Customer email |
| phone | Phone | Customer phone |
| address_line_1 | Text | Street address |
| city | Text | City |
| state | Text | State |
| postal_code | Text | ZIP |
| created_at | DateTime | When customer was created in Square |
| synced_at | DateTime | When record was synced to Zapier |

### 2. TRANSACTIONS Table
| Field | Type | Notes |
|-------|------|-------|
| transaction_id | Text | Square Transaction/Payment ID |
| source | Select | Business source |
| location_id | Text | Location ID |
| customer_id | Text | Link to customer |
| amount | Currency | Total amount |
| currency | Text | USD |
| status | Select | COMPLETED / PENDING / FAILED |
| created_at | DateTime | Transaction date |
| payment_type | Text | CARD / CASH / etc |
| synced_at | DateTime | Sync timestamp |

### 3. INVOICES Table
| Field | Type | Notes |
|-------|------|-------|
| invoice_id | Text | Square Invoice ID |
| source | Select | Business source |
| location_id | Text | Location ID |
| customer_id | Text | Link to customer |
| invoice_number | Text | Display number |
| title | Text | Invoice title |
| amount | Currency | Total amount |
| status | Select | DRAFT / SENT / PAID / CANCELED |
| due_date | Date | Payment due date |
| created_at | DateTime | Creation date |
| paid_at | DateTime | Payment date (if paid) |
| synced_at | DateTime | Sync timestamp |

### 4. SALES_REPORTS Table (Daily Aggregates)
| Field | Type | Notes |
|-------|------|-------|
| report_id | Text | Auto-generated |
| source | Select | Business source |
| location_id | Text | Location ID |
| report_date | Date | Date of sales |
| gross_sales | Currency | Total gross |
| net_sales | Currency | After refunds |
| refunds | Currency | Refund total |
| discounts | Currency | Discount total |
| tax | Currency | Tax collected |
| transaction_count | Number | # of transactions |
| synced_at | DateTime | Sync timestamp |

### 5. ITEM_SALES Table
| Field | Type | Notes |
|-------|------|-------|
| item_sale_id | Text | Auto-generated |
| source | Select | Business source |
| location_id | Text | Location ID |
| item_id | Text | Square Item/Variation ID |
| item_name | Text | Product/Service name |
| category | Text | Item category |
| quantity_sold | Number | Units sold |
| gross_sales | Currency | Total sales for item |
| sale_date | Date | Date of sale |
| synced_at | DateTime | Sync timestamp |

---

## Zapier Interface Sections

### Dashboard Layout

```
┌─────────────────────────────────────────────────────────────┐
│  FitAnon Business Dashboard                                 │
├─────────────────────────────────────────────────────────────┤
│  [Filter: All Sources ▼] [Date Range: Last 30 Days ▼]       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │ Total       │ │ Total       │ │ Total       │           │
│  │ Customers   │ │ Revenue     │ │ Transactions│           │
│  │    XXX      │ │  $XX,XXX    │ │    XXX      │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  TABS: [Customers] [Transactions] [Invoices] [Sales] [Items]│
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Table Component (filtered by selected tab)          │   │
│  │  - Read-only                                         │   │
│  │  - Sortable columns                                  │   │
│  │  - Filter by Source                                  │   │
│  │  - Search                                            │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Zaps to Create (9 Total)

### Customer Sync Zaps (3)
1. **Square (FIT CLINIC LLC) → Customers Table**
   - Trigger: New Customer in Square
   - Action: Create Row in Customers Table
   - Set source = "THE FIT CLINIC LLC"

2. **Square (FIT CLINIC) → Customers Table**
   - Trigger: New Customer in Square
   - Action: Create Row in Customers Table
   - Set source = "THE FIT CLINIC"

3. **Square (FITNESS WITH MIKE) → Customers Table**
   - Trigger: New Customer in Square
   - Action: Create Row in Customers Table
   - Set source = "FITNESS WITH MIKE"

### Transaction Sync Zaps (3)
4-6. Same pattern for each account → Transactions Table

### Invoice Sync Zaps (3)
7-9. Same pattern for each account → Invoices Table

---

## MCP Server Mapping

| Zapier MCP Server | Connected Account | API Key Location |
|-------------------|-------------------|------------------|
| claude-mcp-1 | ? | Zapier Dashboard |
| claude-mcp-2 | ? | Zapier Dashboard |
| claude-mcp-3 | ? | Zapier Dashboard |

**To identify**: In Zapier, click each MCP → Square connection → note the email shown.

---

*Generated for Mike @ FitAnon - January 2026*
