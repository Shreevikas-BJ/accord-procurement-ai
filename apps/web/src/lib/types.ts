export type Row = { id: string; [key: string]: unknown };
export interface User {
  id: string;
  name: string;
  email: string;
  role: "Admin" | "Buyer" | "Viewer";
  organization: string;
  organization_id: string;
}
export interface Evidence {
  evidence_strength?: "strong" | "weak" | "unsupported";
  source_status?: "PRESENT" | "NOT_FOUND" | "AMBIGUOUS" | "EXTRACTION_FAILED";
  sheet?: string | null;
  row?: number | null;
  cell?: string | null;
  evidence_type?: "text" | "ocr" | "visual" | "missing";
  page?: number;
  source_text: string;
  confidence: string | number;
  document_id?: string;
}
export interface Finding {
  code: string;
  message: string;
  severity: string;
}
export interface Line {
  id: string;
  item_id: string | null;
  supplier_sku: string | null;
  manufacturer_part_number: string | null;
  description: string | null;
  quantity: string | null;
  uom: string | null;
  unit_price: string | null;
  moq: string | null;
  lead_time_days: number | null;
  lead_time_min: number | null;
  delivery_date: string | null;
  stated_line_total: string | null;
  confidence: string;
  source_references: Record<string, Evidence>;
  price_tiers: {
    minimum: string;
    maximum: string | null;
    unit_price: string;
  }[];
  line_total?: string | null;
  sku?: string;
  match_method?: string;
  history?: {
    last_price: string | null;
    last_date: string | null;
    average_3m: string | null;
    average_6m: string | null;
    change: string | null;
    sample_count: number;
  };
  candidates?: {
    id: string;
    sku: string;
    description: string;
    confidence: number;
  }[];
}
export interface Quote {
  id: string;
  document_id: string;
  rfq_id: string | null;
  supplier_id: string | null;
  supplier_name: string | null;
  supplier_email: string | null;
  quote_number: string | null;
  rfq_number: string | null;
  quote_date: string | null;
  expiration_date: string | null;
  currency: string | null;
  payment_terms: string | null;
  shipping_terms: string | null;
  shipping_cost: string | null;
  tax: string | null;
  stated_subtotal: string | null;
  stated_total: string | null;
  notes: string | null;
  confidence: string;
  source_references: Record<string, Evidence>;
  review_status: string;
  version: number;
  subtotal: string | null;
  total: string | null;
  line_items: Line[];
  lines: Line[];
  eligible: boolean;
  score: string | null;
  factors: Record<string, string>;
  alerts: Finding[];
  lowest_cost: boolean;
  fastest: boolean;
  lead_time_days: number | null;
  delivery_date: string | null;
  historical_orders: number;
  extraction_provider?: string;
  extraction_diagnostics?: {
    fallback?: boolean;
    model?: string;
    confidence_band?: string;
    needs_review?: boolean;
    findings?: { code: string; field: string; message: string }[];
  };
  document: {
    id: string;
    filename: string;
    raw_text: string;
    status: string;
    error: string | null;
  };
}
export interface Comparison {
  rfq: {
    id: string;
    number: string;
    title: string;
    description: string;
    required_delivery: string;
    supplier_count: number;
    currency: string;
    status: string;
    revision: number;
  };
  requirements: {
    id: string;
    item_id: string;
    sku: string;
    description: string;
    quantity: string;
    uom: string;
  }[];
  quotes: Quote[];
  weights: Record<string, number>;
  recommended_quote_id: string | null;
  explanation: string;
  potential_savings: string;
  savings_basis: string;
  as_of: string;
}
export interface Recommendation {
  id: string;
  quote_id: string;
  explanation: string;
  status: string;
  revision: number;
}
export interface Draft {
  id: string;
  quote_id: string;
  subject: string;
  body: string;
  status: string;
}
export interface ListData {
  items: Row[];
  total: number;
  page: number;
  limit: number;
}
export interface Dashboard {
  metrics: {
    open_rfqs: number;
    quotes_received: number;
    needs_review: number;
    awaiting_response: number;
    potential_savings: string;
    processing_seconds: number | null;
    currency: string;
  };
  rfqs: (Comparison["rfq"] & {
    response_count: number;
    potential_savings: string;
  })[];
  alerts: (Finding & { supplier_name: string; quote_id: string })[];
  activity: Row[];
}
