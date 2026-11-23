import { NextRequest, NextResponse } from "next/server";
import { apiOrigin } from "@/lib/api";

export async function POST(request: NextRequest) {
  const body = await request.formData();
  const response = await fetch(`${apiOrigin()}/registry`, {
    method: "POST",
    body,
    redirect: "manual",
  });
  const location = response.headers.get("location") || "/register";
  const parsed = new URL(location, apiOrigin());
  const dest = request.nextUrl.clone();
  dest.pathname = parsed.pathname || "/register";
  dest.search = parsed.search;
  return NextResponse.redirect(dest, 303);
}
