import { redirect } from "next/navigation";

export default function TransportsPage() {
  redirect("/records?type=other");
}
