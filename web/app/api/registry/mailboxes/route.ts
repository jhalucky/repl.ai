import { NextRequest, NextResponse } from "next/server";
import { apiOrigin } from "@/lib/api";

export async function POST(request: NextRequest) {
  const body = await request.formData();
  const response = await fetch(`${apiOrigin()}/registry/mailboxes`, {
    method: "POST",
    body,
    redirect: "manual",
  });
  const location = response.headers.get("location") || "/register";
  const parsed = new URL(location, apiOrigin());
  const dest = request.nextUrl.clone();
  dest.pathname = parsed.pathname.startsWith("/") ? parsed.pathname : "/register";
  dest.search = parsed.search;
  if (!dest.pathname.startsWith("/")) dest.pathname = "/register";
  return NextResponse.redirect(dest, 303);
}
