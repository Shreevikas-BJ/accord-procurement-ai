"use client";
import { useState } from "react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "./ui/dialog";
import { api } from "@/lib/api";
import type { Row } from "@/lib/types";
export function NewItem({
  sku,
  description,
  onCreated,
}: {
  sku: string;
  description: string;
  onCreated: (item: Row) => void;
}) {
  const [open, setOpen] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [form, setForm] = useState({
    sku,
    description,
    manufacturer_part_number: sku,
    category: "Electrical",
    uom: "EA",
  });
  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => setOpen(true)}
      >
        Create new internal item
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create an internal item</DialogTitle>
            <DialogDescription>
              Verify the specification before creating an item. Save the quote
              review to confirm its supplier mapping.
            </DialogDescription>
          </DialogHeader>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError("");
              try {
                const item = await api<Row>("/items", {
                  method: "POST",
                  body: JSON.stringify(form),
                });
                onCreated(item);
                setOpen(false);
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            {(Object.keys(form) as (keyof typeof form)[]).map((k) => (
              <label key={k}>
                {k.replaceAll("_", " ")}
                <Input
                  required
                  value={form[k]}
                  onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                />
              </label>
            ))}
            {error && (
              <p className="error-box" role="alert">
                {error}
              </p>
            )}
            <DialogFooter>
              <Button type="submit" disabled={busy}>
                Create item
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
