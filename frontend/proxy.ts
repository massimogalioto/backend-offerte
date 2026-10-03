import { NextRequest, NextResponse } from "next/server";
import { createHash, timingSafeEqual } from "node:crypto";

function equal(a: string, b: string) {
  return timingSafeEqual(createHash("sha256").update(a).digest(), createHash("sha256").update(b).digest());
}

export function proxy(request: NextRequest) {
  const username = process.env.FRONTEND_USERNAME;
  const password = process.env.FRONTEND_PASSWORD;
  if (!username || !password) {
    if (process.env.NODE_ENV === "production") return new NextResponse("Configurare le credenziali di accesso del frontend.", { status: 503 });
    return NextResponse.next();
  }
  const authorization = request.headers.get("authorization") ?? "";
  if (authorization.startsWith("Basic ")) {
    const credentials = Buffer.from(authorization.slice(6), "base64").toString("utf8");
    const split = credentials.indexOf(":");
    if (split >= 0 && equal(credentials.slice(0, split), username) && equal(credentials.slice(split + 1), password)) return NextResponse.next();
  }
  return new NextResponse("Accesso riservato", { status: 401, headers: { "WWW-Authenticate": 'Basic realm="Energia Workspace", charset="UTF-8"', "Cache-Control": "no-store" } });
}
export const config = { matcher: ["/((?!_next/static|_next/image|icon.svg|favicon.ico).*)"] };
