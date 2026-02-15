// Supabase Edge Function: scan-pneu
// Recebe imagem (base64) e extrai marca de fogo/DOT via OpenAI Vision.

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function extractMarks(text: string): string[] {
  if (!text) return [];
  const candidates = text.toUpperCase().match(/\b[A-Z0-9-]{6,20}\b/g) ?? [];
  const invalid = new Set(["DOT", "PNEU", "TIRE", "MARCA", "FOGO", "UNKNOWN", "NENHUM"]);
  return candidates.filter((c) => !invalid.has(c));
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed" }), {
      status: 405,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  try {
    const openAiKey = Deno.env.get("OPENAI_API_KEY");
    if (!openAiKey) {
      return new Response(JSON.stringify({ error: "OPENAI_API_KEY not configured" }), {
        status: 503,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const model = Deno.env.get("OPENAI_VISION_MODEL") ?? "gpt-4o-mini";
    const body = await req.json();
    const imageBase64 = body?.image_base64;
    const mimeType = body?.mime_type ?? "image/jpeg";

    if (!imageBase64) {
      return new Response(JSON.stringify({ error: "image_base64 is required" }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const dataUrl = `data:${mimeType};base64,${imageBase64}`;
    const prompt =
      "Leia esta foto de pneu e extraia marcacao de fogo e DOT visiveis. " +
      'Retorne JSON estrito: {"marca_fogo":"...", "dot":"...", "confidence":0.0, "raw_text":"..."} ' +
      "Se nao houver certeza, use null em marca_fogo/dot.";

    const openAiResp = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${openAiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model,
        messages: [
          {
            role: "user",
            content: [
              { type: "text", text: prompt },
              { type: "image_url", image_url: { url: dataUrl } },
            ],
          },
        ],
        max_tokens: 300,
      }),
    });

    if (!openAiResp.ok) {
      const errText = await openAiResp.text();
      return new Response(JSON.stringify({ error: "OpenAI request failed", detail: errText }), {
        status: 502,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const payload = await openAiResp.json();
    const outputText = payload.choices?.[0]?.message?.content ?? "";

    let parsed: Record<string, unknown> | null = null;
    try {
      parsed = JSON.parse(outputText);
    } catch (_e) {
      parsed = null;
    }

    if (parsed) {
      return new Response(
        JSON.stringify({
          status: "ok",
          result: {
            provider: "openai",
            marca_fogo: parsed?.marca_fogo ?? null,
            dot: parsed?.dot ?? null,
            confidence: Number(parsed?.confidence ?? 0),
            raw_text: parsed?.raw_text ?? outputText,
          },
        }),
        {
          status: 200,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        },
      );
    }

    const marks = extractMarks(outputText);
    return new Response(
      JSON.stringify({
        status: "ok",
        result: {
          provider: "openai",
          marca_fogo: marks[0] ?? null,
          dot: null,
          confidence: marks.length ? 0.4 : 0.0,
          raw_text: outputText,
        },
      }),
      {
        status: 200,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      },
    );
  } catch (e) {
    return new Response(
      JSON.stringify({
        error: "Unexpected error",
        detail: e instanceof Error ? e.message : String(e),
      }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      },
    );
  }
});

