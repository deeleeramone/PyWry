# MCP Examples

Example interactions with the PyWry MCP server.

## Data Visualization

### Scatter Plot

**User prompt:**

> Create a scatter plot showing the relationship between hours studied and test scores. Use this data: hours [1, 2, 3, 4, 5, 6, 7, 8], scores [52, 58, 65, 72, 78, 82, 88, 92].

**Claude's tool call:**

```json
{
  "name": "show_plotly",
  "arguments": {
    "figure": {
      "data": [{
        "x": [1, 2, 3, 4, 5, 6, 7, 8],
        "y": [52, 58, 65, 72, 78, 82, 88, 92],
        "type": "scatter",
        "mode": "markers",
        "marker": {"size": 10, "color": "#3b82f6"}
      }],
      "layout": {
        "title": "Hours Studied vs Test Scores",
        "xaxis": {"title": "Hours Studied"},
        "yaxis": {"title": "Test Score"}
      }
    },
    "template": "plotly_white"
  }
}
```

---

### Bar Chart

**User prompt:**

> Show me a bar chart comparing Q1 sales across regions: North $120k, South $95k, East $110k, West $85k.

**Claude's tool call:**

```json
{
  "name": "show_plotly",
  "arguments": {
    "figure": {
      "data": [{
        "x": ["North", "South", "East", "West"],
        "y": [120000, 95000, 110000, 85000],
        "type": "bar",
        "marker": {"color": ["#3b82f6", "#10b981", "#f59e0b", "#ef4444"]}
      }],
      "layout": {
        "title": "Q1 Sales by Region",
        "xaxis": {"title": "Region"},
        "yaxis": {"title": "Sales ($)", "tickformat": "$,.0f"}
      }
    }
  }
}
```

---

### Pie Chart

**User prompt:**

> Create a pie chart of our market share: Us 45%, Competitor A 25%, Competitor B 20%, Others 10%.

**Claude's tool call:**

```json
{
  "name": "show_plotly",
  "arguments": {
    "figure": {
      "data": [{
        "labels": ["Us", "Competitor A", "Competitor B", "Others"],
        "values": [45, 25, 20, 10],
        "type": "pie",
        "hole": 0.4
      }],
      "layout": {
        "title": "Market Share"
      }
    }
  }
}
```

---

## Data Tables

### Simple Table

**User prompt:**

> Display a table of our top 5 products with columns for name, category, price, and stock.

**Claude's tool call:**

```json
{
  "name": "show_dataframe",
  "arguments": {
    "data_json": "[{\"name\": \"Widget Pro\", \"category\": \"Electronics\", \"price\": 299.99, \"stock\": 150}, {\"name\": \"Gadget Plus\", \"category\": \"Electronics\", \"price\": 199.99, \"stock\": 230}, {\"name\": \"Tool Master\", \"category\": \"Tools\", \"price\": 89.99, \"stock\": 500}, {\"name\": \"Smart Hub\", \"category\": \"Smart Home\", \"price\": 149.99, \"stock\": 85}, {\"name\": \"Power Bank X\", \"category\": \"Accessories\", \"price\": 49.99, \"stock\": 1200}]",
    "title": "Top 5 Products"
  }
}
```

---

## Interactive Dashboards

### Sales Dashboard

**User prompt:**

> Create a dashboard showing our monthly sales data with a line chart for trend and a summary table.

**Claude's approach:**

1. First, create the chart:

```json
{
  "name": "show_plotly",
  "arguments": {
    "figure": {
      "data": [{
        "x": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
        "y": [45000, 52000, 49000, 61000, 58000, 72000],
        "type": "scatter",
        "mode": "lines+markers",
        "name": "Sales"
      }],
      "layout": {
        "title": "Monthly Sales Trend",
        "yaxis": {"title": "Sales ($)"}
      }
    },
    "label": "sales-chart"
  }
}
```

2. Then, create the summary table:

```json
{
  "name": "show_dataframe",
  "arguments": {
    "data_json": "[{\"metric\": \"Total Sales\", \"value\": \"$337,000\"}, {\"metric\": \"Average Monthly\", \"value\": \"$56,167\"}, {\"metric\": \"Best Month\", \"value\": \"June ($72,000)\"}, {\"metric\": \"Growth Rate\", \"value\": \"60%\"}]",
    "title": "Sales Summary"
  }
}
```

---

## Updating Widgets

### Update Chart Title

**User prompt:**

> Change the title of the sales chart to "H1 2024 Sales Performance".

**Claude's tool call:**

```json
{
  "name": "update_widget",
  "arguments": {
    "label": "sales-chart",
    "event_type": "plotly:update-layout",
    "data": {
      "layout": {
        "title": "H1 2024 Sales Performance"
      }
    }
  }
}
```

---

### Update Grid Data

**User prompt:**

> Add a new row to the products table: "Mega Widget" in Electronics for $399.99 with 50 in stock.

**Claude's tool call:**

```json
{
  "name": "update_widget",
  "arguments": {
    "label": "products-grid",
    "event_type": "grid:add-rows",
    "data": {
      "rows": [{
        "name": "Mega Widget",
        "category": "Electronics",
        "price": 399.99,
        "stock": 50
      }],
      "position": "top"
    }
  }
}
```

---

## Custom HTML

### Information Card

**User prompt:**

> Create an info card showing our company stats: 150 employees, $12M revenue, 95% customer satisfaction.

**Claude's tool call:**

```json
{
  "name": "show_html",
  "arguments": {
    "html": "<div style='padding: 20px; font-family: system-ui;'><h1 style='color: #1e293b;'>Company Stats</h1><div style='display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-top: 20px;'><div style='background: #f0fdf4; padding: 20px; border-radius: 8px; text-align: center;'><div style='font-size: 36px; font-weight: bold; color: #16a34a;'>150</div><div style='color: #4b5563;'>Employees</div></div><div style='background: #eff6ff; padding: 20px; border-radius: 8px; text-align: center;'><div style='font-size: 36px; font-weight: bold; color: #2563eb;'>$12M</div><div style='color: #4b5563;'>Revenue</div></div><div style='background: #fef3c7; padding: 20px; border-radius: 8px; text-align: center;'><div style='font-size: 36px; font-weight: bold; color: #d97706;'>95%</div><div style='color: #4b5563;'>Satisfaction</div></div></div></div>",
    "title": "Company Stats",
    "width": 600,
    "height": 250
  }
}
```

---

## Multi-Step Workflows

### Data Analysis Workflow

**User prompt:**

> Analyze this sales data and show me insights: [data provided]

Claude might:

1. **Create a summary chart** — Show overall trends
2. **Create a breakdown table** — Show detailed metrics
3. **Create a comparison chart** — Compare categories
4. **Explain the insights** — Provide textual analysis

Each step uses the appropriate MCP tool while Claude provides context and explanations between tool calls.

---

## Tips for Effective Prompts

### Be Specific

❌ "Show me a chart"  
✅ "Create a bar chart comparing monthly revenue for the first 6 months of 2024"

### Provide Data

❌ "Make a chart of our sales"  
✅ "Create a line chart with months Jan-Jun and values 10k, 12k, 15k, 14k, 18k, 22k"

### Specify Appearance

❌ "Show a table"  
✅ "Show a dark-themed table with sortable columns and pagination"

### Use Labels

❌ "Update the chart"  
✅ "Update the chart labeled 'sales-chart' to show Q2 data"
