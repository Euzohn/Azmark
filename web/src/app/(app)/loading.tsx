import { AzmarkLoader } from "@/components/azmark-loader";

export default function Loading() {
  return (
    <div className="flex min-h-[70vh] items-center justify-center">
      <AzmarkLoader className="h-20 w-auto text-foreground" />
    </div>
  );
}
