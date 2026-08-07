import Form from "@rjsf/core";
import validator from "@rjsf/validator-ajv8";
import type { RJSFSchema } from "@rjsf/utils";

interface SchemaFormProps {
  schema: RJSFSchema;
  formData: Record<string, unknown>;
  onChange: (data: Record<string, unknown>) => void;
}

/** Lightweight RJSF wrapper for catalog-driven config editors. */
export default function SchemaForm({ schema, formData, onChange }: SchemaFormProps) {
  return (
    <Form
      schema={schema}
      formData={formData}
      validator={validator}
      liveValidate={false}
      onChange={(e) => onChange((e.formData as Record<string, unknown>) ?? {})}
      children={<></>}
    />
  );
}
