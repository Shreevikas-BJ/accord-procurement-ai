"use client";
import { Dashboard } from "./dashboard";
import { Catalog, DetailPage } from "./catalog";
import { Comparison } from "./comparison";
import { ReviewPage } from "./review";
import { Inbox, DocumentPage } from "./inbox";
import { SettingsPage } from "./settings";
import { Empty } from "./shared";
export function WorkspacePage({ path }: { path: string[] }) {
  const [section, id] = path;
  if (!section) return <Dashboard />;
  if (section === "rfqs" && id) return <Comparison id={id} />;
  if (section === "quotes" && id) return <ReviewPage id={id} />;
  if (section === "documents" && id) return <DocumentPage id={id} />;
  if (["suppliers", "items"].includes(section) && id)
    return <DetailPage kind={section} id={id} />;
  if (
    ["rfqs", "suppliers", "items", "purchase-history", "audit-events"].includes(
      section,
    )
  )
    return <Catalog kind={section} />;
  if (section === "inbox") return <Inbox />;
  if (section === "settings") return <SettingsPage />;
  return (
    <Empty
      title="Page not found"
      text="Use the workspace navigation to return to procurement."
    />
  );
}
