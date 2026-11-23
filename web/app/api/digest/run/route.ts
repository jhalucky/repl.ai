import { NextRequest, NextResponse } from "next/server";
import { apiOrigin } from "@/lib/api";

export async function POST(request: NextRequest) {
  const body = await request.formData();
  const response = await fetch(`${apiOrigin()}/digest/run`, {
    method: "POST",
    body,
    redirect: "manual",
  });
  const location = response.headers.get("location") || "/register";
  const parsed = new URL(location, apiOrigin());
  const dest = request.nextUrl.clone();
  dest.pathname = "/register";
  dest.search = "";
  const notice = parsed.searchParams.get("notice");
  const error = parsed.searchParams.get("error");
  if (notice) dest.searchParams.set("notice", notice);
  if (error) dest.searchParams.set("error", error);
  return NextResponse.redirect(dest, 303);
}
