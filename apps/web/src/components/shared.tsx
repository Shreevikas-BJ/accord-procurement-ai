"use client";
import {
  AlertCircle,
  ArrowUpRight,
  CheckCircle2,
  FileSearch,
} from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
export function PageHeader({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      <div className="heading-actions">{children}</div>
    </div>
  );
}
export function Status({ value }: { value: string }) {
  const good = [
    "Reviewed",
    "Matched",
    "Approved",
    "Active",
    "Complete",
  ].includes(value);
  return (
    <Badge
      variant="outline"
      className={`status ${good ? "good" : value.includes("Review") || value === "Stale" ? "warning" : ""}`}
    >
      <span aria-hidden="true">●</span>
      <span className="status-text">{value}</span>
    </Badge>
  );
}
export function Loading() {
  return (
    <div className="loading-state" aria-label="Loading">
      <Skeleton className="h-9 w-72" />
      <Skeleton className="h-5 w-96" />
      <div className="metrics-grid">
        {[1, 2, 3, 4].map((x) => (
          <Skeleton key={x} className="h-28" />
        ))}
      </div>
      <Skeleton className="h-80 w-full" />
    </div>
  );
}
export function ErrorState({
  error,
  retry,
}: {
  error: string;
  retry: () => void;
}) {
  return (
    <div className="empty-state" role="alert">
      <AlertCircle />
      <h2>We couldn’t load this view</h2>
      <p>{error}</p>
      <Button onClick={retry}>Try again</Button>
    </div>
  );
}
export function Empty({
  title = "Nothing here yet",
  text = "Upload a supplier quotation to get started.",
}: {
  title?: string;
  text?: string;
}) {
  return (
    <div className="empty-state">
      <FileSearch />
      <h2>{title}</h2>
      <p>{text}</p>
    </div>
  );
}
export function Notice({
  text,
  onClose,
}: {
  text: string;
  onClose: () => void;
}) {
  return (
    <div className="toast" role="status">
      <CheckCircle2 size={18} />
      {text}
      <button onClick={onClose} aria-label="Dismiss notification">
        ×
      </button>
    </div>
  );
}
export function SectionLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link className="section-link" href={href}>
      {children}
      <ArrowUpRight size={14} />
    </Link>
  );
}
