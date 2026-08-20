import {
  Ajv2020,
  type ErrorObject,
  type ValidateFunction,
} from "ajv/dist/2020.js";
import { Ajv as AjvDraft07 } from "ajv";

import type {
  JsonObject,
  ResolveToolRequest,
  ResolveToolResult,
  ResolvedToolAnnotations,
  Tool,
  ToolAnnotations,
  ToolResolutionRequestMeta,
} from "./spec.types.js";

export const TOOL_RESOLUTION_EXTENSION_ID =
  "io.modelcontextprotocol/tool-resolution" as const;
export const TOOL_RESOLUTION_METHOD = "tools/resolve" as const;
export const INVALID_PARAMS = -32602;
export const INTERNAL_ERROR = -32603;
export const METHOD_NOT_FOUND = -32601;
export const MISSING_REQUIRED_CLIENT_CAPABILITY = -32021;
const SERVER_INFO_META_KEY = "io.modelcontextprotocol/serverInfo";
const CLIENT_CAPABILITIES_META_KEY =
  "io.modelcontextprotocol/clientCapabilities";
const RESOLVE_RESULT_KEYS = new Set([
  "resultType",
  "name",
  "annotations",
  "_meta",
]);
const RESOLVED_ANNOTATION_KEYS = new Set([
  "readOnlyHint",
  "destructiveHint",
  "idempotentHint",
  "openWorldHint",
]);
let nextResolveRequestId = 0;

export class ToolResolutionError extends Error {
  constructor(
    public readonly code: number,
    message: string,
    public readonly data?: unknown,
  ) {
    super(message);
    this.name = "ToolResolutionError";
  }
}

export type ToolResolver = (
  arguments_: Readonly<JsonObject>,
) => Promise<ResolveToolResult> | ResolveToolResult;

export interface ToolResolverRegistryOptions {
  tools: readonly Tool[];
  resolvers: Readonly<Record<string, ToolResolver>>;
  /**
   * Extension capabilities negotiated by initialize for legacy MCP sessions.
   * Ignored whenever the current request carries per-request capabilities.
   */
  legacyClientExtensions?: Readonly<Record<string, unknown>>;
}

export interface EffectiveAnnotations extends ResolvedToolAnnotations {
  title?: string;
}

export interface ResolutionSelection {
  annotations: EffectiveAnnotations;
  metadata?: ResolveToolResult["_meta"];
  source: "resolved" | "static";
}

export type ResolveRequest = (
  request: ResolveToolRequest,
) => Promise<ResolveToolResult>;

/**
 * Minimal server-side reference implementation.
 *
 * Resolver callbacks are metadata-only by contract. Keep them separate from
 * execution handlers so resolution cannot accidentally invoke a tool.
 */
export class ToolResolverRegistry {
  readonly #tools: ReadonlyMap<string, Tool>;
  readonly #resolvers: Readonly<Record<string, ToolResolver>>;
  readonly #legacyClientExtensions:
    Readonly<Record<string, unknown>> | undefined;
  readonly #validators = new Map<string, ValidateFunction>();
  readonly #ajv2020 = new Ajv2020({ allErrors: true, strict: false });
  readonly #ajvDraft07 = new AjvDraft07({ allErrors: true, strict: false });

  constructor(options: ToolResolverRegistryOptions) {
    this.#tools = new Map(options.tools.map((tool) => [tool.name, tool]));
    this.#resolvers = options.resolvers;
    this.#legacyClientExtensions = options.legacyClientExtensions;
  }

  async resolve(request: ResolveToolRequest): Promise<ResolveToolResult> {
    if (request.method !== TOOL_RESOLUTION_METHOD) {
      throw new ToolResolutionError(
        METHOD_NOT_FOUND,
        `Unsupported method: ${request.method}`,
      );
    }

    const params = (
      request as ResolveToolRequest & {
        params?: ResolveToolRequest["params"];
      }
    ).params;
    if (!params || typeof params !== "object") {
      throw new ToolResolutionError(INVALID_PARAMS, "params are required");
    }
    const negotiatedExtensions = assertClientCapability(
      params._meta,
      this.#legacyClientExtensions,
    );

    const { name, arguments: arguments_ } = params;
    if (
      typeof name !== "string" ||
      typeof arguments_ !== "object" ||
      arguments_ === null ||
      Array.isArray(arguments_)
    ) {
      throw new ToolResolutionError(
        INVALID_PARAMS,
        "name and object arguments are required",
      );
    }
    const tool = this.#tools.get(name);
    if (!tool) {
      throw new ToolResolutionError(INVALID_PARAMS, `Unknown tool: ${name}`);
    }
    if (!isResolvableTool(tool)) {
      throw new ToolResolutionError(
        INVALID_PARAMS,
        `Tool is not resolvable: ${name}`,
      );
    }

    const resolver = this.#resolvers[name];
    if (!resolver) {
      throw new ToolResolutionError(
        INTERNAL_ERROR,
        `No resolver registered for tool: ${name}`,
      );
    }

    const validate = this.#validatorFor(tool);
    if (!validate(arguments_)) {
      throw new ToolResolutionError(
        INVALID_PARAMS,
        `Arguments do not match the input schema for ${name}`,
        formatValidationErrors(validate.errors),
      );
    }

    let result: ResolveToolResult;
    try {
      result = await resolver(arguments_);
    } catch (error) {
      if (error instanceof ToolResolutionError) {
        throw error;
      }
      throw new ToolResolutionError(
        INTERNAL_ERROR,
        `Failed to resolve tool: ${name}`,
        error instanceof Error ? error.message : String(error),
      );
    }

    const resolved = normalizeResolveToolResult(result);
    if (resolved.name !== name) {
      throw new ToolResolutionError(
        INTERNAL_ERROR,
        `Resolver returned metadata for ${resolved.name}, expected ${name}`,
      );
    }
    assertConservativeBound(tool.annotations, resolved.annotations);
    assertMetadataWasNegotiated(resolved._meta, negotiatedExtensions);

    return resolved;
  }

  #validatorFor(tool: Tool): ValidateFunction {
    const existing = this.#validators.get(tool.name);
    if (existing) {
      return existing;
    }
    const dialect = tool.inputSchema.$schema;
    let validator: ValidateFunction;
    try {
      validator = isDraft07Dialect(dialect)
        ? this.#ajvDraft07.compile(tool.inputSchema)
        : this.#ajv2020.compile(tool.inputSchema);
    } catch (error) {
      throw new ToolResolutionError(
        INTERNAL_ERROR,
        `Could not compile input schema for ${tool.name}`,
        error instanceof Error ? error.message : String(error),
      );
    }
    this.#validators.set(tool.name, validator);
    return validator;
  }
}

export function isResolvableTool(tool: Tool): boolean {
  const metadata = tool._meta?.[TOOL_RESOLUTION_EXTENSION_ID];
  return (
    typeof metadata === "object" &&
    metadata !== null &&
    "resolvable" in metadata &&
    metadata.resolvable === true
  );
}

export function expandStaticAnnotations(
  annotations: ToolAnnotations | undefined,
): EffectiveAnnotations {
  const expanded: EffectiveAnnotations = {
    readOnlyHint: annotations?.readOnlyHint ?? false,
    destructiveHint: annotations?.destructiveHint ?? true,
    idempotentHint: annotations?.idempotentHint ?? false,
    openWorldHint: annotations?.openWorldHint ?? true,
  };
  if (annotations?.title !== undefined) {
    expanded.title = annotations.title;
  }
  return expanded;
}

/**
 * Client-side fallback helper.
 *
 * Invalid arguments are surfaced rather than retried or executed. Other
 * resolution failures fall back to the conservative tools/list annotations.
 */
export async function resolveAnnotationsOrStatic(options: {
  tool: Tool;
  arguments: JsonObject;
  requestMeta: ToolResolutionRequestMeta;
  resolve: ResolveRequest;
}): Promise<ResolutionSelection> {
  const fallback = (): ResolutionSelection => ({
    annotations: expandStaticAnnotations(options.tool.annotations),
    source: "static",
  });

  if (!isResolvableTool(options.tool)) {
    return fallback();
  }

  try {
    const result = await options.resolve({
      jsonrpc: "2.0",
      id: `tool-resolution-${++nextResolveRequestId}`,
      method: TOOL_RESOLUTION_METHOD,
      params: {
        name: options.tool.name,
        arguments: options.arguments,
        _meta: options.requestMeta,
      },
    });

    const resolved = normalizeResolveToolResult(result);
    if (resolved.name !== options.tool.name) {
      return fallback();
    }
    assertConservativeBound(options.tool.annotations, resolved.annotations);

    const annotations: EffectiveAnnotations = { ...resolved.annotations };
    if (options.tool.annotations?.title !== undefined) {
      annotations.title = options.tool.annotations.title;
    }

    const selection: ResolutionSelection = {
      annotations,
      source: "resolved",
    };
    const metadata = filterNegotiatedMetadata(
      resolved._meta,
      options.requestMeta,
    );
    if (metadata !== undefined) {
      selection.metadata = metadata;
    }
    return selection;
  } catch (error) {
    if (getErrorCode(error) === INVALID_PARAMS) {
      if (error instanceof ToolResolutionError) {
        throw error;
      }
      throw new ToolResolutionError(
        INVALID_PARAMS,
        getErrorMessage(error, "invalid tool arguments"),
        isObject(error) ? error.data : undefined,
      );
    }
    return fallback();
  }
}

function assertClientCapability(
  meta: ToolResolutionRequestMeta | undefined,
  legacyClientExtensions: Readonly<Record<string, unknown>> | undefined,
): Record<string, unknown> {
  const hasPerRequestCapabilities =
    isObject(meta) && Object.hasOwn(meta, CLIENT_CAPABILITIES_META_KEY);
  const capabilities = meta?.[CLIENT_CAPABILITIES_META_KEY] as unknown;
  const perRequestExtensions = isObject(capabilities)
    ? capabilities.extensions
    : undefined;
  const extensions = hasPerRequestCapabilities
    ? perRequestExtensions
    : legacyClientExtensions;
  const extension = isObject(extensions)
    ? extensions[TOOL_RESOLUTION_EXTENSION_ID]
    : undefined;
  if (!isObject(extension) || Object.keys(extension).length > 0) {
    throw new ToolResolutionError(
      MISSING_REQUIRED_CLIENT_CAPABILITY,
      `Missing or unsupported client capability: ${TOOL_RESOLUTION_EXTENSION_ID}`,
      {
        requiredCapabilities: {
          extensions: {
            [TOOL_RESOLUTION_EXTENSION_ID]: {},
          },
        },
      },
    );
  }
  return extensions as Record<string, unknown>;
}

function normalizeResolveToolResult(
  result: ResolveToolResult,
): ResolveToolResult {
  if (!isObject(result)) {
    throw new ToolResolutionError(
      INTERNAL_ERROR,
      "Resolved result must be an object",
    );
  }
  for (const key of Object.keys(result)) {
    if (!RESOLVE_RESULT_KEYS.has(key)) {
      throw new ToolResolutionError(
        INTERNAL_ERROR,
        `Resolved result contains forbidden field: ${key}`,
      );
    }
  }
  if (result.resultType !== "complete") {
    throw new ToolResolutionError(
      INTERNAL_ERROR,
      'Resolved resultType must be "complete"',
    );
  }
  if (typeof result.name !== "string") {
    throw new ToolResolutionError(
      INTERNAL_ERROR,
      "Resolved result name must be a string",
    );
  }
  const annotations = normalizeResolvedAnnotations(result.annotations);
  const normalized: ResolveToolResult = {
    resultType: "complete",
    name: result.name,
    annotations,
  };
  if (result._meta !== undefined) {
    if (!isObject(result._meta)) {
      throw new ToolResolutionError(
        INTERNAL_ERROR,
        "Resolved result _meta must be an object",
      );
    }
    normalized._meta = result._meta;
  }
  return normalized;
}

function normalizeResolvedAnnotations(
  annotations: ResolvedToolAnnotations,
): ResolvedToolAnnotations {
  if (!isObject(annotations)) {
    throw new ToolResolutionError(
      INTERNAL_ERROR,
      "Resolved annotations must be an object",
    );
  }
  for (const key of Object.keys(annotations)) {
    if (!RESOLVED_ANNOTATION_KEYS.has(key)) {
      throw new ToolResolutionError(
        INTERNAL_ERROR,
        `Resolved annotations contain forbidden field: ${key}`,
      );
    }
  }
  for (const key of [
    "readOnlyHint",
    "destructiveHint",
    "idempotentHint",
    "openWorldHint",
  ] as const) {
    if (typeof annotations[key] !== "boolean") {
      throw new ToolResolutionError(
        INTERNAL_ERROR,
        `Resolved annotation ${key} must be a boolean`,
      );
    }
  }
  return {
    readOnlyHint: annotations.readOnlyHint,
    destructiveHint: annotations.destructiveHint,
    idempotentHint: annotations.idempotentHint,
    openWorldHint: annotations.openWorldHint,
  };
}

function assertConservativeBound(
  staticAnnotations: ToolAnnotations | undefined,
  resolved: ResolvedToolAnnotations,
): void {
  const listed = expandStaticAnnotations(staticAnnotations);
  const violations: string[] = [];

  if (listed.readOnlyHint && !resolved.readOnlyHint) {
    violations.push("readOnlyHint");
  }
  if (
    !listed.readOnlyHint &&
    !listed.destructiveHint &&
    !resolved.readOnlyHint &&
    resolved.destructiveHint
  ) {
    violations.push("destructiveHint");
  }
  if (
    !resolved.readOnlyHint &&
    listed.idempotentHint &&
    !resolved.idempotentHint
  ) {
    violations.push("idempotentHint");
  }
  if (!listed.openWorldHint && resolved.openWorldHint) {
    violations.push("openWorldHint");
  }

  if (violations.length > 0) {
    throw new ToolResolutionError(
      INTERNAL_ERROR,
      `Resolved annotations exceed the conservative tools/list declaration: ${violations.join(", ")}`,
    );
  }
}

function formatValidationErrors(
  errors: ErrorObject[] | null | undefined,
): JsonObject {
  return {
    errors: (errors ?? []).map((error) => ({
      instancePath: error.instancePath,
      keyword: error.keyword,
      message: error.message ?? "validation failed",
    })),
  };
}

function assertMetadataWasNegotiated(
  metadata: ResolveToolResult["_meta"],
  negotiatedExtensions: Record<string, unknown>,
): void {
  if (metadata === undefined) {
    return;
  }
  for (const [extensionId, value] of Object.entries(metadata)) {
    if (extensionId === SERVER_INFO_META_KEY) {
      assertServerInfo(value);
      continue;
    }
    if (!Object.hasOwn(negotiatedExtensions, extensionId)) {
      throw new ToolResolutionError(
        INTERNAL_ERROR,
        `Resolver returned metadata for an unnegotiated extension: ${extensionId}`,
      );
    }
    if (!isJsonObject(value)) {
      throw new ToolResolutionError(
        INTERNAL_ERROR,
        `Resolved metadata for ${extensionId} must be an object`,
      );
    }
  }
}

function filterNegotiatedMetadata(
  metadata: ResolveToolResult["_meta"],
  requestMeta: ToolResolutionRequestMeta,
): ResolveToolResult["_meta"] {
  if (metadata === undefined) {
    return undefined;
  }

  const capabilities = requestMeta[CLIENT_CAPABILITIES_META_KEY] as unknown;
  const extensions = isObject(capabilities)
    ? capabilities.extensions
    : undefined;
  if (!isObject(extensions)) {
    return undefined;
  }

  const filtered: NonNullable<ResolveToolResult["_meta"]> = {};
  for (const [extensionId, value] of Object.entries(metadata)) {
    if (extensionId === SERVER_INFO_META_KEY) {
      assertServerInfo(value);
      filtered[extensionId] = value;
      continue;
    }
    if (!Object.hasOwn(extensions, extensionId)) {
      continue;
    }
    if (!isJsonObject(value)) {
      throw new ToolResolutionError(
        INTERNAL_ERROR,
        `Resolved metadata for ${extensionId} must be an object`,
      );
    }
    filtered[extensionId] = value;
  }
  return Object.keys(filtered).length > 0 ? filtered : undefined;
}

function assertServerInfo(value: unknown): asserts value is JsonObject {
  if (
    !isJsonObject(value) ||
    typeof value.name !== "string" ||
    typeof value.version !== "string" ||
    !isOptionalString(value.title) ||
    !isOptionalString(value.description) ||
    !isOptionalUri(value.websiteUrl) ||
    !isValidIcons(value.icons)
  ) {
    throw new ToolResolutionError(
      INTERNAL_ERROR,
      `Resolved ${SERVER_INFO_META_KEY} must contain string name and version`,
    );
  }
}

function isDraft07Dialect(dialect: unknown): boolean {
  return (
    dialect === "http://json-schema.org/draft-07/schema#" ||
    dialect === "https://json-schema.org/draft-07/schema" ||
    dialect === "https://json-schema.org/draft-07/schema#"
  );
}

function getErrorCode(error: unknown): unknown {
  return isObject(error) ? error.code : undefined;
}

function getErrorMessage(error: unknown, fallback: string): string {
  return isObject(error) && typeof error.message === "string"
    ? error.message
    : fallback;
}

function isOptionalString(value: unknown): boolean {
  return value === undefined || typeof value === "string";
}

function isOptionalUri(value: unknown): boolean {
  return (
    value === undefined || (typeof value === "string" && URL.canParse(value))
  );
}

function isValidIcons(value: unknown): boolean {
  if (value === undefined) {
    return true;
  }
  if (!Array.isArray(value)) {
    return false;
  }
  return value.every(
    (icon) =>
      isJsonObject(icon) &&
      typeof icon.src === "string" &&
      URL.canParse(icon.src) &&
      isOptionalString(icon.mimeType) &&
      (icon.sizes === undefined ||
        (Array.isArray(icon.sizes) &&
          icon.sizes.every((size) => typeof size === "string"))) &&
      (icon.theme === undefined ||
        icon.theme === "light" ||
        icon.theme === "dark"),
  );
}

function isJsonObject(value: unknown): value is JsonObject {
  return isJsonValue(value, new Set()) && !Array.isArray(value);
}

function isJsonValue(value: unknown, ancestors: Set<object>): boolean {
  if (
    value === null ||
    typeof value === "string" ||
    typeof value === "boolean"
  ) {
    return true;
  }
  if (typeof value === "number") {
    return Number.isFinite(value);
  }
  if (typeof value !== "object") {
    return false;
  }
  const prototype = Object.getPrototypeOf(value);
  if (
    !Array.isArray(value) &&
    prototype !== Object.prototype &&
    prototype !== null
  ) {
    return false;
  }
  if (ancestors.has(value)) {
    return false;
  }
  ancestors.add(value);
  const valid = Array.isArray(value)
    ? value.every((item) => isJsonValue(item, ancestors))
    : Reflect.ownKeys(value).every(
        (key) =>
          typeof key === "string" &&
          isJsonValue((value as Record<string, unknown>)[key], ancestors),
      );
  ancestors.delete(value);
  return valid;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
