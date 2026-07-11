#!/usr/bin/env node
/**
 * odoo-mcp — Odoo MCP server for Personal AI Employee (Gold tier)
 *
 * Communicates with Odoo 17 Community via the standard JSON-RPC external API.
 * Exposes tools for invoice management, customer lookup, and accounting summaries.
 *
 * Environment variables:
 *   ODOO_URL      — default: http://localhost:8069
 *   ODOO_DB       — default: odoo
 *   ODOO_USERNAME — default: admin
 *   ODOO_PASSWORD — default: admin
 *   DRY_RUN       — default: true
 *
 * Setup:
 *   cd mcp_servers/odoo_mcp && npm install
 *   docker compose up -d   (start Odoo first)
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const ODOO_URL      = (process.env.ODOO_URL      || "http://localhost:8069").replace(/\/$/, "");
const ODOO_DB       = process.env.ODOO_DB       || "odoo";
const ODOO_USERNAME = process.env.ODOO_USERNAME || "admin";
const ODOO_PASSWORD = process.env.ODOO_PASSWORD || "admin";
const DRY_RUN       = (process.env.DRY_RUN || "true").toLowerCase() === "true";

// ---------------------------------------------------------------------------
// Session state — re-authenticate when session expires
// ---------------------------------------------------------------------------

let _session = { uid: null, cookie: null };

async function authenticate() {
  const res = await fetch(`${ODOO_URL}/web/session/authenticate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      method: "call",
      params: { db: ODOO_DB, login: ODOO_USERNAME, password: ODOO_PASSWORD },
    }),
  });

  const setCookie = res.headers.get("set-cookie") || "";
  const data = await res.json();

  if (!data.result || !data.result.uid) {
    throw new Error(`Odoo authentication failed: ${JSON.stringify(data.error || data.result)}`);
  }

  _session.uid    = data.result.uid;
  _session.cookie = setCookie.split(";")[0];
  return _session;
}

// ---------------------------------------------------------------------------
// JSON-RPC helper
// ---------------------------------------------------------------------------

async function callKw(model, method, args = [], kwargs = {}) {
  if (!_session.uid) await authenticate();

  const body = JSON.stringify({
    jsonrpc: "2.0",
    method: "call",
    params: {
      model,
      method,
      args,
      kwargs: { context: { lang: "en_US", tz: "UTC" }, ...kwargs },
    },
  });

  const res = await fetch(`${ODOO_URL}/web/dataset/call_kw`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Cookie: _session.cookie || "",
    },
    body,
  });

  const data = await res.json();

  if (data.error) {
    // Session expired — re-authenticate once and retry
    if (data.error.data?.name?.includes("SessionExpiredException")) {
      _session = { uid: null, cookie: null };
      await authenticate();
      return callKw(model, method, args, kwargs);
    }
    throw new Error(`Odoo RPC error: ${JSON.stringify(data.error)}`);
  }

  return data.result;
}

// ---------------------------------------------------------------------------
// MCP Server
// ---------------------------------------------------------------------------

const server = new Server(
  { name: "odoo-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

// --- Tool list ---

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "get_accounting_summary",
      description:
        "Get a high-level accounting summary for the current month: " +
        "total invoiced, total paid, total outstanding, and invoice count.",
      inputSchema: { type: "object", properties: {}, required: [] },
    },
    {
      name: "list_invoices",
      description: "List customer or vendor invoices/bills.",
      inputSchema: {
        type: "object",
        properties: {
          type:  { type: "string", enum: ["out_invoice","in_invoice","out_refund","in_refund"], description: "Invoice type (default: out_invoice)" },
          state: { type: "string", enum: ["draft","posted","cancel","all"], description: "Filter by state (default: all)" },
          limit: { type: "number", description: "Max results (default: 20)" },
        },
        required: [],
      },
    },
    {
      name: "create_invoice",
      description: "Create a draft customer invoice in Odoo.",
      inputSchema: {
        type: "object",
        properties: {
          partner_name: { type: "string", description: "Customer name (must exist in Odoo, or will be created)" },
          amount:       { type: "number", description: "Invoice amount (tax-exclusive)" },
          description:  { type: "string", description: "Line item description" },
          due_date:     { type: "string", description: "Due date in YYYY-MM-DD format (optional)" },
        },
        required: ["partner_name", "amount", "description"],
      },
    },
    {
      name: "list_customers",
      description: "List customers (contacts) in Odoo.",
      inputSchema: {
        type: "object",
        properties: {
          search: { type: "string", description: "Filter by name (optional)" },
          limit:  { type: "number", description: "Max results (default: 20)" },
        },
        required: [],
      },
    },
    {
      name: "create_customer",
      description: "Create a new customer/contact in Odoo.",
      inputSchema: {
        type: "object",
        properties: {
          name:  { type: "string", description: "Customer full name" },
          email: { type: "string", description: "Email address (optional)" },
          phone: { type: "string", description: "Phone number (optional)" },
        },
        required: ["name"],
      },
    },
  ],
}));

// --- Tool execution ---

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args = {} } = request.params;

  try {
    switch (name) {

      case "get_accounting_summary": {
        const now = new Date();
        const monthStart = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
        const domain = [
          ["move_type", "=", "out_invoice"],
          ["invoice_date", ">=", monthStart],
          ["state", "!=", "cancel"],
        ];

        const invoices = await callKw("account.move", "search_read", [domain], {
          fields: ["name", "amount_total", "amount_residual", "state"],
          limit: 200,
        });

        const total_invoiced  = invoices.reduce((s, i) => s + (i.amount_total    || 0), 0);
        const total_outstanding = invoices.reduce((s, i) => s + (i.amount_residual || 0), 0);
        const total_paid      = total_invoiced - total_outstanding;
        const invoice_count   = invoices.length;

        return {
          content: [{
            type: "text",
            text:
              `Accounting Summary (current month from ${monthStart}):\n` +
              `  Invoiced:     $${total_invoiced.toFixed(2)}\n` +
              `  Paid:         $${total_paid.toFixed(2)}\n` +
              `  Outstanding:  $${total_outstanding.toFixed(2)}\n` +
              `  Invoice count: ${invoice_count}`,
          }],
        };
      }

      case "list_invoices": {
        const move_type = args.type  || "out_invoice";
        const state     = args.state || "all";
        const limit     = args.limit || 20;

        const domain = [["move_type", "=", move_type]];
        if (state !== "all") domain.push(["state", "=", state]);

        const records = await callKw("account.move", "search_read", [domain], {
          fields: ["name", "partner_id", "amount_total", "amount_residual", "state", "invoice_date", "invoice_date_due"],
          limit,
          order: "invoice_date desc",
        });

        const lines = records.map(r =>
          `  [${r.id}] ${r.name} | ${r.partner_id?.[1] || "—"} | ` +
          `$${r.amount_total?.toFixed(2)} | state:${r.state} | due:${r.invoice_date_due || "—"}`
        );

        return {
          content: [{
            type: "text",
            text: records.length
              ? `Found ${records.length} invoice(s):\n${lines.join("\n")}`
              : "No invoices found matching the criteria.",
          }],
        };
      }

      case "create_invoice": {
        if (DRY_RUN) {
          return {
            content: [{
              type: "text",
              text:
                `[DRY RUN] Would create invoice:\n` +
                `  Customer: ${args.partner_name}\n` +
                `  Amount: $${args.amount}\n` +
                `  Description: ${args.description}\n` +
                `  Due: ${args.due_date || "not set"}`,
            }],
          };
        }

        // Find or create partner
        const partners = await callKw("res.partner", "search_read",
          [[["name", "ilike", args.partner_name], ["customer_rank", ">", 0]]],
          { fields: ["id", "name"], limit: 1 }
        );

        let partner_id;
        if (partners.length) {
          partner_id = partners[0].id;
        } else {
          partner_id = await callKw("res.partner", "create", [{ name: args.partner_name, customer_rank: 1 }]);
        }

        const invoice_vals = {
          move_type: "out_invoice",
          partner_id,
          invoice_line_ids: [[0, 0, {
            name: args.description,
            quantity: 1,
            price_unit: args.amount,
          }]],
        };
        if (args.due_date) invoice_vals.invoice_date_due = args.due_date;

        const invoice_id = await callKw("account.move", "create", [invoice_vals]);
        const [inv] = await callKw("account.move", "read", [[invoice_id]], { fields: ["name", "state"] });

        return {
          content: [{
            type: "text",
            text:
              `Invoice created successfully.\n` +
              `  ID: ${invoice_id}\n` +
              `  Reference: ${inv.name}\n` +
              `  State: ${inv.state} (draft — post manually in Odoo or ask me to post it)`,
          }],
        };
      }

      case "list_customers": {
        const domain = [["customer_rank", ">", 0]];
        if (args.search) domain.push(["name", "ilike", args.search]);

        const records = await callKw("res.partner", "search_read", [domain], {
          fields: ["id", "name", "email", "phone"],
          limit: args.limit || 20,
          order: "name asc",
        });

        const lines = records.map(r =>
          `  [${r.id}] ${r.name} | ${r.email || "—"} | ${r.phone || "—"}`
        );

        return {
          content: [{
            type: "text",
            text: records.length
              ? `Found ${records.length} customer(s):\n${lines.join("\n")}`
              : "No customers found.",
          }],
        };
      }

      case "create_customer": {
        if (DRY_RUN) {
          return {
            content: [{
              type: "text",
              text: `[DRY RUN] Would create customer: ${args.name} | ${args.email || "—"} | ${args.phone || "—"}`,
            }],
          };
        }

        const vals = { name: args.name, customer_rank: 1 };
        if (args.email) vals.email = args.email;
        if (args.phone) vals.phone = args.phone;

        const id = await callKw("res.partner", "create", [vals]);
        return {
          content: [{
            type: "text",
            text: `Customer created.\n  ID: ${id}\n  Name: ${args.name}`,
          }],
        };
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }

  } catch (err) {
    const msg = err.message || String(err);
    const isConnError = msg.includes("ECONNREFUSED") || msg.includes("fetch failed");
    return {
      content: [{
        type: "text",
        text: isConnError
          ? `Odoo is unreachable at ${ODOO_URL}. Is Docker running? Try: docker compose up -d`
          : `Odoo MCP error: ${msg}`,
      }],
      isError: true,
    };
  }
});

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------

const transport = new StdioServerTransport();
await server.connect(transport);
