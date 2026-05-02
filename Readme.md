# DBLens MCP

DBLens MCP is a local Python MCP server for safe read-only exploration of SQLite inventory and sales-order data.

The server exposes three implemented MCP tools:

- `list_instances`: list configured SQLite database instances.
- `inspect_schema`: inspect tables and columns.
- `execute_read_query`: execute a guarded read-only SQL query.

## Local Install

Run these commands from the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip3 install -r requirements.txt
cp .env.example .env
python3 create_sample_db.py
```

The `.env` file should contain:

```env
DB_APP_DEV=databases/app_dev.db
DB_APP_TEST=databases/app_test.db
```

`create_sample_db.py` creates the local SQLite files configured in `.env`.

## Run Locally

Start the MCP server over stdio:

```bash
.venv/bin/python src/server.py
```

The command waits for an MCP client on stdin/stdout. That is normal. Stop it with `Ctrl+C`.

For a one-off terminal test, use `fastmcp call`:

```bash
.venv/bin/fastmcp call \
  --command '.venv/bin/python src/server.py' \
  --target list_instances \
  --json
```

Inspect a table:

```bash
.venv/bin/fastmcp call \
  --command '.venv/bin/python src/server.py' \
  --target inspect_schema \
  --input-json '{"instance_id":"APP_DEV","table_name":"sales_orders"}' \
  --json
```

Run a safe read query:

```bash
.venv/bin/fastmcp call \
  --command '.venv/bin/python src/server.py' \
  --target execute_read_query \
  --input-json '{"instance_id":"APP_DEV","sql":"SELECT sales_order_id, customer_name, status FROM sales_orders WHERE status = '\''OPEN'\''"}' \
  --json
```

## Run With Codex

Add DBLens as a Codex MCP server:

```bash
codex mcp add dblens -- /Users/vinitajain/DBLens-MCP/.venv/bin/python /Users/vinitajain/DBLens-MCP/src/server.py
```

Verify Codex can see it:

```bash
codex mcp list
```

Expected entry:

```text
dblens  /Users/vinitajain/DBLens-MCP/.venv/bin/python  /Users/vinitajain/DBLens-MCP/src/server.py  enabled
```

Then ask Codex:

```text
Use the DBLens MCP server to list available database instances.
```

Example prompts:

```text
Use DBLens to get columns in the sales_orders table.
Use DBLens to get all open orders.
Use DBLens to run a safe read query against APP_DEV:
SELECT item_id, facility_id, on_hand_quantity FROM inventory
```

## Codex Config

Codex stores MCP servers in:

```text
~/.codex/config.toml
```

The equivalent config entry is:

```toml
[mcp_servers.dblens]
command = "/Users/vinitajain/DBLens-MCP/.venv/bin/python"
args = ["/Users/vinitajain/DBLens-MCP/src/server.py"]
cwd = "/Users/vinitajain/DBLens-MCP"
```

## Implemented Safety Behavior

`execute_read_query` currently:

1. Validates `instance_id`.
2. Rejects unsafe SQL.
3. Rejects multi-statement SQL.
4. Appends `LIMIT 100` when a read query does not include a limit.
5. Returns rows as JSON-serializable dictionaries.

Only SELECT-style read queries are allowed.
