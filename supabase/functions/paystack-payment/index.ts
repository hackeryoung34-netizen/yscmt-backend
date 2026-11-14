import { createClient, type User } from "https://esm.sh/@supabase/supabase-js@2.57.4";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SUPABASE_ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY") ?? Deno.env.get("SUPABASE_PUBLISHABLE_KEY") ?? "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const PAYSTACK_SECRET_KEY = Deno.env.get("PAYSTACK_SECRET_KEY") ?? "";
const PAYSTACK_CALLBACK_URL = Deno.env.get("PAYSTACK_CALLBACK_URL") ?? "";
const PAYSTACK_EXPECTED_DOMAIN = Deno.env.get("PAYSTACK_EXPECTED_DOMAIN") ?? "";

const configuredOrigins = (Deno.env.get("PORTAL_ALLOWED_ORIGINS") ?? [
  "https://yscmtenterprise.ng",
  "https://www.yscmtenterprise.ng",
  "https://yscmtenterprise-ktfuaey93-yscmtonlines-projects.vercel.app",
].join(",")).split(",").map((origin) => origin.trim()).filter(Boolean);
const allowedOrigins = new Set(configuredOrigins);

const corsHeaders = (origin: string | null): Record<string, string> => {
  const headers: Record<string, string> = {
    "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info, x-paystack-signature",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Vary": "Origin",
  };
  if (origin && allowedOrigins.has(origin)) {
    headers["Access-Control-Allow-Origin"] = origin;
  }
  return headers;
};

const jsonResponse = (body: unknown, status = 200, origin: string | null = null) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders(origin), "Content-Type": "application/json; charset=utf-8" },
  });

const serviceClient = () => createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
  auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
});

function assertPaymentConfiguration() {
  if (!SUPABASE_URL.startsWith("https://") || !SUPABASE_ANON_KEY ||
      !SUPABASE_SERVICE_ROLE_KEY || !PAYSTACK_SECRET_KEY || !PAYSTACK_CALLBACK_URL) {
    throw new Error("Payment service configuration is incomplete.");
  }
  if (PAYSTACK_EXPECTED_DOMAIN !== "test" && PAYSTACK_EXPECTED_DOMAIN !== "live") {
    throw new Error("Expected Paystack domain must be configured as test or live.");
  }
  if (PAYSTACK_EXPECTED_DOMAIN === "test" && !PAYSTACK_SECRET_KEY.startsWith("sk_test_")) {
    throw new Error("Paystack test mode does not match the configured secret.");
  }
  if (PAYSTACK_EXPECTED_DOMAIN === "live" && !PAYSTACK_SECRET_KEY.startsWith("sk_live_")) {
    throw new Error("Paystack live mode does not match the configured secret.");
  }
  const callback = new URL(PAYSTACK_CALLBACK_URL);
  if (callback.protocol !== "https:") throw new Error("Payment callback URL must use HTTPS.");
}

async function authenticatedUser(request: Request): Promise<User> {
  const authorization = request.headers.get("authorization") ?? "";
  const match = authorization.match(/^Bearer\s+(.+)$/i);
  if (!match?.[1]) throw new Error("A valid signed-in session is required.");
  const token = match[1];
  if (token.length > 16384) throw new Error("Invalid session token.");

  const client = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    global: { headers: { Authorization: `Bearer ${token}` } },
    auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
  });
  const { data, error } = await client.auth.getUser(token);
  if (error || !data.user) throw new Error("The signed-in session is invalid or expired.");
  return data.user;
}

async function paystackRequest(path: string, init?: RequestInit) {
  const headers = new Headers(init?.headers);
  headers.set("Authorization", `Bearer ${PAYSTACK_SECRET_KEY}`);
  headers.set("Content-Type", "application/json");
  const response = await fetch(`https://api.paystack.co${path}`, {
    ...init,
    headers,
    signal: AbortSignal.timeout(12000),
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok || !payload?.status || !payload?.data) {
    throw new Error("Paystack could not complete the requested payment operation.");
  }
  return payload.data;
}

async function verifyTransaction(reference: string) {
  if (!reference || reference.length > 100) throw new Error("Invalid payment reference.");
  const data = await paystackRequest(`/transaction/verify/${encodeURIComponent(reference)}`);
  if (data.reference !== reference || data.domain !== PAYSTACK_EXPECTED_DOMAIN) {
    throw new Error("Paystack verification did not match the expected reference or environment.");
  }
  return data;
}

function sanitizedGatewayResponse(data: Record<string, unknown>) {
  return {
    status: data.status,
    reference: data.reference,
    amount: data.amount,
    currency: data.currency,
    paid_at: data.paid_at ?? null,
    channel: data.channel ?? null,
    transaction_date: data.transaction_date ?? null,
    transaction_id: data.id ?? null,
    fees: data.fees ?? null,
    customer_email: (data.customer as Record<string, unknown> | undefined)?.email ?? null,
  };
}

async function initializePayment(user: User, enrollmentId: string) {
  if (!/^[0-9a-f-]{36}$/i.test(enrollmentId)) throw new Error("A valid enrolment ID is required.");
  const service = serviceClient();
  const { data, error } = await service.rpc("portal_prepare_paystack_payment", {
    p_user_id: user.id,
    p_enrollment_id: enrollmentId,
  });
  if (error) throw new Error("This enrolment is not ready for online payment.");
  const payment = Array.isArray(data) ? data[0] : data;
  if (!payment?.reference || !payment.amount_kobo || payment.currency !== "NGN" || !payment.email) {
    throw new Error("The payment details could not be prepared safely.");
  }
  if (payment.authorization_url) {
    return { reference: payment.reference, authorization_url: payment.authorization_url };
  }

  const checkout = await paystackRequest("/transaction/initialize", {
    method: "POST",
    body: JSON.stringify({
      email: payment.email,
      amount: payment.amount_kobo,
      currency: payment.currency,
      reference: payment.reference,
      callback_url: PAYSTACK_CALLBACK_URL,
      metadata: { user_id: user.id, enrollment_id: enrollmentId, provider: "YSCMT Enterprise" },
    }),
  });
  const checkoutUrl = new URL(checkout.authorization_url);
  if (checkoutUrl.protocol !== "https:" || checkoutUrl.hostname !== "checkout.paystack.com" ||
      checkout.reference !== payment.reference) {
    throw new Error("Paystack returned an unexpected checkout response.");
  }

  const { error: saveError } = await service.rpc("portal_set_paystack_authorization_url", {
    p_reference: payment.reference,
    p_authorization_url: checkout.authorization_url,
  });
  if (saveError) throw new Error("The checkout session could not be safely saved.");
  return { reference: payment.reference, authorization_url: checkout.authorization_url };
}

async function verifyForUser(user: User, reference: string) {
  const verified = await verifyTransaction(reference);
  if (verified.status !== "success") {
    return { status: verified.status ?? "pending", confirmed: false };
  }
  const service = serviceClient();
  const { data, error } = await service.rpc("portal_confirm_paystack_payment", {
    p_user_id: user.id,
    p_reference: reference,
    p_amount_kobo: verified.amount,
    p_currency: verified.currency,
    p_gateway_response: sanitizedGatewayResponse(verified),
  });
  if (error) throw new Error("The verified payment could not be matched to this account.");
  const payment = Array.isArray(data) ? data[0] : data;
  return { confirmed: true, payment };
}

function toHex(buffer: ArrayBuffer) {
  return Array.from(new Uint8Array(buffer), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function constantTimeEqual(left: string, right: string) {
  if (left.length !== right.length) return false;
  let result = 0;
  for (let i = 0; i < left.length; i++) result |= left.charCodeAt(i) ^ right.charCodeAt(i);
  return result === 0;
}

async function validPaystackSignature(rawBody: string, signature: string) {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(PAYSTACK_SECRET_KEY),
    { name: "HMAC", hash: "SHA-512" },
    false,
    ["sign"],
  );
  const digest = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(rawBody));
  return constantTimeEqual(toHex(digest), signature.toLowerCase());
}

async function handleWebhook(request: Request) {
  const signature = request.headers.get("x-paystack-signature") ?? "";
  const rawBody = await request.text();
  if (rawBody.length > 131072 || !signature || !(await validPaystackSignature(rawBody, signature))) {
    return jsonResponse({ error: "Invalid webhook signature." }, 401);
  }

  let event: Record<string, unknown>;
  try { event = JSON.parse(rawBody); }
  catch { return jsonResponse({ error: "Invalid webhook payload." }, 400); }

  if (event.event !== "charge.success") return jsonResponse({ received: true, ignored: true });
  const data = event.data as Record<string, unknown> | undefined;
  const reference = typeof data?.reference === "string" ? data.reference : "";
  if (!reference) return jsonResponse({ error: "Missing payment reference." }, 400);

  const verified = await verifyTransaction(reference);
  if (verified.status !== "success") return jsonResponse({ received: true, confirmed: false }, 202);

  const service = serviceClient();
  const { error } = await service.rpc("portal_confirm_paystack_payment", {
    p_user_id: null,
    p_reference: reference,
    p_amount_kobo: verified.amount,
    p_currency: verified.currency,
    p_gateway_response: sanitizedGatewayResponse(verified),
  });
  if (error) return jsonResponse({ error: "Verified payment could not be reconciled." }, 500);
  return jsonResponse({ received: true, confirmed: true });
}

Deno.serve(async (request: Request) => {
  const origin = request.headers.get("origin");
  if (request.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders(origin) });
  }
  if (request.method !== "POST") return jsonResponse({ error: "Method not allowed." }, 405, origin);

  try {
    assertPaymentConfiguration();
    const url = new URL(request.url);
    if (url.searchParams.get("action") === "webhook") {
      return await handleWebhook(request);
    }

    const rawBody = await request.text();
    if (rawBody.length > 8192) return jsonResponse({ error: "Request is too large." }, 413, origin);
    let body: Record<string, unknown>;
    try { body = JSON.parse(rawBody); }
    catch { return jsonResponse({ error: "Invalid request body." }, 400, origin); }

    const user = await authenticatedUser(request);
    if (body.action === "initialize") {
      const enrollmentId = typeof body.enrollment_id === "string" ? body.enrollment_id : "";
      const checkout = await initializePayment(user, enrollmentId);
      return jsonResponse(checkout, 200, origin);
    }
    if (body.action === "verify") {
      const reference = typeof body.reference === "string" ? body.reference : "";
      const result = await verifyForUser(user, reference);
      return jsonResponse(result, result.confirmed ? 200 : 202, origin);
    }
    return jsonResponse({ error: "Unsupported payment action." }, 400, origin);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Payment service unavailable.";
    const status = message.includes("session") ? 401 :
      message.includes("not ready") || message.includes("could not be matched") ? 403 : 503;
    return jsonResponse({ error: message }, status, origin);
  }
});
