import Form from "@rjsf/core";
import validator from "@rjsf/validator-ajv8";
import type { RJSFSchema, RegistryWidgetsType, WidgetProps } from "@rjsf/utils";

interface SchemaFormProps {
  schema: RJSFSchema;
  formData: Record<string, unknown>;
  onChange: (data: Record<string, unknown>) => void;
  /** Flow-level connector aliases for connector-named fields. */
  connectorAliases?: string[];
}

/** True when a schema property name refers to a connector alias. */
export function isConnectorFieldName(name: string): boolean {
  const n = name.toLowerCase();
  return n === "connector" || n === "connector_id" || n.endsWith("_connector");
}

/** Dropdown of flow connector aliases. */
function ConnectorAliasWidget({
  id,
  value,
  onChange,
  options,
  disabled,
  readonly,
}: WidgetProps) {
  const aliases = (options.enumOptions ?? []).map((o) => String(o.value));
  return (
    <select
      id={id}
      className="w-full"
      value={value ?? ""}
      disabled={disabled || readonly}
      onChange={(e) => onChange(e.target.value || undefined)}
      style={{
        background: "var(--bg)",
        border: "1px solid var(--line-strong)",
        borderRadius: "6px",
        color: "var(--ink)",
        padding: "0.5rem 0.65rem",
        width: "100%",
      }}
    >
      <option value="">Select connector…</option>
      {aliases.map((a) => (
        <option key={a} value={a}>
          {a}
        </option>
      ))}
    </select>
  );
}

/** Catalog-driven RJSF form with connector alias dropdowns where applicable. */
export default function SchemaForm({
  schema,
  formData,
  onChange,
  connectorAliases = [],
}: SchemaFormProps) {
  const widgets: RegistryWidgetsType = {
    ConnectorAliasWidget,
  };

  const uiSchema: Record<string, unknown> = {};
  const props = (schema.properties ?? {}) as Record<string, RJSFSchema>;
  for (const key of Object.keys(props)) {
    if (isConnectorFieldName(key) && connectorAliases.length > 0) {
      uiSchema[key] = {
        "ui:widget": "ConnectorAliasWidget",
        "ui:options": {
          enumOptions: connectorAliases.map((a) => ({ value: a, label: a })),
        },
      };
    }
  }

  return (
    <Form
      schema={schema}
      uiSchema={uiSchema}
      formData={formData}
      validator={validator}
      widgets={widgets}
      liveValidate={false}
      onChange={(e) => onChange((e.formData as Record<string, unknown>) ?? {})}
      children={<></>}
    />
  );
}
