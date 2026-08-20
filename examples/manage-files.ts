import {
  TOOL_RESOLUTION_EXTENSION_ID,
  ToolResolverRegistry,
  type ResolveToolRequest,
  type Tool,
} from "../src/index.js";

const manageFiles: Tool = {
  name: "manage_files",
  description: "Read, append, replace, or delete file contents",
  inputSchema: {
    type: "object",
    properties: {
      path: { type: "string" },
      action: {
        type: "string",
        enum: ["read", "append", "replace", "delete"],
      },
    },
    required: ["path", "action"],
    additionalProperties: false,
  },
  annotations: {
    readOnlyHint: false,
    destructiveHint: true,
    idempotentHint: false,
    openWorldHint: false,
  },
  _meta: {
    [TOOL_RESOLUTION_EXTENSION_ID]: { resolvable: true },
  },
};

const registry = new ToolResolverRegistry({
  tools: [manageFiles],
  resolvers: {
    manage_files: (arguments_) => {
      const action = arguments_.action;
      return {
        resultType: "complete",
        name: "manage_files",
        annotations: {
          readOnlyHint: action === "read",
          destructiveHint: action === "replace" || action === "delete",
          idempotentHint: action !== "append",
          openWorldHint: false,
        },
      };
    },
  },
});

const request: ResolveToolRequest = {
  jsonrpc: "2.0",
  id: 1,
  method: "tools/resolve",
  params: {
    name: "manage_files",
    arguments: { path: "/home/user/notes.txt", action: "read" },
    _meta: {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientCapabilities": {
        extensions: {
          [TOOL_RESOLUTION_EXTENSION_ID]: {},
        },
      },
    },
  },
};

const result = await registry.resolve(request);
console.log(JSON.stringify(result, null, 2));
