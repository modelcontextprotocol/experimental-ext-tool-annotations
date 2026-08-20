# Generated Tool Resolution Types

> Generated from `src/spec.types.ts` by `npm run generate`. Do not edit.

## ToolResolutionToolMetadata

Per-tool opt-in stored at Tool._meta["io.modelcontextprotocol/tool-resolution"].

| Field        | Required | Type      | Description |
| :----------- | :------- | :-------- | :---------- |
| `resolvable` | yes      | `boolean` |             |

## ResolvedToolAnnotations

Core ToolAnnotations fields whose behavior may be resolved per invocation.

| Field             | Required | Type      | Description                                                   |
| :---------------- | :------- | :-------- | :------------------------------------------------------------ |
| `readOnlyHint`    | yes      | `boolean` | True when this invocation does not modify its environment.    |
| `destructiveHint` | yes      | `boolean` | True when this invocation may perform destructive updates.    |
| `idempotentHint`  | yes      | `boolean` | True when repeating this invocation has no additional effect. |
| `openWorldHint`   | yes      | `boolean` | True when this invocation may interact with an open world.    |

## ResolveToolRequestParams

| Field       | Required | Type                        | Description                                                                                                                                                          |
| :---------- | :------- | :-------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`      | yes      | `string`                    | Tool name exactly as returned by tools/list.                                                                                                                         |
| `arguments` | yes      | `JsonObject`                | Complete arguments intended for the subsequent tools/call request.                                                                                                   |
| `_meta`     | no       | `ToolResolutionRequestMeta` | Modern MCP per-request protocol and capability negotiation metadata. Omitted only when using a legacy session whose capabilities were negotiated through initialize. |

## ResolveToolRequest

Extension-defined tools/resolve request.

| Field     | Required | Type                       | Description |
| :-------- | :------- | :------------------------- | :---------- |
| `jsonrpc` | yes      | `string`                   |             |
| `id`      | yes      | `string,number`            |             |
| `method`  | yes      | `string`                   |             |
| `params`  | yes      | `ResolveToolRequestParams` |             |

## ResolveToolResult

Argument-specific pre-execution metadata.

Tool identity and schemas remain authoritative from tools/list and therefore
cannot appear here.

| Field         | Required | Type                       | Description                                                            |
| :------------ | :------- | :------------------------- | :--------------------------------------------------------------------- |
| `resultType`  | yes      | `string`                   | Core result discriminator required by the current MCP protocol.        |
| `name`        | yes      | `string`                   | Tool name, used only to correlate the result with the request.         |
| `annotations` | yes      | `ResolvedToolAnnotations`  | Complete effective values for the four resolvable core behavior hints. |
| `_meta`       | no       | `ToolResolutionResultMeta` | Core result metadata plus metadata owned by negotiated extensions.     |

## ResolveToolResultResponse

| Field     | Required | Type                | Description |
| :-------- | :------- | :------------------ | :---------- |
| `jsonrpc` | yes      | `string`            |             |
| `id`      | yes      | `string,number`     |             |
| `result`  | yes      | `ResolveToolResult` |             |
