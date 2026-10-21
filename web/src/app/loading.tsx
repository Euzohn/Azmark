import { AzmarkLoader } from "@/components/azmark-loader";

export default function Loading() {
  return (
    <div className="flex min-h-dvh items-center justify-center bg-background">
      <AzmarkLoader className="h-24 w-auto text-foreground" />
    </div>
  );
}
