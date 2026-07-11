#!/usr/bin/env node
/**
 * facebook-mcp — Facebook & Instagram MCP server for Personal AI Employee (Gold tier)
 *
 * Uses Meta Graph API v21.0 to post content and retrieve insights.
 *
 * Environment variables:
 *   FACEBOOK_APP_ID
 *   FACEBOOK_APP_SECRET
 *   FACEBOOK_PAGE_ID
 *   FACEBOOK_PAGE_ACCESS_TOKEN
 *   INSTAGRAM_BUSINESS_ACCOUNT_ID
 *   DRY_RUN — default: true
 *
 * Setup:
 *   cd mcp_servers/facebook_mcp && npm install
 *   Add credentials to .env (and .mcp.json env block)
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const GRAPH_BASE = "https://graph.facebook.com/v21.0";

const PAGE_ID    = process.env.FACEBOOK_PAGE_ID               || "";
const PAGE_TOKEN = process.env.FACEBOOK_PAGE_ACCESS_TOKEN     || "";
const APP_ID     = process.env.FACEBOOK_APP_ID                || "";
const APP_SECRET = process.env.FACEBOOK_APP_SECRET            || "";
const IG_ID      = process.env.INSTAGRAM_BUSINESS_ACCOUNT_ID  || "";
const DRY_RUN    = (process.env.DRY_RUN || "true").toLowerCase() === "true";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function credentialError() {
  return {
    content: [{
      type: "text",
      text:
        "Facebook credentials not configured.\n" +
        "Add to .env:\n" +
        "  FACEBOOK_PAGE_ID\n" +
        "  FACEBOOK_PAGE_ACCESS_TOKEN\n" +
        "  INSTAGRAM_BUSINESS_ACCOUNT_ID\n" +
        "Then restart the orchestrator.",
    }],
    isError: true,
  };
}

async function graphGet(path, params = {}) {
  const url = new URL(`${GRAPH_BASE}${path}`);
  url.searchParams.set("access_token", PAGE_TOKEN);
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  const res = await fetch(url.toString());
  const data = await res.json();
  if (data.error) throw new Error(`Graph API error: ${JSON.stringify(data.error)}`);
  return data;
}

async function graphPost(path, body = {}) {
  const url = `${GRAPH_BASE}${path}?access_token=${encodeURIComponent(PAGE_TOKEN)}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (data.error) throw new Error(`Graph API error: ${JSON.stringify(data.error)}`);
  return data;
}

// ---------------------------------------------------------------------------
// MCP Server
// ---------------------------------------------------------------------------

const server = new Server(
  { name: "facebook-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

// --- Tool list ---

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "post_facebook",
      description: "Post a text message to the Facebook Page.",
      inputSchema: {
        type: "object",
        properties: {
          message: { type: "string", description: "The post text to publish" },
        },
        required: ["message"],
      },
    },
    {
      name: "post_comment",
      description: "Post a comment on a Facebook Page post.",
      inputSchema: {
        type: "object",
        properties: {
          post_id: { type: "string", description: "Facebook post ID, usually pageid_postid" },
          message: { type: "string", description: "The comment text to publish" },
        },
        required: ["post_id", "message"],
      },
    },
    {
      name: "post_instagram",
      description:
        "Post a caption (and optional image) to the Instagram Business account. " +
        "Image URL must be publicly accessible. If no image_url is provided, a text-only note is logged.",
      inputSchema: {
        type: "object",
        properties: {
          caption:   { type: "string", description: "Post caption text including hashtags" },
          image_url: { type: "string", description: "Publicly accessible image URL (optional)" },
        },
        required: ["caption"],
      },
    },
    {
      name: "get_facebook_insights",
      description: "Get Facebook Page engagement metrics.",
      inputSchema: {
        type: "object",
        properties: {
          period: { type: "string", enum: ["day", "week", "days_28"], description: "Reporting period (default: week)" },
        },
        required: [],
      },
    },
    {
      name: "get_instagram_insights",
      description: "Get Instagram Business account insights.",
      inputSchema: {
        type: "object",
        properties: {
          period: { type: "string", enum: ["day", "week"], description: "Reporting period (default: week)" },
        },
        required: [],
      },
    },
    {
      name: "get_page_info",
      description: "Get basic Facebook Page information (name, fan count, link).",
      inputSchema: { type: "object", properties: {}, required: [] },
    },
    {
      name: "validate_token",
      description: "Validate the configured Facebook Page access token without exposing it.",
      inputSchema: { type: "object", properties: {}, required: [] },
    },
    {
      name: "list_page_posts",
      description: "List recent Facebook Page posts with IDs, messages, timestamps, and engagement counts.",
      inputSchema: {
        type: "object",
        properties: {
          limit: { type: "number", description: "Max posts to return (default: 5)" },
        },
        required: [],
      },
    },
    {
      name: "list_post_comments",
      description: "List recent comments for a Facebook Page post ID.",
      inputSchema: {
        type: "object",
        properties: {
          post_id: { type: "string", description: "Facebook post ID, usually pageid_postid" },
          limit: { type: "number", description: "Max comments to return (default: 10)" },
        },
        required: ["post_id"],
      },
    },
  ],
}));

// --- Tool execution ---

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args = {} } = request.params;

  if (!PAGE_TOKEN || !PAGE_ID) return credentialError();

  try {
    switch (name) {

      case "post_facebook": {
        if (DRY_RUN) {
          return {
            content: [{
              type: "text",
              text: `[DRY RUN] Would post to Facebook Page (${PAGE_ID}):\n${args.message}`,
            }],
          };
        }
        const result = await graphPost(`/${PAGE_ID}/feed`, { message: args.message });
        const post_id = result.id;
        const url = `https://www.facebook.com/${post_id.replace("_", "/posts/")}`;
        return {
          content: [{
            type: "text",
            text: `Facebook post published.\n  Post ID: ${post_id}\n  URL: ${url}`,
          }],
        };
      }

      case "post_comment": {
        if (DRY_RUN) {
          return {
            content: [{
              type: "text",
              text: `[DRY RUN] Would comment on Facebook post (${args.post_id}):\n${args.message}`,
            }],
          };
        }
        const result = await graphPost(`/${args.post_id}/comments`, { message: args.message });
        return {
          content: [{
            type: "text",
            text: `Facebook comment published.\n  Comment ID: ${result.id}`,
          }],
        };
      }

      case "post_instagram": {
        if (!IG_ID) {
          return {
            content: [{
              type: "text",
              text: "INSTAGRAM_BUSINESS_ACCOUNT_ID not configured in .env.",
            }],
            isError: true,
          };
        }
        if (DRY_RUN) {
          return {
            content: [{
              type: "text",
              text:
                `[DRY RUN] Would post to Instagram (${IG_ID}):\n` +
                `Caption: ${args.caption}\n` +
                `Image URL: ${args.image_url || "(none — text-only not supported by Graph API)"}`,
            }],
          };
        }
        if (!args.image_url) {
          return {
            content: [{
              type: "text",
              text:
                "Instagram Graph API requires an image_url to publish a post.\n" +
                "Please provide a publicly accessible image URL in the approval file's image_url field.\n" +
                "Caption was not posted.",
            }],
            isError: true,
          };
        }
        // Step 1: Create media container
        const container = await graphPost(`/${IG_ID}/media`, {
          image_url: args.image_url,
          caption: args.caption,
        });
        const creation_id = container.id;

        // Step 2: Publish
        const publish = await graphPost(`/${IG_ID}/media_publish`, { creation_id });
        return {
          content: [{
            type: "text",
            text: `Instagram post published.\n  Media ID: ${publish.id}`,
          }],
        };
      }

      case "get_facebook_insights": {
        const period = args.period || "week";
        const metrics = "page_post_engagements,page_follows,page_views_total,page_actions_post_reactions_total";
        const data = await graphGet(`/${PAGE_ID}/insights`, { metric: metrics, period });
        const values = {};
        for (const item of (data.data || [])) {
          const last = item.values?.slice(-1)[0];
          values[item.name] = last?.value ?? "—";
        }
        const reactions = values.page_actions_post_reactions_total || {};
        const reactionTotal = typeof reactions === "object"
          ? Object.values(reactions).reduce((sum, value) => sum + (Number(value) || 0), 0)
          : Number(reactions) || 0;
        return {
          content: [{
            type: "text",
            text:
              `Facebook Page Insights (${period}):\n` +
              `  Post Engagements: ${values.page_post_engagements ?? "—"}\n` +
              `  Page Follows:     ${values.page_follows ?? "—"}\n` +
              `  Page Views:       ${values.page_views_total ?? "—"}\n` +
              `  Reactions:        ${reactionTotal}`,
          }],
        };
      }

      case "get_instagram_insights": {
        if (!IG_ID) return { content: [{ type: "text", text: "INSTAGRAM_BUSINESS_ACCOUNT_ID not set." }], isError: true };
        const period = args.period || "week";
        const metrics = "impressions,reach,profile_views,follower_count";
        const data = await graphGet(`/${IG_ID}/insights`, { metric: metrics, period });
        const values = {};
        for (const item of (data.data || [])) {
          const last = item.values?.slice(-1)[0];
          values[item.name] = last?.value ?? "—";
        }
        return {
          content: [{
            type: "text",
            text:
              `Instagram Insights (${period}):\n` +
              `  Impressions:   ${values.impressions ?? "—"}\n` +
              `  Reach:         ${values.reach ?? "—"}\n` +
              `  Profile Views: ${values.profile_views ?? "—"}\n` +
              `  Followers:     ${values.follower_count ?? "—"}`,
          }],
        };
      }

      case "get_page_info": {
        const data = await graphGet(`/${PAGE_ID}`, { fields: "name,fan_count,link" });
        return {
          content: [{
            type: "text",
            text:
              `Facebook Page Info:\n` +
              `  Name:  ${data.name}\n` +
              `  Fans:  ${data.fan_count}\n` +
              `  Link:  ${data.link || `https://www.facebook.com/${PAGE_ID}`}`,
          }],
        };
      }

      case "validate_token": {
        if (!APP_ID || !APP_SECRET) {
          return {
            content: [{ type: "text", text: "FACEBOOK_APP_ID or FACEBOOK_APP_SECRET is not configured." }],
            isError: true,
          };
        }
        const data = await graphGet("/debug_token", {
          input_token: PAGE_TOKEN,
          access_token: `${APP_ID}|${APP_SECRET}`,
        });
        const details = data.data || {};
        return {
          content: [{
            type: "text",
            text:
              `Facebook token validation:\n` +
              `  Valid: ${Boolean(details.is_valid)}\n` +
              `  Type: ${details.type || "unknown"}\n` +
              `  App ID: ${details.app_id || "unknown"}\n` +
              `  Expires At: ${details.expires_at || "unknown"}\n` +
              `  Scopes: ${(details.scopes || []).join(", ") || "(none)"}`,
          }],
          isError: !details.is_valid,
        };
      }

      case "list_page_posts": {
        const limit = Math.min(Number(args.limit || 5), 25);
        const fields = "id,message,created_time,permalink_url,comments.summary(true).limit(0),reactions.summary(true).limit(0)";
        const data = await graphGet(`/${PAGE_ID}/posts`, { fields, limit });
        const posts = data.data || [];
        const lines = posts.map((post) => {
          const message = (post.message || "(no message)").replace(/\s+/g, " ").slice(0, 160);
          const comments = post.comments?.summary?.total_count ?? 0;
          const reactions = post.reactions?.summary?.total_count ?? 0;
          return (
            `  ${post.id} | ${post.created_time} | comments:${comments} reactions:${reactions}\n` +
            `    ${message}\n` +
            `    ${post.permalink_url || ""}`
          );
        });
        return {
          content: [{
            type: "text",
            text: posts.length
              ? `Recent Facebook Page Posts (${posts.length}):\n${lines.join("\n")}`
              : "No Facebook Page posts found or accessible with the configured token.",
          }],
        };
      }

      case "list_post_comments": {
        const limit = Math.min(Number(args.limit || 10), 50);
        const fields = "id,from,message,created_time,comment_count,like_count";
        const data = await graphGet(`/${args.post_id}/comments`, { fields, limit, order: "reverse_chronological" });
        const comments = data.data || [];
        const lines = comments.map((comment) => {
          const author = comment.from?.name || "unknown";
          const message = (comment.message || "").replace(/\s+/g, " ").slice(0, 220);
          return (
            `  ${comment.id} | ${comment.created_time} | ${author} | likes:${comment.like_count || 0} replies:${comment.comment_count || 0}\n` +
            `    ${message}`
          );
        });
        return {
          content: [{
            type: "text",
            text: comments.length
              ? `Recent Comments (${comments.length}) for ${args.post_id}:\n${lines.join("\n")}`
              : `No comments found or accessible for ${args.post_id}.`,
          }],
        };
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }

  } catch (err) {
    return {
      content: [{ type: "text", text: `Facebook MCP error: ${err.message}` }],
      isError: true,
    };
  }
});

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------

const transport = new StdioServerTransport();
await server.connect(transport);
