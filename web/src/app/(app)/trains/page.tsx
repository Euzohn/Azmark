import { redirect } from "next/navigation";

export default function TrainsPage() {
  redirect("/records?type=train");
}
