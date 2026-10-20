import { redirect } from "next/navigation";

export default function FlightsPage() {
  redirect("/records?type=flight");
}
