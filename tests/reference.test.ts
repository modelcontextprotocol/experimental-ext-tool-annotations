import assert from "node:assert/strict";
import test from "node:test";

import {
  INVALID_PARAMS,
  MISSING_REQUIRED_CLIENT_CAPABILITY,
  TOOL_RESOLUTION_EXTENSION_ID,
  ToolResolutionError,
  ToolResolverRegistry,
  resolveAnnotationsOrStatic,
  type ResolveToolRequest,
  type ResolveToolResult,
  type Tool,
} from "../src/index.js";

const tool: Tool = {
  name: "manage_files",
  inputSchema: {
    type: "object",
    properties: {
      action: { enum: ["read", "delete"] },
    },
    required: ["action"],
    additionalProperties: false,
  },
  annotations: {
    title: "Manage files",
    readOnlyHint: false,
    destructiveHint: true,
    idempotentHint: false,
    openWorldHint: false,
  },
  _meta: {
    [TOOL_RESOLUTION_EXTENSION_ID]: { resolvable: true },
  },
};

function request(
  arguments_: Record<string, never | string>,
): ResolveToolRequest {
  return {
    jsonrpc: "2.0",
    id: 1,
    method: "tools/resolve",
    params: {
      name: tool.name,
      arguments: arguments_,
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
}

test("resolves argument-specific annotations without returning a Tool", async () => {
  const registry = new ToolResolverRegistry({
    tools: [tool],
    resolvers: {
      manage_files: (arguments_) => ({
        resultType: "complete",
        name: "manage_files",
        annotations: {
          readOnlyHint: arguments_.action === "read",
          destructiveHint: arguments_.action === "delete",
          idempotentHint: true,
          openWorldHint: false,
        },
      }),
    },
  });

  const result = await registry.resolve(request({ action: "read" }));
  assert.deepEqual(result, {
    resultType: "complete",
    name: "manage_files",
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
  });
  assert.equal("inputSchema" in result, false);
});

test("validates arguments before invoking a resolver", async () => {
  let called = false;
  const registry = new ToolResolverRegistry({
    tools: [tool],
    resolvers: {
      manage_files: () => {
        called = true;
        throw new Error("must not run");
      },
    },
  });

  await assert.rejects(
    registry.resolve(request({ action: "append" })),
    (error: unknown) =>
      error instanceof ToolResolutionError && error.code === INVALID_PARAMS,
  );
  assert.equal(called, false);
});

test("requires capability support on the current request", async () => {
  const registry = new ToolResolverRegistry({
    tools: [tool],
    resolvers: {},
  });
  const missing = {
    ...request({ action: "read" }),
    params: {
      ...request({ action: "read" }).params,
      _meta: {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientCapabilities": {
          extensions: {
            "com.example/other": {},
          },
        },
      },
    },
  } as unknown as ResolveToolRequest;

  await assert.rejects(registry.resolve(missing), (error: unknown) => {
    assert.ok(error instanceof ToolResolutionError);
    assert.equal(error.code, MISSING_REQUIRED_CLIENT_CAPABILITY);
    assert.deepEqual(error.data, {
      requiredCapabilities: {
        extensions: {
          [TOOL_RESOLUTION_EXTENSION_ID]: {},
        },
      },
    });
    return true;
  });
});

test("rejects unsupported capability settings", async () => {
  const registry = new ToolResolverRegistry({
    tools: [tool],
    resolvers: {},
  });
  const unsupported = request({ action: "read" });
  const capabilities =
    unsupported.params._meta!["io.modelcontextprotocol/clientCapabilities"]!;
  const extensions = capabilities.extensions as unknown as Record<
    string,
    unknown
  >;
  extensions[TOOL_RESOLUTION_EXTENSION_ID] = {
    futureRequiredMode: true,
  };

  await assert.rejects(
    registry.resolve(unsupported),
    (error: unknown) =>
      error instanceof ToolResolutionError &&
      error.code === MISSING_REQUIRED_CLIENT_CAPABILITY,
  );
});

test("reports missing request metadata as a capability error", async () => {
  const registry = new ToolResolverRegistry({
    tools: [tool],
    resolvers: {},
  });
  const missing = {
    jsonrpc: "2.0",
    id: 1,
    method: "tools/resolve",
    params: {
      name: "manage_files",
      arguments: { action: "read" },
    },
  } as unknown as ResolveToolRequest;

  await assert.rejects(
    registry.resolve(missing),
    (error: unknown) =>
      error instanceof ToolResolutionError &&
      error.code === MISSING_REQUIRED_CLIENT_CAPABILITY,
  );
});

test("uses initialize-negotiated capabilities for a legacy request", async () => {
  const registry = new ToolResolverRegistry({
    tools: [tool],
    resolvers: {
      manage_files: () => ({
        resultType: "complete",
        name: "manage_files",
        annotations: {
          readOnlyHint: true,
          destructiveHint: false,
          idempotentHint: true,
          openWorldHint: false,
        },
      }),
    },
    legacyClientExtensions: {
      [TOOL_RESOLUTION_EXTENSION_ID]: {},
    },
  });
  const legacyRequest = request({ action: "read" });
  legacyRequest.params._meta = { progressToken: "legacy-progress" };

  const result = await registry.resolve(legacyRequest);
  assert.equal(result.annotations.readOnlyHint, true);
});

test("validates tool arguments against explicit draft-07 schemas", async () => {
  const draft07Tool: Tool = {
    ...tool,
    inputSchema: {
      $schema: "http://json-schema.org/draft-07/schema#",
      type: "object",
      properties: {
        action: { const: "read" },
      },
      required: ["action"],
      additionalProperties: false,
    },
  };
  const registry = new ToolResolverRegistry({
    tools: [draft07Tool],
    resolvers: {
      manage_files: () => ({
        resultType: "complete",
        name: "manage_files",
        annotations: {
          readOnlyHint: true,
          destructiveHint: false,
          idempotentHint: true,
          openWorldHint: false,
        },
      }),
    },
  });

  const result = await registry.resolve(request({ action: "read" }));
  assert.equal(result.resultType, "complete");
});

test("rejects resolved risk outside the static conservative bound", async () => {
  const closedWorldTool: Tool = {
    ...tool,
    annotations: {
      ...tool.annotations,
      openWorldHint: false,
    },
  };
  const registry = new ToolResolverRegistry({
    tools: [closedWorldTool],
    resolvers: {
      manage_files: () => ({
        resultType: "complete",
        name: "manage_files",
        annotations: {
          readOnlyHint: true,
          destructiveHint: false,
          idempotentHint: true,
          openWorldHint: true,
        },
      }),
    },
  });

  await assert.rejects(
    registry.resolve(request({ action: "read" })),
    /conservative tools\/list declaration/,
  );
});

test("rejects server metadata for an unnegotiated extension", async () => {
  const registry = new ToolResolverRegistry({
    tools: [tool],
    resolvers: {
      manage_files: () => ({
        resultType: "complete",
        name: "manage_files",
        annotations: {
          readOnlyHint: true,
          destructiveHint: false,
          idempotentHint: true,
          openWorldHint: false,
        },
        _meta: {
          "com.example/cost-estimate": { amount: 0 },
        },
      }),
    },
  });

  await assert.rejects(
    registry.resolve(request({ action: "read" })),
    /unnegotiated extension/,
  );
});

test("rejects result fields and annotation fields owned by tools/list", async () => {
  const registry = new ToolResolverRegistry({
    tools: [tool],
    resolvers: {
      manage_files: () =>
        ({
          resultType: "complete",
          name: "manage_files",
          inputSchema: { type: "object" },
          annotations: {
            title: "Spoofed title",
            readOnlyHint: true,
            destructiveHint: false,
            idempotentHint: true,
            openWorldHint: false,
          },
        }) as unknown as ResolveToolResult,
    },
  });

  await assert.rejects(
    registry.resolve(request({ action: "read" })),
    /forbidden field/,
  );
});

test("preserves valid core result metadata without extension negotiation", async () => {
  const registry = new ToolResolverRegistry({
    tools: [tool],
    resolvers: {
      manage_files: () => ({
        resultType: "complete",
        name: "manage_files",
        annotations: {
          readOnlyHint: true,
          destructiveHint: false,
          idempotentHint: true,
          openWorldHint: false,
        },
        _meta: {
          "io.modelcontextprotocol/serverInfo": {
            name: "example-server",
            version: "1.0.0",
          },
        },
      }),
    },
  });

  const result = await registry.resolve(request({ action: "read" }));
  assert.deepEqual(result._meta?.["io.modelcontextprotocol/serverInfo"], {
    name: "example-server",
    version: "1.0.0",
  });
});

test("rejects malformed optional core server metadata fields", async () => {
  const registry = new ToolResolverRegistry({
    tools: [tool],
    resolvers: {
      manage_files: () =>
        ({
          resultType: "complete",
          name: "manage_files",
          annotations: {
            readOnlyHint: true,
            destructiveHint: false,
            idempotentHint: true,
            openWorldHint: false,
          },
          _meta: {
            "io.modelcontextprotocol/serverInfo": {
              name: "example-server",
              version: "1.0.0",
              icons: [{ src: 42, theme: "solarized" }],
            },
          },
        }) as unknown as ResolveToolResult,
    },
  });

  await assert.rejects(
    registry.resolve(request({ action: "read" })),
    /serverInfo/,
  );
});

test("rejects non-JSON extension metadata before serialization", async () => {
  const registry = new ToolResolverRegistry({
    tools: [tool],
    resolvers: {
      manage_files: () =>
        ({
          resultType: "complete",
          name: "manage_files",
          annotations: {
            readOnlyHint: true,
            destructiveHint: false,
            idempotentHint: true,
            openWorldHint: false,
          },
          _meta: {
            [TOOL_RESOLUTION_EXTENSION_ID]: { estimate: 1n },
          },
        }) as unknown as ResolveToolResult,
    },
  });

  await assert.rejects(
    registry.resolve(request({ action: "read" })),
    /must be an object/,
  );
});

test("falls back to expanded static annotations on resolution failure", async () => {
  const selection = await resolveAnnotationsOrStatic({
    tool,
    arguments: { action: "delete" },
    requestMeta: request({ action: "delete" }).params._meta!,
    resolve: async () => {
      throw new ToolResolutionError(-32603, "temporarily unavailable");
    },
  });

  assert.equal(selection.source, "static");
  assert.deepEqual(selection.annotations, {
    title: "Manage files",
    readOnlyHint: false,
    destructiveHint: true,
    idempotentHint: false,
    openWorldHint: false,
  });
});

test("ignores unnegotiated result metadata while preserving annotations", async () => {
  const selection = await resolveAnnotationsOrStatic({
    tool,
    arguments: { action: "read" },
    requestMeta: request({ action: "read" }).params._meta!,
    resolve: async () => ({
      resultType: "complete",
      name: "manage_files",
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
      _meta: {
        "com.example/cost-estimate": { amount: 0 },
      },
    }),
  });

  assert.equal(selection.source, "resolved");
  assert.equal(selection.metadata, undefined);
  assert.equal(selection.annotations.readOnlyHint, true);
});

test("does not hide invalid arguments behind static fallback", async () => {
  await assert.rejects(
    resolveAnnotationsOrStatic({
      tool,
      arguments: { action: "append" },
      requestMeta: request({ action: "append" }).params._meta!,
      resolve: async () => {
        throw new ToolResolutionError(INVALID_PARAMS, "invalid arguments");
      },
    }),
    /invalid arguments/,
  );
});

test("surfaces transport-shaped invalid params errors", async () => {
  await assert.rejects(
    resolveAnnotationsOrStatic({
      tool,
      arguments: { action: "append" },
      requestMeta: request({ action: "append" }).params._meta!,
      resolve: async () => {
        throw { code: INVALID_PARAMS, message: "invalid arguments" };
      },
    }),
    (error: unknown) =>
      error instanceof ToolResolutionError && error.code === INVALID_PARAMS,
  );
});

test("uses unique JSON-RPC ids for concurrent resolutions", async () => {
  const ids: Array<string | number> = [];
  const resolve = async (request_: ResolveToolRequest) => {
    ids.push(request_.id);
    return {
      resultType: "complete" as const,
      name: "manage_files",
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    };
  };

  await Promise.all([
    resolveAnnotationsOrStatic({
      tool,
      arguments: { action: "read" },
      requestMeta: request({ action: "read" }).params._meta!,
      resolve,
    }),
    resolveAnnotationsOrStatic({
      tool,
      arguments: { action: "read" },
      requestMeta: request({ action: "read" }).params._meta!,
      resolve,
    }),
  ]);

  assert.equal(new Set(ids).size, 2);
});
