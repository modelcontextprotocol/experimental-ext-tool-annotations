/**
 * Wire types for the io.modelcontextprotocol/tool-resolution extension.
 *
 * This file is the source of truth for generated JSON Schema and type docs.
 */

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonObject | JsonValue[];

export interface JsonObject {
  [key: string]: JsonValue;
}

/** Core ToolAnnotations fields whose behavior may be resolved per invocation. */
export interface ResolvedToolAnnotations {
  /** True when this invocation does not modify its environment. */
  readOnlyHint: boolean;
  /** True when this invocation may perform destructive updates. */
  destructiveHint: boolean;
  /** True when repeating this invocation has no additional effect. */
  idempotentHint: boolean;
  /** True when this invocation may interact with an open world. */
  openWorldHint: boolean;
}

/** Core ToolAnnotations, included here to type the static tools/list fallback. */
export interface ToolAnnotations {
  /** Human-readable tool title. This field is not resolvable. */
  title?: string;
  readOnlyHint?: boolean;
  destructiveHint?: boolean;
  idempotentHint?: boolean;
  openWorldHint?: boolean;
  /** Namespaced fields owned by negotiated ToolAnnotations extensions. */
  [key: string]: unknown;
}

export interface Icon {
  src: string;
  mimeType?: string;
  sizes?: string[];
  theme?: "light" | "dark";
}

/** Minimal core Tool shape used by the reference implementation. */
export interface Tool {
  name: string;
  title?: string;
  description?: string;
  inputSchema: {
    type: "object";
    [key: string]: unknown;
  };
  outputSchema?: {
    [key: string]: unknown;
  };
  annotations?: ToolAnnotations;
  icons?: Icon[];
  _meta?: {
    [key: string]: unknown;
  };
}

/** Per-tool opt-in stored at Tool._meta["io.modelcontextprotocol/tool-resolution"]. */
export interface ToolResolutionToolMetadata {
  resolvable: true;
}

/** A tool from tools/list that opts in to argument-specific resolution. */
export interface ResolvableTool extends Tool {
  _meta: {
    "io.modelcontextprotocol/tool-resolution": ToolResolutionToolMetadata;
    [key: string]: unknown;
  };
}

/** The extension currently defines no capability settings. */
export type ToolResolutionCapability = Record<string, never>;

export interface ToolResolutionExtensions {
  "io.modelcontextprotocol/tool-resolution": ToolResolutionCapability;
  [key: string]: JsonObject;
}

export interface ToolResolutionClientCapabilities {
  extensions: ToolResolutionExtensions;
  [key: string]: JsonValue;
}

export interface ToolResolutionRequestMeta {
  progressToken?: string | number;
  "io.modelcontextprotocol/protocolVersion"?: string;
  "io.modelcontextprotocol/clientCapabilities"?: ToolResolutionClientCapabilities;
  [key: string]: unknown;
}

export interface ResolveToolRequestParams {
  /** Tool name exactly as returned by tools/list. */
  name: string;
  /** Complete arguments intended for the subsequent tools/call request. */
  arguments: JsonObject;
  /**
   * Modern MCP per-request protocol and capability negotiation metadata.
   * Omitted only when using a legacy session whose capabilities were negotiated
   * through initialize.
   */
  _meta?: ToolResolutionRequestMeta;
}

/** Extension-defined tools/resolve request. */
export interface ResolveToolRequest {
  jsonrpc: "2.0";
  id: string | number;
  method: "tools/resolve";
  params: ResolveToolRequestParams;
}

/**
 * Argument-specific pre-execution metadata.
 *
 * Tool identity and schemas remain authoritative from tools/list and therefore
 * cannot appear here.
 */
export interface ResolveToolResult {
  /** Core result discriminator required by the current MCP protocol. */
  resultType: "complete";
  /** Tool name, used only to correlate the result with the request. */
  name: string;
  /** Complete effective values for the four resolvable core behavior hints. */
  annotations: ResolvedToolAnnotations;
  /** Core result metadata plus metadata owned by negotiated extensions. */
  _meta?: ToolResolutionResultMeta;
}

export interface ToolResolutionResultMeta {
  [key: string]: JsonObject;
}

export interface ResolveToolResultResponse {
  jsonrpc: "2.0";
  id: string | number;
  result: ResolveToolResult;
}

export interface ToolResolutionServerCapabilities {
  extensions: ToolResolutionExtensions;
  [key: string]: JsonValue;
}
