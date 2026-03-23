#!/usr/bin/env node
/**
 * gmail-mcp — Gmail MCP server for Personal AI Employee (Silver tier)
 *
 * Exposes one tool:
 *   send_email(to, subject, body, thread_id?, in_reply_to?)
 *
 * Launched automatically by Claude Code when it reads .claude/settings.json.
 * Credentials are read from env vars (set in .env / settings.json env block):
 *   GMAIL_TOKEN_PATH        — path to OAuth token JSON (default: secrets/gmail_token.json)
 *   GMAIL_CREDENTIALS_PATH  — path to OAuth credentials JSON (default: secrets/gmail_credentials.json)
 *   DRY_RUN                 — "true" → log only, never actually send (default: true)
 *
 * Setup (one time):
 *   cd mcp_servers/gmail_mcp && npm install
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { google } from "googleapis";
import { readFileSync } from "fs";
import { resolve } from "path";
import { Buffer } from "buffer";

// ---------------------------------------------------------------------------
// Config — paths resolved relative to CWD (project root when launched by Claude)
// ---------------------------------------------------------------------------

const TOKEN_PATH = resolve(
  process.cwd(),
  process.env.GMAIL_TOKEN_PATH || "secrets/gmail_token.json"
);
const CREDS_PATH = resolve(
  process.cwd(),
  process.env.GMAIL_CREDENTIALS_PATH || "secrets/gmail_credentials.json"
);
const DRY_RUN = (process.env.DRY_RUN || "true").toLowerCase() === "true";

// ---------------------------------------------------------------------------
// Gmail OAuth2 helper
// ---------------------------------------------------------------------------

function getOAuth2Client() {
  const creds = JSON.parse(readFileSync(CREDS_PATH, "utf-8"));
  const { client_secret, client_id, redirect_uris } =
    creds.installed || creds.web;
  const oAuth2Client = new google.auth.OAuth2(
    client_id,
    client_secret,
    redirect_uris[0]
  );
  const token = JSON.parse(readFileSync(TOKEN_PATH, "utf-8"));
  oAuth2Client.setCredentials(token);
  return oAuth2Client;
}

// ---------------------------------------------------------------------------
// MIME builder — plain-text email, no external dependencies
// ---------------------------------------------------------------------------

function buildRawMessage({ to, subject, body, in_reply_to, thread_id }) {
  const lines = [
    `To: ${to}`,
    `Subject: ${subject}`,
    "MIME-Version: 1.0",
    "Content-Type: text/plain; charset=UTF-8",
    "Content-Transfer-Encoding: quoted-printable",
  ];
  if (in_reply_to) {
    lines.push(`In-Reply-To: ${in_reply_to}`);
    lines.push(`References: ${in_reply_to}`);
  }
  lines.push("", body);

  const raw = Buffer.from(lines.join("\r\n"), "utf-8").toString("base64url");
  const payload = { raw };
  if (thread_id) payload.threadId = thread_id;
  return payload;
}

// ---------------------------------------------------------------------------
// MCP Server
// ---------------------------------------------------------------------------

const server = new Server(
  { name: "gmail-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

// --- Tool list ---

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "send_email",
      description:
        "Send a plain-text email via the Gmail API. " +
        "Only call this after the human has approved the email in /Pending_Approval/Approved/. " +
        "Returns a confirmation string with the Gmail message ID on success.",
      inputSchema: {
        type: "object",
        properties: {
          to: {
            type: "string",
            description: "Recipient email address (e.g. user@example.com)",
          },
          subject: {
            type: "string",
            description: "Email subject line",
          },
          body: {
            type: "string",
            description: "Plain-text email body (no markdown, no HTML)",
          },
          thread_id: {
            type: "string",
            description:
              "Gmail thread ID to reply into — copy from the approval file frontmatter (optional)",
          },
          in_reply_to: {
            type: "string",
            description:
              "Message-ID header of the email being replied to — copy from the approval file frontmatter (optional)",
          },
        },
        required: ["to", "subject", "body"],
      },
    },
  ],
}));

// --- Tool execution ---

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name !== "send_email") {
    throw new Error(`Unknown tool: ${request.params.name}`);
  }

  const {
    to,
    subject,
    body,
    thread_id = "",
    in_reply_to = "",
  } = request.params.arguments;

  // Dry-run mode — never actually send
  if (DRY_RUN) {
    return {
      content: [
        {
          type: "text",
          text:
            `[DRY RUN] gmail-mcp would send email:\n` +
            `  To:      ${to}\n` +
            `  Subject: ${subject}\n` +
            `  Body:    ${body.slice(0, 120)}${body.length > 120 ? "..." : ""}`,
        },
      ],
    };
  }

  // Validate credentials exist before attempting to send
  try {
    readFileSync(TOKEN_PATH);
    readFileSync(CREDS_PATH);
  } catch (err) {
    return {
      content: [
        {
          type: "text",
          text:
            `gmail-mcp: credentials not found.\n` +
            `  TOKEN_PATH: ${TOKEN_PATH}\n` +
            `  CREDS_PATH: ${CREDS_PATH}\n` +
            `  Run: python setup/gmail_oauth_setup.py`,
        },
      ],
      isError: true,
    };
  }

  try {
    const auth = getOAuth2Client();
    const gmail = google.gmail({ version: "v1", auth });

    // Prefix "Re:" if replying
    const finalSubject =
      subject.startsWith("Re:") ? subject
      : in_reply_to             ? `Re: ${subject}`
      :                           subject;

    const payload = buildRawMessage({
      to,
      subject: finalSubject,
      body,
      in_reply_to,
      thread_id,
    });

    const sent = await gmail.users.messages.send({
      userId: "me",
      requestBody: payload,
    });

    return {
      content: [
        {
          type: "text",
          text:
            `Email sent successfully.\n` +
            `  To:         ${to}\n` +
            `  Subject:    ${finalSubject}\n` +
            `  Message ID: ${sent.data.id}\n` +
            `  Thread ID:  ${sent.data.threadId}`,
        },
      ],
    };
  } catch (err) {
    return {
      content: [
        {
          type: "text",
          text: `gmail-mcp: failed to send email.\n  Error: ${err.message}`,
        },
      ],
      isError: true,
    };
  }
});

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------

const transport = new StdioServerTransport();
await server.connect(transport);
