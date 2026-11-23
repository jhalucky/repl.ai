import { redirect } from "next/navigation";

export default function FounderPage() {
  redirect("/register?plan=founder");
}
