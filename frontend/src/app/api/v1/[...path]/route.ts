import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

async function proxy(
  req: NextRequest,
  context: { params: { path: string[] } }
): Promise<NextResponse> {
  const backendBase =
    process.env.BACKEND_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    (process.env.VERCEL ? "" : "http://localhost:8000");

  if (!backendBase) {
    return NextResponse.json(
      {
        detail:
          "Backend service binding (BACKEND_URL) is not configured. In Vercel → Project Settings → Build and Deployment → Root Directory, make sure Root Directory is blank ('.') rather than 'frontend', then Redeploy so both 'frontend' and 'backend' services from vercel.json are built.",
      },
      { status: 503 }
    );
  }

  const subPath = (context.params.path || []).join("/");
  const targetUrl = `${backendBase.replace(/\/$/, "")}/api/v1/${subPath}${req.nextUrl.search}`;

  const headers = new Headers();
  const apiKey = req.headers.get("x-api-key") || "dev-secret-key";
  headers.set("x-api-key", apiKey);

  const contentType = req.headers.get("content-type");
  if (contentType) {
    headers.set("content-type", contentType);
  }

  const init: RequestInit = {
    method: req.method,
    headers,
    cache: "no-store",
  };

  if (req.method !== "GET" && req.method !== "HEAD") {
    const bodyText = await req.text();
    if (bodyText) {
      init.body = bodyText;
    }
  }

  try {
    const upstream = await fetch(targetUrl, init);
    if (upstream.status === 204) {
      return new NextResponse(null, { status: 204 });
    }
    const text = await upstream.text();
    return new NextResponse(text, {
      status: upstream.status,
      headers: {
        "content-type":
          upstream.headers.get("content-type") || "application/json",
      },
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      { detail: `Failed to reach FastAPI backend (${targetUrl}): ${msg}` },
      { status: 502 }
    );
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
