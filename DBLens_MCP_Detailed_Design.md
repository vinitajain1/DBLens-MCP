# DBLens MCP MCP — Detailed Design Document

## 1. Overview

**Project Name:** DBLens MCP MCP  
**Project Type:** Local MCP Server for Safe AI-Assisted Database Exploration  
**Database:** SQLite  
**Domain Data:** Inventory and Sales Orders  
**Primary Goal:** Help a user ask natural-language questions in Claude/Cursor and safely query local structured business data through an MCP server.

DBLens MCP MCP is a local Python-based Model Context Protocol server that exposes controlled database tools to AI clients such as Claude Desktop or Cursor. The AI client interprets the user's natural-language question, selects the correct MCP tool, sends structured arguments to the server, and receives structured results. The MCP server itself does not interpret natural language. It only executes defined tools safely.

---

## 2. Goals

### 2.1 Functional Goals

1. Allow an AI assistant to list available local database instances.
2. Allow the AI assistant to inspect schema for inventory and sales-order data.
3. Allow read-only SQL execution with safety guardrails.
4. Automatically add a row limit to SELECT queries.
5. Block destructive SQL operations.
6. Log every tool call and generated query for auditability.
7. Support multiple local SQLite databases to simulate Dev/Test/Prod-like environments.
8. Provide query-plan inspection using SQLite `EXPLAIN QUERY PLAN`.

### 2.2 Learning Goals

This project helps understand:

1. How MCP clients communicate with MCP servers.
2. How natural language becomes structured tool calls.
3. How to expose backend capabilities safely to AI assistants.
4. How to build guardrails around database access.
5. How to design tool schemas and backend execution boundaries.

---

## 4. Example Use Cases

### 4.1 Inventory Lookup

User asks:

> Which items are low on inventory?

The AI client calls:

```json
{
  "tool": "execute_read_query",
  "arguments": {
    "instance_id": "APP_DEV",
    "sql": "SELECT item_id, item_name, facility_id, on_hand_quantity, reorder_point FROM inventory WHERE on_hand_quantity < reorder_point"
  }
}
```

The MCP server validates the SQL, adds `LIMIT 100` if missing, executes it against SQLite, and returns rows.

---

### 4.2 Sales Order Lookup

User asks:

> Show me open sales orders for customer Acme.

The AI client calls:

```json
{
  "tool": "execute_read_query",
  "arguments": {
    "instance_id": "APP_DEV",
    "sql": "SELECT * FROM sales_orders WHERE customer_name = 'Acme' AND status = 'OPEN'"
  }
}
```

---

### 4.3 Schema Inspection

User asks:

> What columns are available in the inventory table?

The AI client calls:

```json
{
  "tool": "inspect_schema",
  "arguments": {
    "instance_id": "APP_DEV",
    "table_name": "inventory"
  }
}
```

---

### 4.4 Query Performance Check

User asks:

> Explain how this query will run.

The AI client calls:

```json
{
  "tool": "describe_query",
  "arguments": {
    "instance_id": "APP_DEV",
    "sql": "SELECT * FROM inventory WHERE item_id = 'ITEM-1001'"
  }
}
```

---

## 5. High-Level Architecture

```text
+-----------------------------+
| User                        |
| Natural-language question   |
+-------------+---------------+
              |
              v
+-----------------------------+
| MCP Client                  |
| Claude Desktop / Cursor     |
| - Understands intent        |
| - Chooses tool              |
| - Sends structured JSON-RPC |
+-------------+---------------+
              |
              | stdio JSON-RPC
              v
+-----------------------------+
| Python MCP Server           |
| DBLens MCP MCP             |
| - Tool registry             |
| - Input validation          |
| - SQL guardrails            |
| - Audit logging             |
+-------------+---------------+
              |
              v
+-----------------------------+
| SQLite Access Layer         |
| - Connection management     |
| - Query execution           |
| - Row formatting            |
+-------------+---------------+
              |
              v
+-----------------------------+
| Local SQLite Databases      |
| APP_DEV / APP_TEST          |
| Inventory + Sales Orders    |
+-----------------------------+
```

---

## 6. Component Design

### 6.1 MCP Client

Examples:

1. Vscode - Github Copilot

Responsibilities:

1. Starts the MCP server process.
2. Sends MCP protocol messages over stdio.
3. Lists available tools from the server.
4. Uses the LLM to decide which tool to call.
5. Sends structured `tools/call` requests.
6. Converts tool results back into natural language.

The MCP client is responsible for natural-language interpretation. The MCP server is responsible for safe execution.

---

### 6.2 Python MCP Server

Main file:

```text
src/server.py
```

Responsibilities:

1. Initialize `FastMCP`.
2. Register tools:
   - `list_instances`
   - `inspect_schema`
   - `execute_read_query`
   - `describe_query`
3. Validate tool inputs.
4. Route requests to the database layer.
5. Return JSON-serializable responses.

---

### 6.3 Configuration Layer

File:

```text
src/config.py
```

Responsibilities:

1. Load local database paths from `.env`.
2. Map instance IDs to SQLite database files.
3. Validate that a requested instance exists.

Example `.env`:

```env
DB_APP_DEV=databases/app_dev.db
DB_APP_TEST=databases/app_test.db
```

Example mapping:

```python
{
  "APP_DEV": "databases/app_dev.db",
  "APP_TEST": "databases/app_test.db"
}
```

---

### 6.4 Database Layer

File:

```text
src/db.py
```

Responsibilities:

1. Open SQLite connections.
2. Execute validated SQL.
3. Convert SQLite rows into dictionaries.
4. Close connections safely.
5. Handle database errors.

The database layer should not decide whether a query is safe. Safety checks happen before this layer is called.

---

### 6.5 SQL Guardrails Layer

File:

```text
src/guardrails.py
```

Responsibilities:

1. Allow only read-style queries in the MVP.
2. Block destructive or privileged SQL keywords.
3. Automatically append `LIMIT 100` to SELECT queries if missing.
4. Prevent multi-statement SQL execution.
5. Optionally enforce that queries start with `SELECT`, `WITH`, or `EXPLAIN`.

Blocked keywords:

```text
DROP
DELETE
TRUNCATE
ALTER
UPDATE
INSERT
REPLACE
CREATE
GRANT
REVOKE
ATTACH
DETACH
PRAGMA
```

MVP recommendation:

Only allow:

```text
SELECT
WITH
EXPLAIN
```

This is safer than trying to block every dangerous keyword.

---

### 6.6 Audit Logger

File:

```text
src/audit.py
```

Responsibilities:

1. Log every tool call.
2. Log instance ID.
3. Log SQL query.
4. Log timestamp.
5. Log whether the query was allowed or blocked.

Example log:

```text
2026-04-30T20:12:10Z | tool=execute_read_query | instance=APP_DEV | status=allowed | sql=SELECT * FROM inventory LIMIT 100
2026-04-30T20:13:15Z | tool=execute_read_query | instance=APP_DEV | status=blocked | reason=Blocked keyword DELETE
```

---

## 7. Data Model

The local database simulates a small supply-chain system with inventory and sales-order data.

### 7.1 `items`

Stores item master data.

| Column | Type | Description |
|---|---|---|
| item_id | TEXT PRIMARY KEY | Unique item identifier |
| item_name | TEXT | Human-readable item name |
| category | TEXT | Item category |
| unit_of_measure | TEXT | Unit such as EA, LB, TON |

---

### 7.2 `facilities`

Stores warehouse or plant information.

| Column | Type | Description |
|---|---|---|
| facility_id | TEXT PRIMARY KEY | Facility identifier |
| facility_name | TEXT | Facility name |
| region | TEXT | Region or location |

---

### 7.3 `inventory`

Stores current inventory by item and facility.

| Column | Type | Description |
|---|---|---|
| inventory_id | INTEGER PRIMARY KEY | Row ID |
| item_id | TEXT | FK to items |
| facility_id | TEXT | FK to facilities |
| on_hand_quantity | REAL | Current available quantity |
| reserved_quantity | REAL | Quantity already reserved |
| reorder_point | REAL | Low-inventory threshold |
| updated_at | TEXT | Last update timestamp |

Useful derived value:

```text
available_quantity = on_hand_quantity - reserved_quantity
```

---

### 7.4 `sales_orders`

Stores sales-order headers.

| Column | Type | Description |
|---|---|---|
| sales_order_id | TEXT PRIMARY KEY | Sales order identifier |
| customer_name | TEXT | Customer |
| order_date | TEXT | Order date |
| requested_ship_date | TEXT | Requested ship date |
| status | TEXT | OPEN, SHIPPED, CANCELLED, BACKORDERED |

---

### 7.5 `sales_order_lines`

Stores item-level order lines.

| Column | Type | Description |
|---|---|---|
| line_id | INTEGER PRIMARY KEY | Row ID |
| sales_order_id | TEXT | FK to sales_orders |
| item_id | TEXT | FK to items |
| facility_id | TEXT | Ship-from facility |
| ordered_quantity | REAL | Quantity ordered |
| shipped_quantity | REAL | Quantity shipped |

Useful derived value:

```text
open_quantity = ordered_quantity - shipped_quantity
```

---

## 8. MCP Tool Design

### 8.1 `list_instances`

Purpose:

List available local SQLite database instances.

Input:

```json
{}
```

Output:

```json
{
  "instances": ["APP_DEV", "APP_TEST"]
}
```

---

### 8.2 `inspect_schema`

Purpose:

Inspect tables and columns.

Input:

```json
{
  "instance_id": "APP_DEV",
  "table_name": "inventory"
}
```

`table_name` is optional. If omitted, the tool returns all tables and columns.

Output:

```json
[
  {
    "table_name": "inventory",
    "column_name": "item_id",
    "data_type": "TEXT",
    "is_primary_key": 0
  }
]
```

---

### 8.3 `execute_read_query`

Purpose:

Run a safe read-only SQL query.

Input:

```json
{
  "instance_id": "APP_DEV",
  "sql": "SELECT * FROM inventory WHERE on_hand_quantity < reorder_point"
}
```

Safety behavior:

1. Rejects non-read queries.
2. Rejects blocked keywords.
3. Rejects multi-statement SQL.
4. Appends `LIMIT 100` if missing.
5. Logs the query.

Output:

```json
{
  "sql_executed": "SELECT * FROM inventory WHERE on_hand_quantity < reorder_point LIMIT 100",
  "row_count": 2,
  "rows": [
    {
      "item_id": "ITEM-1001",
      "facility_id": "FAC-UT",
      "on_hand_quantity": 20,
      "reorder_point": 50
    }
  ]
}
```

---

### 8.4 `describe_query`

Purpose:

Run SQLite `EXPLAIN QUERY PLAN`.

Input:

```json
{
  "instance_id": "APP_DEV",
  "sql": "SELECT * FROM inventory WHERE item_id = 'ITEM-1001'"
}
```

Output:

```json
{
  "query_plan": [
    {
      "id": 2,
      "parent": 0,
      "notused": 0,
      "detail": "SEARCH inventory USING INDEX idx_inventory_item_id"
    }
  ]
}
```

---

### 8.5 Optional Future Tool: `compare_schema`

Purpose:

Compare schema between two local database instances.

Input:

```json
{
  "left_instance_id": "APP_DEV",
  "right_instance_id": "APP_TEST",
  "table_name": "inventory"
}
```

Output:

```json
{
  "table_name": "inventory",
  "only_in_left": [],
  "only_in_right": ["safety_stock"],
  "type_mismatches": []
}
```

---

### 8.6 Optional Future Tool: `inventory_health_summary`

Purpose:

A business-friendly tool that avoids making the LLM write SQL.

Input:

```json
{
  "instance_id": "APP_DEV"
}
```

Output:

```json
{
  "low_inventory_count": 4,
  "backordered_order_count": 3,
  "top_constrained_items": [
    {
      "item_id": "ITEM-1001",
      "item_name": "Steel Coil",
      "available_quantity": 12,
      "open_sales_order_quantity": 40
    }
  ]
}
```

This is safer and more reliable than exposing a generic SQL execution tool.

---

## 9. Request Flow

### 9.1 Tool Discovery Flow

1. Cursor/Claude starts the MCP server using local configuration.
2. MCP client sends `tools/list`.
3. Server returns tool names, descriptions, and argument schemas.
4. LLM now knows what actions are available.

---

### 9.2 Query Execution Flow

1. User asks a natural-language question.
2. LLM decides that `execute_read_query` is the correct tool.
3. LLM generates SQL and structured arguments.
4. MCP client sends a JSON-RPC `tools/call` request.
5. MCP server validates the instance ID.
6. MCP server validates SQL safety.
7. MCP server appends `LIMIT 100` if needed.
8. MCP server logs the query.
9. MCP server executes the SQL against SQLite.
10. MCP server returns structured rows.
11. LLM summarizes the rows for the user.

---

## 10. Example MCP Tool Call

Natural-language question:

> Which inventory items are below reorder point and have open sales orders?

Possible generated SQL:

```sql
SELECT
  i.item_id,
  it.item_name,
  i.facility_id,
  i.on_hand_quantity,
  i.reserved_quantity,
  i.reorder_point,
  SUM(sol.ordered_quantity - sol.shipped_quantity) AS open_order_quantity
FROM inventory i
JOIN items it ON i.item_id = it.item_id
JOIN sales_order_lines sol
  ON i.item_id = sol.item_id
 AND i.facility_id = sol.facility_id
JOIN sales_orders so
  ON sol.sales_order_id = so.sales_order_id
WHERE i.on_hand_quantity < i.reorder_point
  AND so.status IN ('OPEN', 'BACKORDERED')
GROUP BY
  i.item_id,
  it.item_name,
  i.facility_id,
  i.on_hand_quantity,
  i.reserved_quantity,
  i.reorder_point
```

The server will execute:

```sql
... LIMIT 100
```

if the original SQL does not contain a limit.

---

## 11. Safety Design

### 11.1 Why Guardrails Are Needed

The LLM is allowed to generate tool arguments. That means it could generate risky SQL by accident. The MCP server must be the safety boundary.

### 11.2 Recommended MVP Rule

Only allow read queries:

```text
SELECT
WITH
EXPLAIN
```

Reject everything else.

### 11.3 Multi-Statement Blocking

Reject SQL containing multiple statements, for example:

```sql
SELECT * FROM inventory; DELETE FROM inventory;
```

### 11.4 Row Limit

Automatically append:

```sql
LIMIT 100
```

This prevents huge result sets from overwhelming the LLM context window.

### 11.5 Local-Only Scope

The server should run locally through stdio and should not expose an HTTP port for the MVP.

---

## 12. Error Handling

### 12.1 Unknown Instance

Input:

```json
{
  "instance_id": "APP_PROD"
}
```

Output:

```json
{
  "error": "Unknown instance_id: APP_PROD",
  "available_instances": ["APP_DEV", "APP_TEST"]
}
```

### 12.2 Unsafe SQL

Input:

```sql
DELETE FROM inventory
```

Output:

```json
{
  "error": "Unsafe SQL rejected",
  "reason": "Only SELECT, WITH, and EXPLAIN queries are allowed"
}
```

### 12.3 SQL Syntax Error

Output:

```json
{
  "error": "SQL execution failed",
  "details": "near 'FORM': syntax error"
}
```

---

## 13. Project Structure

```text
DBLens MCP-mcp/
  README.md
  requirements.txt
  .env.example
  create_sample_db.py
  databases/
    app_dev.db
    app_test.db
  src/
    server.py
    config.py
    db.py
    guardrails.py
    audit.py
    tools/
      __init__.py
      list_instances.py
      inspect_schema.py
      execute_read_query.py
      describe_query.py
```

For a small learning project, keeping tools directly in `server.py` is acceptable. As the project grows, move each tool into its own module.

---

## 14. Local Development Setup

### 14.1 Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 14.2 Install Dependencies

```bash
pip install -r requirements.txt
```

### 14.3 Create Sample Database

```bash
python create_sample_db.py
```

### 14.4 Run MCP Server Manually

```bash
python src/server.py
```

Normally, the server is started by Cursor or Claude Desktop, not directly by the user.

---

## 15. Cursor Configuration

Create:

```text
.cursor/mcp.json
```

Example:

```json
{
  "mcpServers": {
    "DBLens MCP": {
      "command": "python",
      "args": ["/absolute/path/to/DBLens MCP-mcp/src/server.py"]
    }
  }
}
```

---

## 16. Claude Desktop Configuration

Example concept:

```json
{
  "mcpServers": {
    "DBLens MCP": {
      "command": "python",
      "args": ["/absolute/path/to/DBLens MCP-mcp/src/server.py"]
    }
  }
}
```

Use the exact config location required by Claude Desktop on your operating system.

---

## 17. Testing Strategy

### 17.1 Unit Tests

Test:

1. Instance loading.
2. Unknown instance behavior.
3. SQL keyword blocking.
4. Automatic limit insertion.
5. Multi-statement rejection.
6. Audit log writing.

### 17.2 Integration Tests

Test:

1. `list_instances` returns configured DBs.
2. `inspect_schema` returns inventory and sales-order tables.
3. `execute_read_query` returns expected rows.
4. `describe_query` returns SQLite query plan.

### 17.3 Manual AI Client Tests

Ask Cursor/Claude:

1. "What tables are in APP_DEV?"
2. "Show inventory below reorder point."
3. "Which sales orders are backordered?"
4. "Join inventory and sales orders to find constrained items."
5. "Try deleting an inventory row."  
   Expected: the tool should reject the query.

---

## 18. Future Enhancements

1. Add schema comparison between APP_DEV and APP_TEST.
2. Add predefined business tools such as `get_low_inventory_items`.
3. Add query result summarization limits.
4. Add CSV export for query results.
5. Add SQLite read-only connection mode.
6. Add role-based tool exposure.
7. Add a Streamable HTTP transport option.
8. Add richer audit logs in JSONL format.
9. Add table allowlists.
10. Add column masking for sensitive data.

---

## 19. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| LLM generates unsafe SQL | Data corruption | Allow only SELECT/WITH/EXPLAIN |
| Large query result | Context overflow | Auto LIMIT 100 |
| Wrong database selected | Incorrect answer | Require explicit `instance_id` |
| SQL injection through table name | Unsafe execution | Validate identifiers using regex |
| Sensitive data exposure | Privacy issue | Column allowlist/masking |
| Audit gaps | Hard to debug | Log every tool call |

---

## 20. MVP Scope

The MVP is complete when:

1. Cursor/Claude can connect to the MCP server.
2. User can ask for available instances.
3. User can inspect schema.
4. User can run safe read queries.
5. Unsafe SQL is rejected.
6. All queries are logged.
7. The sample database contains inventory and sales-order data.

---

## 21. Recommended Implementation Order

1. Create SQLite sample database.
2. Build config loader.
3. Build database query helper.
4. Build SQL guardrails.
5. Register `list_instances`.
6. Register `inspect_schema`.
7. Register `execute_read_query`.
8. Register `describe_query`.
9. Add audit logging.
10. Connect to Cursor/Claude.
11. Add tests.
12. Polish README and examples.

---

## 22. Summary

DBLens MCP MCP is a practical learning project because it demonstrates the core MCP pattern:

```text
Natural language → LLM tool selection → MCP structured call → Safe backend execution → Structured result → Natural-language answer
```

The project is useful because it mirrors real enterprise workflows while remaining simple enough to run locally. By using SQLite and inventory/sales-order data, it avoids cloud setup complexity while still showing schema inspection, database querying, safety guardrails, audit logging, and MCP client integration.