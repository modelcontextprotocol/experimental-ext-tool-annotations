import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { createGenerator, type Schema } from "ts-json-schema-generator";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const schemaPath = resolve(root, "schema/tool-resolution.schema.json");
const docsPath = resolve(root, "docs/generated/tool-resolution-types.md");

const generator = createGenerator({
  path: resolve(root, "src/spec.types.ts"),
  tsconfig: resolve(root, "tsconfig.json"),
  type: "*",
  additionalProperties: false,
  expose: "export",
  jsDoc: "extended",
  skipTypeCheck: false,
});

const generated = generator.createSchema("*") as Schema & {
  definitions?: Record<string, unknown>;
};
const schema = convertTo202012(generated);

schema.$id =
  "https://modelcontextprotocol.io/extensions/tool-resolution/schema.json";
schema.title = "MCP Tool Resolution Extension";
schema.description = "Wire types for io.modelcontextprotocol/tool-resolution.";

mkdirSync(dirname(schemaPath), { recursive: true });
writeFileSync(schemaPath, `${JSON.stringify(schema, null, 2)}\n`);

mkdirSync(dirname(docsPath), { recursive: true });
writeFileSync(docsPath, renderDocs(schema));

function convertTo202012(
  input: Schema & { definitions?: Record<string, unknown> },
): Record<string, unknown> & { $defs?: Record<string, unknown> } {
  const converted = JSON.parse(
    JSON.stringify(input).replaceAll("#/definitions/", "#/$defs/"),
  ) as Record<string, unknown> & {
    definitions?: Record<string, unknown>;
    $defs?: Record<string, unknown>;
  };
  converted.$schema = "https://json-schema.org/draft/2020-12/schema";
  if (converted.definitions) {
    converted.$defs = converted.definitions;
    delete converted.definitions;
  }
  return converted;
}

function renderDocs(schema: { $defs?: Record<string, unknown> }): string {
  const definitions = schema.$defs ?? {};
  const names = [
    "ToolResolutionToolMetadata",
    "ResolvedToolAnnotations",
    "ResolveToolRequestParams",
    "ResolveToolRequest",
    "ResolveToolResult",
    "ResolveToolResultResponse",
  ];

  const sections = names.map((name) => {
    const definition = definitions[name] as
      | {
          description?: string;
          properties?: Record<
            string,
            {
              description?: string;
              type?: string;
              $ref?: string;
            }
          >;
          required?: string[];
        }
      | undefined;
    if (!definition) {
      throw new Error(`Missing generated definition: ${name}`);
    }

    const required = new Set(definition.required ?? []);
    const rows = Object.entries(definition.properties ?? {}).map(
      ([field, property]) =>
        `| \`${field}\` | ${required.has(field) ? "yes" : "no"} | ${describeType(property)} | ${escapeCell(property.description ?? "")} |`,
    );

    return [
      `## ${name}`,
      "",
      definition.description ?? "",
      "",
      "| Field | Required | Type | Description |",
      "| :--- | :--- | :--- | :--- |",
      ...rows,
    ].join("\n");
  });

  return [
    "# Generated Tool Resolution Types",
    "",
    "> Generated from `src/spec.types.ts` by `npm run generate`. Do not edit.",
    "",
    ...sections.flatMap((section) => [section, ""]),
  ].join("\n");
}

function describeType(property: { type?: string; $ref?: string }): string {
  if (property.$ref) {
    return `\`${property.$ref.split("/").at(-1) ?? property.$ref}\``;
  }
  return property.type ? `\`${property.type}\`` : "composite";
}

function escapeCell(value: string): string {
  return value.replaceAll("|", "\\|").replaceAll("\n", " ");
}
