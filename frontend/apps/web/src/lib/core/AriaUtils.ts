// ARIA accessibility props type definition
export type AriaProps = {
  "aria-label"?: string;
  "aria-labelledby"?: string;
  "aria-describedby"?: string;
  "aria-expanded"?: boolean;
  "aria-controls"?: string;
  "aria-hidden"?: boolean;
  "aria-disabled"?: boolean;
  "aria-checked"?: boolean;
  "aria-selected"?: boolean;
  "aria-invalid"?: boolean;
  "aria-required"?: boolean;
  "aria-live"?: "polite" | "assertive" | "off";
  "aria-atomic"?: boolean;
  "aria-busy"?: boolean;
  role?: string;
  [key: string]: any;
};