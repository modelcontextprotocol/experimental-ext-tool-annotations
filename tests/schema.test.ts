import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { Ajv2020 } from "ajv/dist/2020.js";

const schemaUrl = new URL(
  "../schema/tool-resolution.schema.json",
  import.meta.url,
);
const examples = [
  ["ResolveToolRequest", "resolve-request.json"],
  ["ResolveToolResultResponse", "resolve-response.json"],
  ["ResolvableTool", "resolvable-tool.json"],
] as const;

test("wire examples conform to the generated schema", async () => {
  const schema = JSON.parse(await readFile(schemaUrl, "utf8")) as {
    $id: string;
  };
  const ajv = new Ajv2020({ strict: false });
  ajv.addSchema(schema);

  for (const [definition, file] of examples) {
    const validate = ajv.getSchema(`${schema.$id}#/$defs/${definition}`);
    assert.ok(validate, `missing schema definition ${definition}`);
    const value = JSON.parse(
      await readFile(
        new URL(`../examples/wire/${file}`, import.meta.url),
        "utf8",
      ),
    );
    assert.equal(
      validate(value),
      true,
      `${file}: ${ajv.errorsText(validate.errors)}`,
    );
  }
});
