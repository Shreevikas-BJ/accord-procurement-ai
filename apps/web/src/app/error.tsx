"use client";
import { Button } from "@/components/ui/button";
export default function Error({ reset }: { reset: () => void }) {
  return (
    <div className="empty-state" role="alert">
      <h2>This view could not be displayed.</h2>
      <p>Your saved data is safe. Try loading the view again.</p>
      <Button onClick={reset}>Try again</Button>
    </div>
  );
}
